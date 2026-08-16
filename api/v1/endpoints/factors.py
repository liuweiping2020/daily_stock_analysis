# -*- coding: utf-8 -*-
"""Factor computation and query endpoints."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.services.factor_service import FactorService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/list", summary="列出可用因子")
def list_factors_api():
    service = FactorService()
    return service.list_available_factors()


@router.post("/compute/{code}", summary="计算并保存因子值")
def compute_factors(code: str, days: int = Query(default=60, ge=10, le=365)):
    service = FactorService()
    saved = service.compute_and_save(code, days=days)
    return {"code": code, "saved": saved}


@router.get("/values/{code}", summary="查询因子值")
def get_factor_values(
    code: str,
    factor_names: Optional[str] = Query(default=None, description="逗号分隔的因子名"),
    days: int = Query(default=30, ge=1, le=365),
):
    service = FactorService()
    names = factor_names.split(",") if factor_names else None
    values = service.get_factors(code, factor_names=names, days=days)
    return {"code": code, "count": len(values), "items": values}


@router.get("/latest/{code}", summary="获取最新因子值")
def get_latest_factors(code: str):
    service = FactorService()
    factors = service.get_latest_factors(code)
    if not factors:
        raise HTTPException(status_code=404, detail=f"未找到 {code} 的因子数据，请先计算")
    return {"code": code, "factors": factors}
