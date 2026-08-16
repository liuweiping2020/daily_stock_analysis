# -*- coding: utf-8 -*-
"""Experience review endpoints — decision snapshots, records, and prompt injection."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.deps import get_database_manager
from api.v1.schemas.common import ErrorResponse
from src.services.experience_review_service import ExperienceReviewService
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------
# Request / response schemas (route-local to keep the contract visible)
# ---------------------------------------------------------------------
class SnapshotCreateRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    decision_date: date = Field(..., description="决策日期（T 日）")
    action: str = Field(..., description="BUY/HOLD/SELL")
    conviction: Optional[float] = Field(None, ge=0.0, le=1.0, description="信心度 0.0-1.0")
    target_price: Optional[float] = Field(None, description="目标价")
    stop_loss: Optional[float] = Field(None, description="止损价")
    take_profit: Optional[float] = Field(None, description="止盈价")
    reasoning: Optional[str] = Field(None, description="决策理由")
    analyst_reports: Optional[Dict[str, Any]] = Field(None, description="各 agent 报告（role -> report）")
    debate_summary: Optional[str] = Field(None, description="多空辩论摘要")
    analysis_history_id: Optional[int] = Field(None, description="关联分析历史 id")


class SnapshotCreateResponse(BaseModel):
    id: int
    code: str
    decision_date: date
    action: str
    status: str = "pending"


class ExperienceRecordItem(BaseModel):
    id: int
    decision_snapshot_id: int
    code: str
    ret_5d: Optional[float] = None
    ret_20d: Optional[float] = None
    ret_60d: Optional[float] = None
    label: Optional[str] = None
    root_cause: Optional[str] = None
    lessons: List[Any] = Field(default_factory=list)
    tags: List[Any] = Field(default_factory=list)
    confidence: Optional[float] = None
    reviewed_at: Optional[str] = None


class ExperienceRecordsResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[ExperienceRecordItem] = Field(default_factory=list)


class ExperienceReviewResponse(BaseModel):
    processed: int
    completed: int
    insufficient: int
    errors: int


class ExperienceForPromptResponse(BaseModel):
    code: str
    prompt_text: str
    records_used: int


# ---------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------
@router.post(
    "/snapshots",
    response_model=SnapshotCreateResponse,
    responses={
        400: {"description": "参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="创建决策快照",
    description="保存一次 T 日决策快照，供后续经验复盘",
)
def create_snapshot(
    request: SnapshotCreateRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> SnapshotCreateResponse:
    try:
        service = ExperienceReviewService(db_manager)
        snapshot = service.create_snapshot(
            code=request.code,
            decision_date=request.decision_date,
            action=request.action,
            conviction=request.conviction,
            target_price=request.target_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            reasoning=request.reasoning,
            analyst_reports=request.analyst_reports,
            debate_summary=request.debate_summary,
            analysis_history_id=request.analysis_history_id,
        )
        return SnapshotCreateResponse(
            id=snapshot.id,
            code=snapshot.code,
            decision_date=snapshot.decision_date,
            action=snapshot.action,
            status=snapshot.status,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except Exception as exc:
        logger.error(f"创建决策快照失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"创建决策快照失败: {str(exc)}"},
        )


@router.get(
    "/records",
    response_model=ExperienceRecordsResponse,
    responses={
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取经验记录",
    description="分页获取经验复盘记录，支持按股票代码过滤",
)
def list_experience_records(
    code: Optional[str] = Query(None, description="股票代码筛选"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=200, description="每页数量"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> ExperienceRecordsResponse:
    try:
        service = ExperienceReviewService(db_manager)
        # Fetch one page's worth of records; the service returns the most
        # recent first, so we apply simple offset/limit pagination here.
        page_limit = limit
        offset = (page - 1) * page_limit
        all_records = service.get_recent_experiences(
            code=code,
            limit=offset + page_limit,
        )
        page_items = all_records[offset:offset + page_limit]
        items = [ExperienceRecordItem(**item) for item in page_items]
        # total is bounded by the fetched window; precise total count
        # would require a dedicated count query, which the service does
        # not expose to keep the read path lightweight.
        total = len(all_records)
        return ExperienceRecordsResponse(
            total=total,
            page=page,
            limit=limit,
            items=items,
        )
    except Exception as exc:
        logger.error(f"查询经验记录失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询经验记录失败: {str(exc)}"},
        )


@router.post(
    "/review",
    response_model=ExperienceReviewResponse,
    responses={
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="触发经验复盘",
    description="扫描已到期的待复盘快照，回填 5/20/60 日实际收益并归因",
)
def run_experience_review(
    eval_days: Optional[int] = Query(None, ge=1, le=365, description="最小天龄（自然日）"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> ExperienceReviewResponse:
    try:
        service = ExperienceReviewService(db_manager)
        stats = service.run_review(eval_days=eval_days)
        return ExperienceReviewResponse(**stats)
    except Exception as exc:
        logger.error(f"经验复盘执行失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"经验复盘执行失败: {str(exc)}"},
        )


@router.get(
    "/for-prompt",
    response_model=ExperienceForPromptResponse,
    responses={
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取注入 Prompt 的经验文本",
    description="按股票代码返回近期经验复盘的可注入文本",
)
def get_experiences_for_prompt(
    code: str = Query(..., description="股票代码"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> ExperienceForPromptResponse:
    try:
        service = ExperienceReviewService(db_manager)
        text = service.get_experiences_for_prompt(code)
        records_used = len(service.get_recent_experiences(code=code, limit=10))
        return ExperienceForPromptResponse(
            code=code,
            prompt_text=text,
            records_used=records_used,
        )
    except Exception as exc:
        logger.error(f"获取经验 Prompt 失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"获取经验 Prompt 失败: {str(exc)}"},
        )
