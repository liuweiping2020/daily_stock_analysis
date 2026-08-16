# -*- coding: utf-8 -*-
"""多媒体多平台发布服务。

主职责：
1. 平台注册/更新/启用状态
2. 内容来源映射：analysis_history / market_review / 手工文本
3. 任务拆分：一次提交 N 个目标平台 → N 条 MediaPublishTask
4. 立即执行 / 计划执行 / 失败重试
5. 与适配器解耦：仅通过 adapters.build_adapter 拿到具体平台
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.media.adapters import (
    BaseMediaAdapter,
    PublishPayload,
    PublishResult,
    MediaAdapterError,
    build_adapter,
    list_supported_platforms,
)
from src.storage import DatabaseManager, MediaPlatform, MediaPublishTask, AnalysisHistory


logger = logging.getLogger(__name__)


class MediaPublishService:
    """多媒体多平台发布服务。"""

    VALID_STATUSES = {
        "pending", "queued", "running", "published",
        "failed", "retried", "cancelled",
    }

    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        self._db = db or DatabaseManager.get_instance()

    # ============== 平台管理 ============== #

    def list_platforms(self, *, only_enabled: bool = False) -> List[Dict[str, Any]]:
        """数据库里已注册的平台。"""
        with self._db.get_session() as sess:
            q = sess.query(MediaPlatform)
            if only_enabled:
                q = q.filter(MediaPlatform.enabled.is_(True))
            rows = q.order_by(MediaPlatform.id.asc()).all()
            return [self._platform_to_dict(r) for r in rows]

    def list_supported_platform_specs(self) -> List[Dict[str, Any]]:
        """所有代码内支持的平台规格。"""
        return list_supported_platforms()

    def get_platform(self, platform_id: int) -> Optional[Dict[str, Any]]:
        with self._db.get_session() as sess:
            p = sess.get(MediaPlatform, platform_id)
            return self._platform_to_dict(p) if p else None

    def upsert_platform(self, *, platform_code: str, display_name: str,
                        account_id: Optional[str] = None,
                        credentials: Optional[Dict[str, Any]] = None,
                        extra: Optional[Dict[str, Any]] = None,
                        enabled: bool = True,
                        default_target: Optional[str] = None,
                        ) -> Dict[str, Any]:
        """创建或更新（按 platform_code + account_id 去重）平台凭据。"""
        creds_json = json.dumps(credentials, ensure_ascii=False) if credentials is not None else None
        extra_json = json.dumps(extra, ensure_ascii=False) if extra is not None else None
        with self._db.get_session() as sess:
            p = (
                sess.query(MediaPlatform)
                .filter(
                    MediaPlatform.platform_code == platform_code,
                    (MediaPlatform.account_id == account_id)
                    if account_id is not None
                    else (MediaPlatform.account_id.is_(None)),
                )
                .one_or_none()
            )
            if p is None:
                p = MediaPlatform(
                    platform_code=platform_code,
                    display_name=display_name,
                    account_id=account_id,
                    credentials_json=creds_json,
                    enabled=enabled,
                    default_target=default_target,
                    extra_json=extra_json,
                )
                sess.add(p)
            else:
                p.display_name = display_name
                p.enabled = enabled
                if default_target is not None:
                    p.default_target = default_target
                if creds_json is not None:
                    p.credentials_json = creds_json
                if extra_json is not None:
                    p.extra_json = extra_json
                p.updated_at = datetime.now()
            sess.commit()
            return self._platform_to_dict(p)

    def set_platform_enabled(self, platform_id: int, enabled: bool) -> bool:
        with self._db.get_session() as sess:
            p = sess.get(MediaPlatform, platform_id)
            if not p:
                return False
            p.enabled = bool(enabled)
            p.updated_at = datetime.now()
            sess.commit()
            return True

    def delete_platform(self, platform_id: int) -> bool:
        with self._db.get_session() as sess:
            p = sess.get(MediaPlatform, platform_id)
            if not p:
                return False
            # 删除前：保留任务，仅把任务的 platform_id 置 NULL（通过先删任务关联可能不存在），
            # 这里直接删平台，保留任务记录（设置为 platform_code 字符串匹配失败即可）
            sess.query(MediaPublishTask).filter(
                MediaPublishTask.platform_id == platform_id
            ).update({MediaPublishTask.platform_code: MediaPublishTask.platform_code})
            sess.delete(p)
            sess.commit()
            return True

    # ============== 任务创建 ============== #

    def create_tasks(self, *,
                     source_type: str,
                     source_ref_id: Optional[int] = None,
                     source_display_name: Optional[str] = None,
                     title: Optional[str] = None,
                     content_markdown: Optional[str] = None,
                     content_html: Optional[str] = None,
                     summary: Optional[str] = None,
                     cover_url: Optional[str] = None,
                     tags: Optional[List[str]] = None,
                     original_author: Optional[str] = None,
                     platform_ids: Optional[List[int]] = None,
                     platform_codes: Optional[List[str]] = None,
                     schedule_at: Optional[datetime] = None,
                     max_retries: int = 2,
                     ) -> List[Dict[str, Any]]:
        """创建发布任务。

        - ``source_type`` 为 ``analysis`` 时：若不传 title/markdown/html，
          会从 ``AnalysisHistory`` 里回填报告内容。
        - ``platform_ids`` 与 ``platform_codes`` 至少传其一；两者都传时取并集。
        """
        platforms: List[MediaPlatform] = self._resolve_platforms(
            platform_ids=platform_ids, platform_codes=platform_codes,
        )
        if not platforms:
            raise ValueError("未指定任何已注册且启用的目标平台")

        title_final, md, html, summary_final = self._resolve_content(
            source_type=source_type,
            source_ref_id=source_ref_id,
            title=title,
            content_markdown=content_markdown,
            content_html=content_html,
            summary=summary,
            source_display_name=source_display_name,
        )
        if not title_final:
            raise ValueError("title 为空，且无法从分析历史自动生成")

        tags_csv = ",".join(tags) if tags else None
        now = datetime.now()
        created: List[MediaPublishTask] = []
        with self._db.get_session() as sess:
            for p in platforms:
                task = MediaPublishTask(
                    source_type=source_type,
                    source_ref_id=source_ref_id,
                    source_display_name=source_display_name,
                    title=title_final,
                    content_markdown=md,
                    content_html=html,
                    cover_url=cover_url,
                    tags_csv=tags_csv,
                    original_author=original_author,
                    summary=summary_final,
                    platform_id=p.id,
                    platform_code=p.platform_code,
                    target_location=p.default_target,
                    status="pending",
                    schedule_at=schedule_at,
                    retry_count=0,
                    max_retries=max_retries,
                    created_at=now,
                    updated_at=now,
                )
                sess.add(task)
                created.append(task)
            sess.commit()
            return [self._task_to_dict(t) for t in created]

    # ============== 任务执行 ============== #

    def run_task(self, task_id: int, *, force: bool = False) -> Dict[str, Any]:
        """立即执行单条任务。"""
        with self._db.get_session() as sess:
            task = sess.get(MediaPublishTask, task_id)
            if not task:
                raise LookupError(f"task {task_id} not found")
            if not force and task.status in {"published", "running", "cancelled"}:
                return self._task_to_dict(task)

            # 关联平台
            platform = sess.get(MediaPlatform, task.platform_id)
            if platform is None or not platform.enabled:
                task.status = "failed"
                task.error_code = "PLATFORM_DISABLED_OR_DELETED"
                task.error_message = (
                    f"平台 (id={task.platform_id}, code={task.platform_code}) "
                    "不存在或已禁用"
                )
                sess.commit()
                return self._task_to_dict(task)

            task.status = "running"
            task.execute_started_at = datetime.now()
            sess.commit()

            try:
                adapter = self._adapter_for(platform)
                payload = self._payload_from_task(task)
                result: PublishResult = adapter.publish(payload)
            except MediaAdapterError as e:
                result = PublishResult(
                    ok=False,
                    error_code=e.code,
                    error_message=e.message,
                    extra={"raw": str(e.raw)[:5000]} if e.raw is not None else {},
                )
            except Exception as e:  # noqa: BLE001
                logger.exception("执行发布任务 task_id=%s 未预期异常", task_id)
                result = PublishResult(
                    ok=False,
                    error_code="UNEXPECTED",
                    error_message=f"{type(e).__name__}: {e}",
                )

            task.executed_at = datetime.now()
            if result.ok:
                task.status = "published"
                task.remote_article_id = result.article_id
                task.remote_url = result.url
                task.remote_extra_json = (
                    json.dumps(result.extra, ensure_ascii=False)
                    if result.extra else None
                )
                task.error_code = None
                task.error_message = None
            else:
                task.status = "failed"
                task.error_code = result.error_code or "FAILED"
                task.error_message = (result.error_message or "")[:4000]
                if result.extra:
                    task.remote_extra_json = json.dumps(result.extra, ensure_ascii=False)
                # 如还可重试，状态置为 retried（用户可通过 retry API 或调度器触发下次）
                if task.retry_count < (task.max_retries or 0):
                    task.status = "retried"
            sess.commit()
            return self._task_to_dict(task)

    def run_batch(self, *, limit: int = 20, include_scheduled: bool = True) -> Dict[str, Any]:
        """批量执行到期/待执行任务。返回执行摘要。"""
        now = datetime.now()
        with self._db.get_session() as sess:
            q = sess.query(MediaPublishTask).filter(
                MediaPublishTask.status.in_(["pending", "retried"])
            )
            if include_scheduled:
                q = q.filter(
                    (MediaPublishTask.schedule_at.is_(None))
                    | (MediaPublishTask.schedule_at <= now)
                )
            else:
                q = q.filter(MediaPublishTask.schedule_at.is_(None))
            tasks = q.order_by(MediaPublishTask.id.asc()).limit(limit).all()
            ids = [t.id for t in tasks]

        success = failed = 0
        results: List[Dict[str, Any]] = []
        for tid in ids:
            d = self.run_task(tid, force=False)
            if d["status"] == "published":
                success += 1
            else:
                failed += 1
            results.append({"id": tid, "status": d["status"],
                            "error_code": d.get("error_code")})
        return {
            "total": len(ids),
            "published": success,
            "failed": failed,
            "items": results,
        }

    def retry_task(self, task_id: int, *, reset_status: bool = True) -> Dict[str, Any]:
        with self._db.get_session() as sess:
            task = sess.get(MediaPublishTask, task_id)
            if not task:
                raise LookupError(f"task {task_id} not found")
            task.retry_count = (task.retry_count or 0) + 1
            task.status = "pending" if reset_status else task.status
            if reset_status:
                task.error_code = None
                task.error_message = None
                task.remote_article_id = None
                task.remote_url = None
                task.execute_started_at = None
                task.executed_at = None
            task.updated_at = datetime.now()
            sess.commit()
            return self._task_to_dict(task)

    def cancel_task(self, task_id: int) -> Dict[str, Any]:
        with self._db.get_session() as sess:
            task = sess.get(MediaPublishTask, task_id)
            if not task:
                raise LookupError(f"task {task_id} not found")
            if task.status in {"running", "published"}:
                raise ValueError(f"task {task_id} status={task.status}，不可取消")
            task.status = "cancelled"
            task.updated_at = datetime.now()
            sess.commit()
            return self._task_to_dict(task)

    def list_tasks(self, *, source_type: Optional[str] = None,
                   source_ref_id: Optional[int] = None,
                   platform_code: Optional[str] = None,
                   status: Optional[str] = None,
                   limit: int = 50,
                   offset: int = 0,
                   ) -> List[Dict[str, Any]]:
        with self._db.get_session() as sess:
            q = sess.query(MediaPublishTask)
            if source_type:
                q = q.filter(MediaPublishTask.source_type == source_type)
            if source_ref_id is not None:
                q = q.filter(MediaPublishTask.source_ref_id == source_ref_id)
            if platform_code:
                q = q.filter(MediaPublishTask.platform_code == platform_code)
            if status:
                q = q.filter(MediaPublishTask.status == status)
            rows = (
                q.order_by(MediaPublishTask.id.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [self._task_to_dict(r) for r in rows]

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        with self._db.get_session() as sess:
            t = sess.get(MediaPublishTask, task_id)
            return self._task_to_dict(t) if t else None

    # ============== 内部 ============== #

    def _resolve_platforms(self, *,
                           platform_ids: Optional[Iterable[int]],
                           platform_codes: Optional[Iterable[str]],
                           ) -> List[MediaPlatform]:
        with self._db.get_session() as sess:
            results: Dict[int, MediaPlatform] = {}
            if platform_ids:
                for p in (
                    sess.query(MediaPlatform)
                    .filter(MediaPlatform.id.in_(list(platform_ids)))
                    .filter(MediaPlatform.enabled.is_(True))
                    .all()
                ):
                    results[p.id] = p
            if platform_codes:
                for p in (
                    sess.query(MediaPlatform)
                    .filter(MediaPlatform.platform_code.in_(list(platform_codes)))
                    .filter(MediaPlatform.enabled.is_(True))
                    .all()
                ):
                    results[p.id] = p
            return list(results.values())

    def _resolve_content(self, *,
                         source_type: str,
                         source_ref_id: Optional[int],
                         title: Optional[str],
                         content_markdown: Optional[str],
                         content_html: Optional[str],
                         summary: Optional[str],
                         source_display_name: Optional[str],
                         ) -> Tuple[str, str, str, str]:
        """当分析来源未提供 content 时，从 AnalysisHistory 回填报告。"""
        md = content_markdown or ""
        html = content_html or ""
        summ = summary or ""
        if title:
            return title, md, html, summ
        if source_type == "analysis" and source_ref_id:
            with self._db.get_session() as sess:
                h = sess.get(AnalysisHistory, source_ref_id)
                if h:
                    code = h.code or ""
                    qdate = (h.query_date.strftime("%Y-%m-%d")
                             if hasattr(h, "query_date") and h.query_date else "")
                    auto_title = f"{code} {qdate} 智能分析报告".strip()
                    # 分析报告正文存储位置
                    report_text = (
                        getattr(h, "report_content", None)
                        or getattr(h, "report", None)
                        or ""
                    )
                    if report_text and not md:
                        md = str(report_text)
                    source_display_name = source_display_name or f"{code} {qdate}"
                    if not summ and md:
                        summ = md[:180].strip()
                    return auto_title, md, html, summ
        if source_type == "market_review":
            return ("大盘复盘报告 " + (source_display_name or datetime.now().strftime("%Y-%m-%d")),
                    md, html, summ)
        return ("未命名发布内容", md, html, summ)

    @staticmethod
    def _adapter_for(platform: MediaPlatform) -> BaseMediaAdapter:
        credentials = (
            json.loads(platform.credentials_json)
            if platform.credentials_json else None
        )
        extra = json.loads(platform.extra_json) if platform.extra_json else None
        return build_adapter(
            platform_code=platform.platform_code,
            credentials=credentials,
            extra=extra,
        )

    @staticmethod
    def _payload_from_task(task: MediaPublishTask) -> PublishPayload:
        tags = [t for t in (task.tags_csv or "").split(",") if t]
        ref_date = None
        if task.created_at:
            ref_date = task.created_at.strftime("%Y-%m-%d")
        return PublishPayload(
            title=task.title,
            markdown=task.content_markdown or "",
            html=task.content_html or "",
            summary=task.summary,
            tags=tags,
            cover_url=task.cover_url,
            original_author=task.original_author,
            reference_date=ref_date,
            platform_options={"target_location": task.target_location},
        )

    @staticmethod
    def _platform_to_dict(p: MediaPlatform) -> Dict[str, Any]:
        credentials: Optional[Dict[str, Any]] = None
        if p.credentials_json:
            try:
                credentials = json.loads(p.credentials_json)
                # 不在返回里暴露真正的密钥值，仅返回 key 列表
                credentials = {k: "***" for k in credentials.keys()}
            except Exception:
                credentials = None
        extra: Optional[Dict[str, Any]] = None
        if p.extra_json:
            try:
                extra = json.loads(p.extra_json)
            except Exception:
                extra = None
        return {
            "id": p.id,
            "platform_code": p.platform_code,
            "display_name": p.display_name,
            "account_id": p.account_id,
            "credentials_key_hints": credentials if credentials else [],
            "enabled": p.enabled,
            "default_target": p.default_target,
            "extra": extra,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }

    @staticmethod
    def _task_to_dict(t: MediaPublishTask) -> Dict[str, Any]:
        extra = None
        if t.remote_extra_json:
            try:
                extra = json.loads(t.remote_extra_json)
            except Exception:
                extra = t.remote_extra_json[:1000]
        return {
            "id": t.id,
            "source_type": t.source_type,
            "source_ref_id": t.source_ref_id,
            "source_display_name": t.source_display_name,
            "title": t.title,
            "summary": (t.summary or "")[:300],
            "platform_id": t.platform_id,
            "platform_code": t.platform_code,
            "target_location": t.target_location,
            "status": t.status,
            "schedule_at": t.schedule_at.isoformat() if t.schedule_at else None,
            "execute_started_at": t.execute_started_at.isoformat() if t.execute_started_at else None,
            "executed_at": t.executed_at.isoformat() if t.executed_at else None,
            "retry_count": t.retry_count,
            "max_retries": t.max_retries,
            "remote_article_id": t.remote_article_id,
            "remote_url": t.remote_url,
            "error_code": t.error_code,
            "error_message": (t.error_message or "")[:300],
            "tags": [x for x in (t.tags_csv or "").split(",") if x],
            "extra": extra,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
