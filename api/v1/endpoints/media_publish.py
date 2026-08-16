# -*- coding: utf-8 -*-
"""多媒体发布：平台管理 + 任务调度 + 发布执行。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.media import MediaPublishService


router = APIRouter()
_service: Optional[MediaPublishService] = None


def _svc() -> MediaPublishService:
    global _service
    if _service is None:
        _service = MediaPublishService()
    return _service


# =============== Schemas =============== #

class PlatformUpsertIn(BaseModel):
    platform_code: str = Field(..., min_length=1, max_length=32)
    display_name: str = Field(..., min_length=1, max_length=128)
    account_id: Optional[str] = Field(None, max_length=128)
    credentials: Optional[Dict[str, Any]] = Field(
        None, description="按平台各字段的凭据字典；存储于本地数据库，建议部署端加密。"
    )
    extra: Optional[Dict[str, Any]] = None
    enabled: bool = True
    default_target: Optional[str] = Field(None, max_length=256)


class CreateTasksIn(BaseModel):
    source_type: str = Field(..., pattern=r"^(analysis|market_review|manual)$")
    source_ref_id: Optional[int] = None
    source_display_name: Optional[str] = Field(None, max_length=256)
    title: Optional[str] = Field(None, max_length=512)
    content_markdown: Optional[str] = None
    content_html: Optional[str] = None
    summary: Optional[str] = None
    cover_url: Optional[str] = Field(None, max_length=512)
    tags: Optional[List[str]] = Field(default_factory=list)
    original_author: Optional[str] = Field(None, max_length=128)
    platform_ids: Optional[List[int]] = None
    platform_codes: Optional[List[str]] = None
    schedule_at: Optional[datetime] = None
    max_retries: int = 2


class EnabledPatchIn(BaseModel):
    enabled: bool


# =============== Platforms =============== #

@router.get("/platforms/specs", tags=["MediaPublish"],
            summary="列出所有支持的平台规格")
def list_platform_specs() -> List[Dict[str, Any]]:
    return _svc().list_supported_platform_specs()


@router.get("/platforms", tags=["MediaPublish"],
            summary="列出已注册平台")
def list_platforms(only_enabled: bool = Query(False)) -> List[Dict[str, Any]]:
    return _svc().list_platforms(only_enabled=only_enabled)


@router.get("/platforms/{platform_id}", tags=["MediaPublish"],
            summary="查询单个平台")
def get_platform(platform_id: int) -> Dict[str, Any]:
    data = _svc().get_platform(platform_id)
    if not data:
        raise HTTPException(status_code=404, detail="platform not found")
    return data


@router.post("/platforms", tags=["MediaPublish"],
             summary="注册或更新平台（按 platform_code + account_id 去重）")
def upsert_platform(body: PlatformUpsertIn) -> Dict[str, Any]:
    try:
        return _svc().upsert_platform(**body.dict())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/platforms/{platform_id}/enabled", tags=["MediaPublish"],
              summary="启用/禁用平台")
def patch_platform_enabled(platform_id: int, body: EnabledPatchIn) -> Dict[str, Any]:
    ok = _svc().set_platform_enabled(platform_id, body.enabled)
    if not ok:
        raise HTTPException(status_code=404, detail="platform not found")
    return {"ok": True}


@router.delete("/platforms/{platform_id}", tags=["MediaPublish"],
               summary="删除平台注册")
def delete_platform(platform_id: int) -> Dict[str, Any]:
    ok = _svc().delete_platform(platform_id)
    if not ok:
        raise HTTPException(status_code=404, detail="platform not found")
    return {"ok": True}


# =============== Tasks =============== #

@router.post("/tasks", tags=["MediaPublish"],
             summary="创建发布任务（可一次指定多个目标平台）")
def create_tasks(body: CreateTasksIn) -> List[Dict[str, Any]]:
    try:
        return _svc().create_tasks(**body.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks", tags=["MediaPublish"],
            summary="查询发布任务列表")
def list_tasks(source_type: Optional[str] = Query(None),
               source_ref_id: Optional[int] = Query(None),
               platform_code: Optional[str] = Query(None),
               status: Optional[str] = Query(None),
               limit: int = Query(50, ge=1, le=500),
               offset: int = Query(0, ge=0)) -> List[Dict[str, Any]]:
    return _svc().list_tasks(
        source_type=source_type,
        source_ref_id=source_ref_id,
        platform_code=platform_code,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/tasks/{task_id}", tags=["MediaPublish"],
            summary="查询单条发布任务详情")
def get_task(task_id: int) -> Dict[str, Any]:
    t = _svc().get_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="task not found")
    return t


@router.post("/tasks/{task_id}/run", tags=["MediaPublish"],
             summary="立即执行单条发布任务")
def run_task(task_id: int, force: bool = False) -> Dict[str, Any]:
    try:
        return _svc().run_task(task_id, force=force)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/run-batch", tags=["MediaPublish"],
             summary="批量执行到期/待处理任务（用于调度器/定时触发）")
def run_batch(limit: int = Query(20, ge=1, le=200),
              include_scheduled: bool = True) -> Dict[str, Any]:
    return _svc().run_batch(limit=limit, include_scheduled=include_scheduled)


@router.post("/tasks/{task_id}/retry", tags=["MediaPublish"],
             summary="重试失败任务")
def retry_task(task_id: int) -> Dict[str, Any]:
    try:
        return _svc().retry_task(task_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/tasks/{task_id}/cancel", tags=["MediaPublish"],
             summary="取消尚未执行的任务")
def cancel_task(task_id: int) -> Dict[str, Any]:
    try:
        return _svc().cancel_task(task_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============== One-shot "Export for Clipboard" 快捷接口 =============== #

class ExportNowIn(BaseModel):
    title: str = Field(..., max_length=512)
    content_markdown: Optional[str] = None
    content_html: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    cover_url: Optional[str] = None
    original_author: Optional[str] = None
    reference_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    target_platform_codes: List[str] = Field(
        default_factory=lambda: ["clipboard_export"],
        description="目标平台编码列表；默认仅通用导出。若指定已启用的 wechat_mp/zhihu 等，将同步创建任务。",
    )


@router.post("/export/now", tags=["MediaPublish"],
             summary="立即导出（默认通用剪贴板），可选同步创建多平台发布任务")
def export_now(body: ExportNowIn) -> Dict[str, Any]:
    from src.media.adapters import build_adapter, PublishPayload, MediaAdapterError

    # 1. 生成通用导出（必然成功）
    export_adapter = build_adapter(platform_code="clipboard_export")
    payload = PublishPayload(
        title=body.title,
        markdown=body.content_markdown or "",
        html=body.content_html or "",
        summary=body.summary,
        tags=list(body.tags),
        cover_url=body.cover_url,
        original_author=body.original_author,
        reference_date=body.reference_date,
    )
    export_result = export_adapter.publish(payload)

    # 2. 如目标平台除 clipboard 外还有其它 → 创建对应任务
    created = []
    extra_targets = [c for c in body.target_platform_codes if c != "clipboard_export"]
    if extra_targets:
        try:
            created = _svc().create_tasks(
                source_type="manual",
                source_display_name="即时导出",
                title=body.title,
                content_markdown=body.content_markdown,
                content_html=body.content_html,
                summary=body.summary,
                cover_url=body.cover_url,
                tags=list(body.tags),
                original_author=body.original_author,
                platform_codes=extra_targets,
            )
        except Exception as e:  # noqa: BLE001
            export_result.extra.setdefault("task_creation_error", str(e))

    return {
        "export": {
            "ok": export_result.ok,
            "article_id": export_result.article_id,
            "extra": export_result.extra,
        },
        "tasks_created": created,
    }
