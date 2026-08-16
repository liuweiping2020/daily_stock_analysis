# -*- coding: utf-8 -*-
"""
===================================
数据源健康监控接口
===================================

职责：
1. 暴露 DataSourceHealthTracker 的健康摘要与熔断状态
2. 提供重置入口用于排障与回归验证
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from data_provider.health import get_health_tracker

router = APIRouter()


@router.get("/status", summary="获取数据源健康状态")
def get_data_source_health():
    """返回各数据源的成功率、延迟、熔断状态等健康摘要。"""
    tracker = get_health_tracker()
    return {"fetchers": tracker.get_health_summary()}


@router.post("/reset", summary="重置数据源健康状态")
def reset_data_source_health(fetcher: Optional[str] = None):
    """重置指定或全部数据源的健康统计与熔断状态。

    Args:
        fetcher: 指定 fetcher 名称；不传则重置全部。
    """
    tracker = get_health_tracker()
    tracker.reset(fetcher)
    return {"message": "health data reset", "fetcher": fetcher or "all"}
