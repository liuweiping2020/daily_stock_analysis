# -*- coding: utf-8 -*-
"""Factor engine — factor computation and evaluation framework.

Inspired by Microsoft Qlib's factor mining pipeline, this module provides:
1. A Factor base class for pluggable factor definitions
2. Built-in technical and statistical factors
3. Factor evaluation (IC, rank IC, factor returns)
4. Factor registry for extensibility
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FactorValue:
    """A computed factor value for a single stock on a single date."""
    factor_name: str = ""
    code: str = ""
    date: Optional[date] = None
    value: float = 0.0
    raw_data: Dict[str, Any] = field(default_factory=dict)


class Factor(ABC):
    """Abstract base class for factors.

    A factor takes historical daily bars and computes a numeric value
    that can be used for ranking stocks or generating signals.
    """

    name: str = "base"
    description: str = ""
    category: str = "technical"  # technical/fundamental/statistical/custom

    @abstractmethod
    def compute(self, bars: List[Any]) -> float:
        """Compute factor value from a list of daily bars.

        Args:
            bars: List of daily bar objects (with .close, .high, .low, .volume)
                  sorted by date ascending.

        Returns:
            Numeric factor value (NaN if insufficient data)
        """
        ...

    def min_bars(self) -> int:
        """Minimum number of bars needed to compute this factor."""
        return 10


# ============================================================
# Built-in Technical Factors
# ============================================================

class MAFactor(Factor):
    """Moving Average factor — distance of price from MA."""

    name = "ma_distance"
    description = "价格相对移动平均线的偏离度"
    category = "technical"

    def __init__(self, window: int = 20):
        self.window = window

    def compute(self, bars: List[Any]) -> float:
        if len(bars) < self.window:
            return float('nan')
        closes = [b.close for b in bars[-self.window:] if b.close is not None]
        if len(closes) < self.window:
            return float('nan')
        ma = sum(closes) / len(closes)
        latest = closes[-1]
        if ma == 0:
            return float('nan')
        return (latest - ma) / ma * 100  # percentage deviation

    def min_bars(self) -> int:
        return self.window


class RSIFactor(Factor):
    """RSI factor — Relative Strength Index."""

    name = "rsi"
    description = "RSI 相对强弱指标"
    category = "technical"

    def __init__(self, period: int = 14):
        self.period = period

    def compute(self, bars: List[Any]) -> float:
        if len(bars) < self.period + 1:
            return float('nan')
        closes = [b.close for b in bars if b.close is not None]
        if len(closes) < self.period + 1:
            return float('nan')

        gains = []
        losses = []
        for i in range(1, self.period + 1):
            change = closes[-i] - closes[-i-1]
            if change > 0:
                gains.append(change)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(change))

        avg_gain = sum(gains) / self.period
        avg_loss = sum(losses) / self.period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def min_bars(self) -> int:
        return self.period + 1


class VolatilityFactor(Factor):
    """Volatility factor — standard deviation of daily returns."""

    name = "volatility"
    description = "日收益率标准差（波动率）"
    category = "statistical"

    def __init__(self, window: int = 20):
        self.window = window

    def compute(self, bars: List[Any]) -> float:
        if len(bars) < self.window + 1:
            return float('nan')
        closes = [b.close for b in bars[-(self.window+1):] if b.close is not None]
        if len(closes) < self.window + 1:
            return float('nan')

        returns = []
        for i in range(1, len(closes)):
            if closes[i-1] > 0:
                returns.append((closes[i] - closes[i-1]) / closes[i-1])

        if len(returns) < 2:
            return float('nan')

        avg = sum(returns) / len(returns)
        variance = sum((r - avg) ** 2 for r in returns) / len(returns)
        return math.sqrt(variance) * math.sqrt(252)  # annualized

    def min_bars(self) -> int:
        return self.window + 1


class MomentumFactor(Factor):
    """Momentum factor — return over past N days."""

    name = "momentum"
    description = "N日动量（区间收益率）"
    category = "technical"

    def __init__(self, window: int = 20):
        self.window = window

    def compute(self, bars: List[Any]) -> float:
        if len(bars) < self.window + 1:
            return float('nan')
        closes = [b.close for b in bars if b.close is not None]
        if len(closes) < self.window + 1:
            return float('nan')

        start_close = closes[-(self.window + 1)]
        end_close = closes[-1]

        if start_close == 0:
            return float('nan')
        return (end_close - start_close) / start_close * 100

    def min_bars(self) -> int:
        return self.window + 1


class VolumeFactor(Factor):
    """Volume ratio factor — recent volume vs average volume."""

    name = "volume_ratio"
    description = "近期成交量相对均量比率"
    category = "technical"

    def __init__(self, short_window: int = 5, long_window: int = 20):
        self.short_window = short_window
        self.long_window = long_window

    def compute(self, bars: List[Any]) -> float:
        if len(bars) < self.long_window:
            return float('nan')
        volumes = [b.volume for b in bars if hasattr(b, 'volume') and b.volume is not None]
        if len(volumes) < self.long_window:
            return float('nan')

        short_avg = sum(volumes[-self.short_window:]) / self.short_window
        long_avg = sum(volumes[-self.long_window:]) / self.long_window

        if long_avg == 0:
            return float('nan')
        return short_avg / long_avg

    def min_bars(self) -> int:
        return self.long_window


class TurnoverFactor(Factor):
    """Price-volume correlation factor."""

    name = "price_volume_corr"
    description = "价量相关系数"
    category = "statistical"

    def __init__(self, window: int = 20):
        self.window = window

    def compute(self, bars: List[Any]) -> float:
        if len(bars) < self.window:
            return float('nan')
        recent = bars[-self.window:]
        closes = [b.close for b in recent if b.close is not None]
        volumes = [b.volume for b in recent if hasattr(b, 'volume') and b.volume is not None]

        if len(closes) < self.window or len(volumes) < self.window:
            return float('nan')

        # Pearson correlation
        n = len(closes)
        mean_c = sum(closes) / n
        mean_v = sum(volumes) / n

        cov = sum((c - mean_c) * (v - mean_v) for c, v in zip(closes, volumes)) / n
        std_c = math.sqrt(sum((c - mean_c) ** 2 for c in closes) / n)
        std_v = math.sqrt(sum((v - mean_v) ** 2 for v in volumes) / n)

        if std_c == 0 or std_v == 0:
            return 0.0
        return cov / (std_c * std_v)

    def min_bars(self) -> int:
        return self.window


# ============================================================
# Factor Registry
# ============================================================

_FACTOR_REGISTRY: Dict[str, type[Factor]] = {}

def register_factor(cls: type[Factor]) -> type[Factor]:
    """Decorator to register a factor class."""
    _FACTOR_REGISTRY[cls.name] = cls
    return cls

def get_factor(name: str, **kwargs) -> Optional[Factor]:
    """Instantiate a registered factor by name."""
    cls = _FACTOR_REGISTRY.get(name)
    if cls is None:
        return None
    return cls(**kwargs)

def list_factors() -> List[Dict[str, str]]:
    """List all registered factors."""
    return [{"name": k, "description": v.description, "category": v.category} for k, v in _FACTOR_REGISTRY.items()]

# Register built-in factors
for _f in [MAFactor, RSIFactor, VolatilityFactor, MomentumFactor, VolumeFactor, TurnoverFactor]:
    register_factor(_f)


# ============================================================
# Factor Engine — batch computation and evaluation
# ============================================================

class FactorEngine:
    """Batch factor computation and evaluation engine.

    Computes multiple factors for a stock and evaluates their
    predictive power (IC, rank IC, factor returns).
    """

    def __init__(self, factors: Optional[List[Factor]] = None):
        self.factors = factors or self._default_factors()

    @staticmethod
    def _default_factors() -> List[Factor]:
        return [
            MAFactor(window=20),
            RSIFactor(period=14),
            VolatilityFactor(window=20),
            MomentumFactor(window=20),
            VolumeFactor(short_window=5, long_window=20),
            TurnoverFactor(window=20),
        ]

    def compute_all(self, bars: List[Any], code: str = "") -> List[FactorValue]:
        """Compute all registered factors for a single stock."""
        results = []
        for factor in self.factors:
            try:
                value = factor.compute(bars)
                latest_date = bars[-1].date if bars and hasattr(bars[-1], 'date') else None
                results.append(FactorValue(
                    factor_name=factor.name,
                    code=code,
                    date=latest_date,
                    value=value,
                ))
            except Exception as e:
                logger.warning("[FactorEngine] factor %s failed: %s", factor.name, e)
                results.append(FactorValue(
                    factor_name=factor.name,
                    code=code,
                    value=float('nan'),
                ))
        return results

    def compute_factor_series(
        self,
        factor: Factor,
        bars: List[Any],
        code: str = "",
    ) -> List[FactorValue]:
        """Compute a single factor across a rolling window of bars.

        Produces a time series of factor values, useful for IC evaluation.
        """
        results = []
        min_bars = factor.min_bars()

        for i in range(min_bars, len(bars) + 1):
            window_bars = bars[:i]
            try:
                value = factor.compute(window_bars)
                bar_date = window_bars[-1].date if hasattr(window_bars[-1], 'date') else None
                results.append(FactorValue(
                    factor_name=factor.name,
                    code=code,
                    date=bar_date,
                    value=value,
                ))
            except Exception as e:
                logger.warning("[FactorEngine] rolling compute failed at idx %d: %s", i, e)

        return results

    def evaluate_ic(
        self,
        factor_values: List[FactorValue],
        forward_returns: List[Tuple[date, float]],
    ) -> Dict[str, float]:
        """Evaluate Information Coefficient of a factor.

        Args:
            factor_values: Time series of factor values
            forward_returns: Time series of forward returns (same dates)

        Returns:
            Dict with IC, rank_IC, and IC IR (information ratio)
        """
        # Match by date
        factor_map = {fv.date: fv.value for fv in factor_values if fv.date and not math.isnan(fv.value)}
        return_map = {d: r for d, r in forward_returns if d in factor_map}

        common_dates = sorted(set(factor_map.keys()) & set(return_map.keys()))
        if len(common_dates) < 5:
            return {"ic": 0.0, "rank_ic": 0.0, "ic_ir": 0.0, "sample_size": len(common_dates)}

        factor_vals = [factor_map[d] for d in common_dates]
        return_vals = [return_map[d] for d in common_dates]

        # Pearson IC
        n = len(factor_vals)
        mean_f = sum(factor_vals) / n
        mean_r = sum(return_vals) / n
        cov = sum((f - mean_f) * (r - mean_r) for f, r in zip(factor_vals, return_vals)) / n
        std_f = math.sqrt(sum((f - mean_f) ** 2 for f in factor_vals) / n)
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in return_vals) / n)
        ic = cov / (std_f * std_r) if std_f > 0 and std_r > 0 else 0.0

        # Rank IC (Spearman)
        factor_ranks = self._rank(factor_vals)
        return_ranks = self._rank(return_vals)
        mean_fr = sum(factor_ranks) / n
        mean_rr = sum(return_ranks) / n
        cov_r = sum((f - mean_fr) * (r - mean_rr) for f, r in zip(factor_ranks, return_ranks)) / n
        std_fr = math.sqrt(sum((f - mean_fr) ** 2 for f in factor_ranks) / n)
        std_rr = math.sqrt(sum((r - mean_rr) ** 2 for r in return_ranks) / n)
        rank_ic = cov_r / (std_fr * std_rr) if std_fr > 0 and std_rr > 0 else 0.0

        # IC IR (mean IC / std IC over rolling windows)
        ic_series = []
        window = min(20, n // 2)
        if window >= 5:
            for i in range(window, n + 1):
                fv = factor_vals[i-window:i]
                rv = return_vals[i-window:i]
                w_mean_f = sum(fv) / window
                w_mean_r = sum(rv) / window
                w_cov = sum((f - w_mean_f) * (r - w_mean_r) for f, r in zip(fv, rv)) / window
                w_std_f = math.sqrt(sum((f - w_mean_f) ** 2 for f in fv) / window)
                w_std_r = math.sqrt(sum((r - w_mean_r) ** 2 for r in rv) / window)
                w_ic = w_cov / (w_std_f * w_std_r) if w_std_f > 0 and w_std_r > 0 else 0.0
                ic_series.append(w_ic)

            if ic_series:
                ic_mean = sum(ic_series) / len(ic_series)
                ic_std = math.sqrt(sum((x - ic_mean) ** 2 for x in ic_series) / len(ic_series))
                ic_ir = ic_mean / ic_std if ic_std > 0 else 0.0
            else:
                ic_ir = 0.0
        else:
            ic_ir = 0.0

        return {
            "ic": round(ic, 4),
            "rank_ic": round(rank_ic, 4),
            "ic_ir": round(ic_ir, 4),
            "sample_size": len(common_dates),
        }

    @staticmethod
    def _rank(values: List[float]) -> List[float]:
        """Compute ranks of values (1-based, average for ties)."""
        indexed = sorted(enumerate(values), key=lambda x: x[1])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(indexed):
            j = i
            while j < len(indexed) - 1 and indexed[j+1][1] == indexed[i][1]:
                j += 1
            avg_rank = (i + 1 + j + 1) / 2
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = avg_rank
            i = j + 1
        return ranks
