# -*- coding: utf-8 -*-
"""
===================================
API v1 路由聚合
===================================

职责：
1. 聚合 v1 版本的所有 endpoint 路由
2. 统一添加 /api/v1 前缀
"""

from fastapi import APIRouter

from api.v1.endpoints import alerts, analysis, auth, history, stocks, backtest, system_config, agent, usage, portfolio, experience, sim_trading, data_health, strategy_backtest, unified_data, factors, media_publish

# 创建 v1 版本主路由
router = APIRouter(prefix="/api/v1")

router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Auth"]
)

router.include_router(
    agent.router,
    prefix="/agent",
    tags=["Agent"]
)

router.include_router(
    analysis.router,
    prefix="/analysis",
    tags=["Analysis"]
)

router.include_router(
    history.router,
    prefix="/history",
    tags=["History"]
)

router.include_router(
    stocks.router,
    prefix="/stocks",
    tags=["Stocks"]
)

router.include_router(
    backtest.router,
    prefix="/backtest",
    tags=["Backtest"]
)

router.include_router(
    system_config.router,
    prefix="/system",
    tags=["SystemConfig"]
)

router.include_router(
    usage.router,
    prefix="/usage",
    tags=["Usage"]
)

router.include_router(
    portfolio.router,
    prefix="/portfolio",
    tags=["Portfolio"]
)

router.include_router(
    alerts.router,
    prefix="/alerts",
    tags=["Alerts"]
)

router.include_router(
    data_health.router,
    prefix="/data-health",
    tags=["DataHealth"]
)

router.include_router(
    experience.router,
    prefix="/experience",
    tags=["Experience"]
)

router.include_router(
    sim_trading.router,
    prefix="/sim-trading",
    tags=["SimTrading"]
)

router.include_router(
    strategy_backtest.router,
    prefix="/strategy-backtest",
    tags=["StrategyBacktest"]
)

router.include_router(
    factors.router,
    prefix="/factors",
    tags=["Factors"]
)

router.include_router(
    unified_data.router,
    prefix="/data",
    tags=["UnifiedData"]
)

router.include_router(
    media_publish.router,
    prefix="/media",
    tags=["MediaPublish"]
)
