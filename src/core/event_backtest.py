# -*- coding: utf-8 -*-
"""Event-driven backtesting engine.

Inspired by Backtrader's event-driven architecture, this engine processes
market data bar-by-bar, generates signals via Strategy objects, and simulates
order execution with configurable rules.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from src.core.strategy import (
    MarketContext,
    SignalType,
    Strategy,
    TradingSignal,
)

logger = logging.getLogger(__name__)


@dataclass
class BacktestPosition:
    """Simplified position for event-driven backtest."""
    code: str = ""
    quantity: int = 0
    avg_cost: float = 0.0
    entry_date: Optional[date] = None

    @property
    def is_open(self) -> bool:
        return self.quantity > 0

    @property
    def market_value(self) -> float:
        return 0.0  # computed at evaluation time


@dataclass
class BacktestTrade:
    """A single trade record from event-driven backtest."""
    code: str = ""
    side: str = ""  # buy/sell
    quantity: int = 0
    price: float = 0.0
    commission: float = 0.0
    timestamp: Optional[date] = None
    signal_reason: str = ""
    pnl: float = 0.0  # realized PnL for sells


@dataclass
class EventBacktestConfig:
    """Configuration for event-driven backtest."""
    initial_capital: float = 100000.0
    commission_rate: float = 0.0003  # 万三
    min_commission: float = 5.0      # 最低5元
    stamp_duty_rate: float = 0.0005  # 印花税 卖出
    slippage: float = 0.0            # 滑点
    allow_short: bool = False         # 是否允许做空


@dataclass
class EventBacktestResult:
    """Result of an event-driven backtest run."""
    code: str = ""
    strategy_name: str = ""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    initial_capital: float = 0.0
    final_value: float = 0.0
    total_return_pct: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: Optional[float] = None
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    signals: List[TradingSignal] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades


class EventBacktestEngine:
    """Event-driven backtesting engine.

    Processes bars sequentially, generates signals via Strategy,
    simulates order execution with commission/slippage rules.
    """

    def __init__(self, config: Optional[EventBacktestConfig] = None):
        self.config = config or EventBacktestConfig()

    def run(
        self,
        strategy: Strategy,
        bars: List[Any],
        code: str = "",
    ) -> EventBacktestResult:
        """Run a backtest for a single stock.

        Args:
            strategy: Strategy instance to use
            bars: List of daily bars (DailyBarLike) sorted by date ascending
            code: Stock code

        Returns:
            EventBacktestResult with trades, equity curve, and metrics
        """
        result = EventBacktestResult(
            code=code,
            strategy_name=strategy.name,
            initial_capital=self.config.initial_capital,
        )

        if not bars:
            return result

        result.start_date = bars[0].date if hasattr(bars[0], 'date') else None
        result.end_date = bars[-1].date if hasattr(bars[-1], 'date') else None

        cash = self.config.initial_capital
        position = BacktestPosition(code=code)
        warmup = strategy.warmup_period()
        equity_curve = []
        all_signals = []

        for i, bar in enumerate(bars):
            bar_date = bar.date if hasattr(bar, 'date') else None
            bar_close = bar.close if hasattr(bar, 'close') and bar.close else 0.0

            # Skip warmup period
            if i < warmup:
                equity = cash + position.quantity * bar_close
                equity_curve.append({
                    "date": str(bar_date) if bar_date else "",
                    "cash": round(cash, 2),
                    "position_value": round(position.quantity * bar_close, 2),
                    "equity": round(equity, 2),
                })
                continue

            # Build context for strategy
            ctx = MarketContext(
                code=code,
                current_date=bar_date,
                bars=bars[:i+1],
                position_info={"quantity": position.quantity, "avg_cost": position.avg_cost} if position.is_open else None,
            )

            # Generate signal
            try:
                signal = strategy.generate_signal(ctx)
                all_signals.append(signal)
            except Exception as e:
                logger.warning("[EventBacktest] strategy error at %s: %s", bar_date, e)
                signal = TradingSignal(signal_type=SignalType.NO_ACTION, reasoning=f"策略异常: {e}")

            # Execute signal
            if signal.signal_type == SignalType.BUY and not position.is_open:
                # Buy with all available cash
                buy_price = bar_close * (1 + self.config.slippage)
                max_qty = int(cash / (buy_price * (1 + self.config.commission_rate)))
                # A-share: round to 100
                max_qty = (max_qty // 100) * 100
                if max_qty > 0:
                    gross = max_qty * buy_price
                    commission = max(gross * self.config.commission_rate, self.config.min_commission)
                    cash -= (gross + commission)
                    position.quantity = max_qty
                    position.avg_cost = buy_price
                    position.entry_date = bar_date
                    trade = BacktestTrade(
                        code=code, side="buy", quantity=max_qty,
                        price=buy_price, commission=commission,
                        timestamp=bar_date, signal_reason=signal.reasoning,
                    )
                    result.trades.append(trade)

            elif signal.signal_type == SignalType.SELL and position.is_open:
                # Sell all
                sell_price = bar_close * (1 - self.config.slippage)
                gross = position.quantity * sell_price
                commission = max(gross * self.config.commission_rate, self.config.min_commission)
                stamp_duty = gross * self.config.stamp_duty_rate
                net = gross - commission - stamp_duty
                realized_pnl = (sell_price - position.avg_cost) * position.quantity - commission - stamp_duty
                cash += net

                trade = BacktestTrade(
                    code=code, side="sell", quantity=position.quantity,
                    price=sell_price, commission=commission + stamp_duty,
                    timestamp=bar_date, signal_reason=signal.reasoning,
                    pnl=realized_pnl,
                )
                result.trades.append(trade)

                if realized_pnl > 0:
                    result.winning_trades += 1
                else:
                    result.losing_trades += 1

                position = BacktestPosition(code=code)

            # Record equity
            equity = cash + position.quantity * bar_close
            equity_curve.append({
                "date": str(bar_date) if bar_date else "",
                "cash": round(cash, 2),
                "position_value": round(position.quantity * bar_close, 2),
                "equity": round(equity, 2),
            })

        # Close position at last bar
        if position.is_open and bars:
            last_close = bars[-1].close if hasattr(bars[-1], 'close') and bars[-1].close else 0.0
            if last_close > 0:
                gross = position.quantity * last_close
                commission = max(gross * self.config.commission_rate, self.config.min_commission)
                stamp_duty = gross * self.config.stamp_duty_rate
                cash += gross - commission - stamp_duty
                realized_pnl = (last_close - position.avg_cost) * position.quantity - commission - stamp_duty
                if realized_pnl > 0:
                    result.winning_trades += 1
                else:
                    result.losing_trades += 1

        # Calculate metrics
        result.final_value = cash
        result.total_return_pct = ((cash - self.config.initial_capital) / self.config.initial_capital * 100) if self.config.initial_capital > 0 else 0.0
        result.total_trades = len([t for t in result.trades if t.side == "sell"])
        result.equity_curve = equity_curve
        result.signals = all_signals

        # Max drawdown
        if equity_curve:
            peak = equity_curve[0]["equity"]
            max_dd = 0.0
            for point in equity_curve:
                eq = point["equity"]
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak * 100 if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
            result.max_drawdown_pct = round(max_dd, 2)

        # Simple Sharpe (daily returns)
        if len(equity_curve) > 2:
            returns = []
            for i in range(1, len(equity_curve)):
                prev = equity_curve[i-1]["equity"]
                curr = equity_curve[i]["equity"]
                if prev > 0:
                    returns.append((curr - prev) / prev)
            if returns:
                avg_ret = sum(returns) / len(returns)
                variance = sum((r - avg_ret) ** 2 for r in returns) / len(returns)
                std = math.sqrt(variance) if variance > 0 else 0
                # Annualized Sharpe (252 trading days, risk-free = 0)
                result.sharpe_ratio = round((avg_ret / std) * math.sqrt(252), 4) if std > 0 else None

        return result
