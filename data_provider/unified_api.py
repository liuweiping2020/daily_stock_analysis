# -*- coding: utf-8 -*-
"""Unified data API — market-agnostic data access layer.

Inspired by OpenBB's unified financial data platform, this module provides
a single entry point for fetching stock data across all markets (cn/hk/us),
abstracting away the underlying data source selection logic.

Key features:
- Market detection from stock code (no manual market parameter needed)
- Unified response format regardless of which fetcher served the request
- Support for daily bars, realtime quotes, fundamentals, and search
- Automatic market-aware fetcher filtering (delegated to DataFetcherManager)

The unified layer intentionally stays thin: it normalizes the existing
``DataFetcherManager`` responses (tuple/dataframe/``UnifiedRealtimeQuote``
/nested fundamental context) into flat, market-agnostic dataclasses. All
multi-source fallback, circuit breaking and health tracking remain owned by
``DataFetcherManager``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def detect_market(code: str) -> str:
    """Auto-detect market from stock code.

    Returns: 'cn', 'hk', or 'us'.

    Recognition order keeps ambiguous forms (HK prefix, 5-digit codes, US
    index tickers, exchange suffixes) ahead of the generic 6-digit CN rule.
    The result is informational — ``DataFetcherManager`` re-detects the
    market internally for source routing, so a mismatch here never breaks
    data fetching.
    """
    code = (code or "").strip().upper()

    # US indices: ^GSPC, ^IXIC, ^DJI ...
    if code.startswith("^"):
        return "us"

    # Explicit exchange suffix: 600519.SH / 000001.SZ / 600519.BJ / 00700.HK / AAPL.US
    if "." in code:
        _base, _, suffix = code.rpartition(".")
        if suffix in {"SH", "SZ", "SS", "BJ"}:
            return "cn"
        if suffix == "HK":
            return "hk"
        if suffix == "US":
            return "us"

    # HK: starts with 'HK' (e.g. HK00700) or 5-digit number (e.g. 00700)
    if code.startswith("HK") or (code.isdigit() and len(code) == 5):
        return "hk"

    # US: alphabetic ticker (1-5 letters), e.g. AAPL, TSLA
    if re.match(r"^[A-Z]{1,5}$", code):
        return "us"

    # CN: 6-digit number, e.g. 600519
    if re.match(r"^\d{6}$", code):
        return "cn"

    # Default to CN
    return "cn"


@dataclass
class UnifiedDailyBar:
    """Normalized daily OHLCV bar — same shape for all markets."""
    date: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    change_pct: Optional[float] = None
    turnover: Optional[float] = None


@dataclass
class UnifiedQuote:
    """Normalized realtime quote — same shape for all markets."""
    code: str = ""
    name: str = ""
    market: str = ""
    current_price: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: float = 0.0
    turnover: Optional[float] = None
    prev_close: Optional[float] = None
    timestamp: Optional[str] = None


@dataclass
class UnifiedFundamental:
    """Normalized fundamental data — same shape for all markets."""
    code: str = ""
    market: str = ""
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    market_cap: Optional[float] = None
    dividend_yield: Optional[float] = None
    roe: Optional[float] = None
    debt_ratio: Optional[float] = None
    revenue: Optional[float] = None
    net_profit: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    revenue_growth: Optional[float] = None
    profit_growth: Optional[float] = None
    source: str = ""


@dataclass
class StockSearchResult:
    """Stock search result item."""
    code: str = ""
    name: str = ""
    market: str = ""
    exchange: Optional[str] = None


def _to_float(value: Any) -> Optional[float]:
    """Best-effort float conversion that tolerates None / NaN / numeric strings."""
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    # Filter NaN / inf so they don't leak into the unified response.
    if result != result:  # NaN check
        return None
    if result in (float("inf"), float("-inf")):
        return None
    return result


class UnifiedDataAPI:
    """Unified market-agnostic data access API.

    This is the main entry point for all data fetching. It:
    1. Auto-detects market from stock code
    2. Delegates source selection / fallback to ``DataFetcherManager``
    3. Normalizes the response to a unified, flat format

    Usage::

        api = UnifiedDataAPI()
        bars = api.get_daily_bars("600519", days=30)
        quote = api.get_realtime_quote("AAPL")
        fundamentals = api.get_fundamentals("hk00700")
    """

    def __init__(self):
        self._manager: Optional[Any] = None

    @property
    def manager(self):
        """Lazy-init DataFetcherManager (avoids import cost until first use)."""
        if self._manager is None:
            from data_provider.base import DataFetcherManager
            self._manager = DataFetcherManager()
        return self._manager

    def get_daily_bars(
        self,
        code: str,
        days: int = 30,
        end_date: Optional[date] = None,
        market: Optional[str] = None,
    ) -> List[UnifiedDailyBar]:
        """Fetch daily OHLCV bars for any market.

        Args:
            code: Stock code (market auto-detected if not specified)
            days: Number of trading days to fetch
            end_date: End date (default: today)
            market: Force market ('cn'/'hk'/'us'), auto-detect if None

        Returns:
            List of UnifiedDailyBar, oldest first. Empty list on failure.
        """
        # market is informational here; DataFetcherManager routes by code.
        _ = market or detect_market(code)
        end_date = end_date or date.today()
        start_date = end_date - timedelta(days=days * 2)  # buffer for weekends

        try:
            result = self.manager.get_daily_data(
                code=code,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
            )
            # DataFetcherManager.get_daily_data returns Tuple[DataFrame, source_name].
            if isinstance(result, tuple):
                df = result[0]
            else:
                df = result
            if df is None or getattr(df, "empty", True):
                return []

            bars: List[UnifiedDailyBar] = []
            for _, row in df.iterrows():
                bar = UnifiedDailyBar(
                    date=str(row.get("date", "")),
                    open=float(row.get("open", 0) or 0),
                    high=float(row.get("high", 0) or 0),
                    low=float(row.get("low", 0) or 0),
                    close=float(row.get("close", 0) or 0),
                    volume=float(row.get("volume", 0) or 0),
                    # Canonical daily schema uses pct_chg/amount; keep aliases as fallback.
                    change_pct=_to_float(row.get("pct_chg", row.get("change_pct"))),
                    turnover=_to_float(row.get("amount", row.get("turnover"))),
                )
                bars.append(bar)

            return bars[-days:] if len(bars) > days else bars
        except Exception as exc:
            logger.error("[UnifiedAPI] get_daily_bars failed for %s: %s", code, exc)
            return []

    def get_realtime_quote(self, code: str, market: Optional[str] = None) -> Optional[UnifiedQuote]:
        """Fetch realtime quote for any market.

        ``DataFetcherManager.get_realtime_quote`` returns a
        ``UnifiedRealtimeQuote`` object (or None). Field names differ from the
        unified response, so they are remapped here.
        """
        market = market or detect_market(code)

        try:
            quote_data = self.manager.get_realtime_quote(code)
            if quote_data is None:
                return None

            if isinstance(quote_data, dict):
                data: Dict[str, Any] = quote_data
            else:
                data = getattr(quote_data, "__dict__", {}) or {}

            def _get(*keys: str, default: Any = None) -> Any:
                for key in keys:
                    if key in data and data[key] is not None:
                        return data[key]
                return default

            source_raw = data.get("source")
            timestamp = (
                data.get("timestamp")
                or data.get("update_time")
                or (getattr(source_raw, "value", None) if source_raw is not None else None)
            )

            return UnifiedQuote(
                code=str(data.get("code", code) or code),
                name=str(data.get("name", "") or ""),
                market=market,
                current_price=float(_get("price", "current_price", default=0) or 0),
                change=float(_get("change_amount", "change", default=0) or 0),
                change_pct=float(_get("change_pct", "pct_change", default=0) or 0),
                open=float(_get("open_price", "open", default=0) or 0),
                high=float(_get("high", default=0) or 0),
                low=float(_get("low", default=0) or 0),
                volume=float(_get("volume", default=0) or 0),
                turnover=_to_float(_get("amount", "turnover")),
                prev_close=_to_float(_get("pre_close", "prev_close")),
                timestamp=timestamp,
            )
        except Exception as exc:
            logger.error("[UnifiedAPI] get_realtime_quote failed for %s: %s", code, exc)
            return None

    def get_fundamentals(self, code: str, market: Optional[str] = None) -> Optional[UnifiedFundamental]:
        """Fetch fundamental data for any market.

        ``DataFetcherManager`` exposes ``get_fundamental_context`` which
        returns a nested, fail-open context dict (valuation/growth/earnings
        blocks, each with ``status``/``data``). This method flattens the
        relevant metrics into :class:`UnifiedFundamental`.
        """
        market = market or detect_market(code)

        try:
            context = self.manager.get_fundamental_context(code)
            if not isinstance(context, dict) or not context:
                return None

            valuation = self._block_data(context.get("valuation"))
            growth = self._block_data(context.get("growth"))
            earnings = self._block_data(context.get("earnings"))

            dividend_yield: Optional[float] = None
            dividend = earnings.get("dividend")
            if isinstance(dividend, dict):
                dividend_yield = _to_float(
                    dividend.get("ttm_dividend_yield_pct", dividend.get("dividend_yield"))
                )

            source = self._summarize_source_chain(context.get("source_chain"))

            fundamental = UnifiedFundamental(
                code=code,
                market=str(context.get("market", market) or market),
                pe_ratio=_to_float(valuation.get("pe_ratio", valuation.get("pe"))),
                pb_ratio=_to_float(valuation.get("pb_ratio", valuation.get("pb"))),
                ps_ratio=_to_float(valuation.get("ps_ratio", valuation.get("ps"))),
                market_cap=_to_float(
                    valuation.get("market_cap", valuation.get("total_mv", valuation.get("market_value")))
                ),
                dividend_yield=dividend_yield,
                roe=_to_float(growth.get("roe", earnings.get("roe"))),
                debt_ratio=_to_float(
                    earnings.get("debt_ratio", earnings.get("asset_liability_ratio"))
                ),
                revenue=_to_float(
                    earnings.get("revenue", earnings.get("total_revenue"))
                ),
                net_profit=_to_float(
                    earnings.get("net_profit", earnings.get("net_profit_parent", earnings.get("net_income")))
                ),
                gross_margin=_to_float(growth.get("gross_margin", earnings.get("gross_margin"))),
                net_margin=_to_float(
                    earnings.get("net_margin", earnings.get("profit_margin"))
                ),
                revenue_growth=_to_float(
                    growth.get("revenue_growth", growth.get("revenue_yoy"))
                ),
                profit_growth=_to_float(
                    growth.get("profit_growth", growth.get("net_profit_yoy", growth.get("profit_yoy")))
                ),
                source=source,
            )

            # Fail-open context may return all-empty blocks (e.g. pipeline
            # disabled or market not supported). Treat that as "not found"
            # so the API can respond 404 instead of an all-None payload.
            key_metrics = (
                fundamental.pe_ratio, fundamental.pb_ratio, fundamental.market_cap,
                fundamental.roe, fundamental.revenue, fundamental.net_profit,
            )
            if all(metric is None for metric in key_metrics):
                return None
            return fundamental
        except Exception as exc:
            logger.error("[UnifiedAPI] get_fundamentals failed for %s: %s", code, exc)
            return None

    @staticmethod
    def _block_data(block: Any) -> Dict[str, Any]:
        """Extract the ``data`` payload from a fundamental context block."""
        if isinstance(block, dict):
            data = block.get("data")
            if isinstance(data, dict):
                return data
            # Some blocks may already be flat payloads (no status/data wrapper).
            if "status" not in block and "data" not in block:
                return block
        return {}

    @staticmethod
    def _summarize_source_chain(source_chain: Any) -> str:
        """Join provider names from the fundamental source chain for debugging."""
        if not isinstance(source_chain, list) or not source_chain:
            return ""
        names: List[str] = []
        seen = set()
        for item in source_chain:
            if not isinstance(item, dict):
                continue
            provider = str(item.get("provider") or "").strip()
            if provider and provider not in seen:
                seen.add(provider)
                names.append(provider)
        return ",".join(names)

    def search_stocks(self, keyword: str, limit: int = 10) -> List[StockSearchResult]:
        """Search stocks by name or code across all markets.

        Uses the cached frontend stock-name index (code -> name) maintained by
        :mod:`src.data.stock_index_loader`. Results are de-duplicated by name
        so the same stock surfaced under multiple lookup keys only appears once.
        """
        results: List[StockSearchResult] = []
        keyword = (keyword or "").strip().lower()
        if not keyword:
            return results

        try:
            from src.data.stock_index_loader import get_stock_name_index_map
            name_map = get_stock_name_index_map()
        except Exception as exc:
            logger.debug("[UnifiedAPI] stock index unavailable: %s", exc)
            return results

        if not name_map:
            return results

        seen_names: set = set()
        for code, name in name_map.items():
            name_str = str(name or "")
            if keyword not in str(code).lower() and keyword not in name_str.lower():
                continue
            if name_str in seen_names:
                continue
            seen_names.add(name_str)
            results.append(StockSearchResult(
                code=str(code),
                name=name_str,
                market=detect_market(str(code)),
                exchange=None,
            ))
            if len(results) >= limit:
                break

        return results

    def get_multi_market_quotes(self, codes: List[str]) -> Dict[str, Optional[UnifiedQuote]]:
        """Batch fetch quotes for multiple stocks across markets."""
        return {code: self.get_realtime_quote(code) for code in codes}

    def get_market_summary(self, code: str, days: int = 30) -> Dict[str, Any]:
        """Get a comprehensive summary for a stock: bars + quote + fundamentals.

        Returns a dict with keys: 'code', 'market', 'bars', 'quote',
        'fundamentals'. ``quote`` / ``fundamentals`` are ``None`` when the
        underlying source returned no data.
        """
        market = detect_market(code)
        bars = self.get_daily_bars(code, days=days)
        quote = self.get_realtime_quote(code)
        fundamentals = self.get_fundamentals(code)

        return {
            "code": code,
            "market": market,
            "bars": [asdict(bar) for bar in bars],
            "quote": asdict(quote) if quote is not None else None,
            "fundamentals": asdict(fundamentals) if fundamentals is not None else None,
        }


# Thread-safe global singleton.
_unified_api: Optional[UnifiedDataAPI] = None
_unified_api_lock = Lock()


def get_unified_api() -> UnifiedDataAPI:
    """Get the global UnifiedDataAPI singleton (thread-safe)."""
    global _unified_api
    if _unified_api is None:
        with _unified_api_lock:
            if _unified_api is None:
                _unified_api = UnifiedDataAPI()
    return _unified_api
