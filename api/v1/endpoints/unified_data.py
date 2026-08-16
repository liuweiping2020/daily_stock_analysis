# -*- coding: utf-8 -*-
"""
===================================
统一数据接口（市场无关）
===================================

职责：
1. 暴露 UnifiedDataAPI 的统一数据访问能力
2. 提供 cn/hk/us 通用的日线、行情、基本面、搜索与综合摘要接口
3. 自动检测市场，屏蔽底层多数据源选择逻辑
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from data_provider.unified_api import detect_market, get_unified_api

router = APIRouter()
logger = logging.getLogger(__name__)


class DailyBarResponse(BaseModel):
    date: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    change_pct: Optional[float] = None
    turnover: Optional[float] = None


class StockSearchItem(BaseModel):
    code: str = ""
    name: str = ""
    market: str = ""
    exchange: Optional[str] = None


@router.get(
    "/bars/{code}",
    response_model=List[DailyBarResponse],
    summary="获取日线数据",
    description="市场无关的日 OHLCV 数据，自动识别 cn/hk/us；可通过 market 强制指定。",
)
def get_bars(
    code: str,
    days: int = Query(default=30, ge=1, le=365, description="返回最近 N 个交易日"),
    market: Optional[str] = Query(default=None, description="强制指定市场 cn/hk/us"),
):
    api = get_unified_api()
    bars = api.get_daily_bars(code, days=days, market=market)
    return [DailyBarResponse(**asdict(bar)) for bar in bars]


@router.get("/quote/{code}", summary="获取实时行情")
def get_quote(code: str, market: Optional[str] = Query(default=None, description="强制指定市场 cn/hk/us")):
    api = get_unified_api()
    quote = api.get_realtime_quote(code, market=market)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"未找到 {code} 的行情数据")
    return asdict(quote)


@router.get("/fundamentals/{code}", summary="获取基本面数据")
def get_fundamentals(code: str, market: Optional[str] = Query(default=None, description="强制指定市场 cn/hk/us")):
    api = get_unified_api()
    fund = api.get_fundamentals(code, market=market)
    if fund is None:
        raise HTTPException(status_code=404, detail=f"未找到 {code} 的基本面数据")
    return asdict(fund)


@router.get(
    "/search",
    response_model=List[StockSearchItem],
    summary="搜索股票",
    description="按代码或名称关键词跨市场搜索，结果取自本地股票名称索引。",
)
def search_stocks(
    q: str = Query(..., description="股票代码或名称关键词"),
    limit: int = Query(default=10, ge=1, le=50, description="返回条数上限"),
):
    api = get_unified_api()
    results = api.search_stocks(q, limit=limit)
    return [StockSearchItem(**asdict(r)) for r in results]


@router.get("/summary/{code}", summary="获取综合数据摘要")
def get_summary(code: str, days: int = Query(default=30, ge=1, le=365, description="摘要包含的日线天数")):
    api = get_unified_api()
    return api.get_market_summary(code, days=days)


@router.get("/detect-market/{code}", summary="自动检测市场")
def get_market_detection(code: str):
    return {"code": code, "market": detect_market(code)}
