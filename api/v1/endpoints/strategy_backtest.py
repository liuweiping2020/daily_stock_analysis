# -*- coding: utf-8 -*-
"""Strategy-based backtest endpoints."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.core.event_backtest import EventBacktestConfig, EventBacktestEngine
from src.core.strategy import get_strategy, list_strategies
from api.deps import get_database_manager

router = APIRouter()
logger = logging.getLogger(__name__)


class StrategyBacktestRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    strategy_name: str = Field(..., description="策略名称")
    strategy_params: dict = Field(default_factory=dict, description="策略参数")
    initial_capital: float = Field(default=100000.0, description="初始资金")
    days: int = Field(default=90, description="回测天数")


class StrategyInfo(BaseModel):
    name: str
    description: str


@router.get("/strategies", response_model=List[StrategyInfo], summary="列出可用策略")
def get_strategies():
    return list_strategies()


@router.post("/run", summary="运行策略回测")
def run_strategy_backtest(req: StrategyBacktestRequest):
    try:
        strategy = get_strategy(req.strategy_name, **req.strategy_params)
        if strategy is None:
            raise HTTPException(status_code=404, detail=f"策略 '{req.strategy_name}' 不存在")

        db_manager = get_database_manager()
        # Fetch daily bars from storage
        end_date = date.today()
        start_date = end_date - timedelta(days=req.days)

        with db_manager.get_session() as session:
            from sqlalchemy import and_, select
            from src.storage import StockDaily
            rows = session.execute(
                select(StockDaily)
                .where(and_(
                    StockDaily.code == req.code,
                    StockDaily.date >= start_date,
                    StockDaily.date <= end_date,
                ))
                .order_by(StockDaily.date.asc())
            ).scalars().all()

        if not rows:
            raise HTTPException(status_code=404, detail=f"未找到股票 {req.code} 的日线数据")

        bars = rows  # StockDaily has date, high, low, close attributes

        config = EventBacktestConfig(initial_capital=req.initial_capital)
        engine = EventBacktestEngine(config=config)
        result = engine.run(strategy, bars, code=req.code)

        return {
            "code": result.code,
            "strategy_name": result.strategy_name,
            "start_date": str(result.start_date) if result.start_date else None,
            "end_date": str(result.end_date) if result.end_date else None,
            "initial_capital": result.initial_capital,
            "final_value": round(result.final_value, 2),
            "total_return_pct": round(result.total_return_pct, 2),
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "win_rate": round(result.win_rate, 4),
            "max_drawdown_pct": result.max_drawdown_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "trades": [
                {
                    "side": t.side,
                    "quantity": t.quantity,
                    "price": round(t.price, 2),
                    "commission": round(t.commission, 2),
                    "timestamp": str(t.timestamp) if t.timestamp else None,
                    "signal_reason": t.signal_reason,
                    "pnl": round(t.pnl, 2),
                }
                for t in result.trades
            ],
            "equity_curve": result.equity_curve[-30:],  # last 30 points
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"策略回测失败: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"策略回测失败: {str(exc)}")
