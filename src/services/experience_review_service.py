# -*- coding: utf-8 -*-
"""Experience review service — backtests AI decisions against reality.

Persists T-day decision snapshots, then — once enough trading days have
elapsed — fetches the actual 5 / 20 / 60-day returns and records an
attributed experience record.  Recent experiences can be injected back
into agent prompts so the system learns from its own history.

Follows the same ``DatabaseManager``-backed pattern as ``BacktestService``.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, select

from src.repositories.stock_repo import StockRepository
from src.storage import (
    DatabaseManager,
    DecisionSnapshot,
    ExperienceRecord,
)

logger = logging.getLogger(__name__)

# Forward-return windows (in trading days) we evaluate every snapshot on.
DEFAULT_EVAL_WINDOWS: tuple[int, ...] = (5, 20, 60)
DEFAULT_EVAL_DAYS = 60  # default minimum age before a snapshot is reviewable


class ExperienceReviewService:
    """Persist decisions, review them later, and surface lessons."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()
        self.stock_repo = StockRepository(self.db)

    # ------------------------------------------------------------------
    # Snapshot creation
    # ------------------------------------------------------------------
    def create_snapshot(
        self,
        *,
        code: str,
        decision_date: date,
        action: str,
        conviction: Optional[float] = None,
        target_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        reasoning: Optional[str] = None,
        analyst_reports: Optional[Dict[str, Any]] = None,
        debate_summary: Optional[str] = None,
        analysis_history_id: Optional[int] = None,
    ) -> DecisionSnapshot:
        """Persist a T-day decision snapshot for later review."""
        action_normalized = (action or "").strip().upper() or "HOLD"
        reports_json = (
            json.dumps(analyst_reports, ensure_ascii=False, default=str)
            if analyst_reports is not None
            else None
        )
        snapshot = DecisionSnapshot(
            analysis_history_id=analysis_history_id,
            code=code,
            decision_date=decision_date,
            action=action_normalized,
            conviction=conviction,
            target_price=target_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=reasoning,
            analyst_reports_json=reports_json,
            debate_summary=debate_summary,
            status="pending",
        )
        with self.db.session_scope() as session:
            session.add(snapshot)
            session.flush()
            session.refresh(snapshot)
            # Detach so callers can read attributes after the session closes.
            session.expunge(snapshot)
        logger.info(
            "[ExperienceReview] snapshot created: code=%s date=%s action=%s id=%s",
            code, decision_date, action_normalized, snapshot.id,
        )
        return snapshot

    # ------------------------------------------------------------------
    # Review pass: backfill actual returns + attribution
    # ------------------------------------------------------------------
    def run_review(self, eval_days: Optional[int] = None) -> Dict[str, Any]:
        """Scan pending snapshots whose eval window has elapsed and record experiences.

        Args:
            eval_days: minimum age (calendar days) a snapshot must reach before
                review. Defaults to :data:`DEFAULT_EVAL_DAYS` (60).

        Returns:
            Aggregate stats for the review pass.
        """
        if eval_days is None:
            eval_days = DEFAULT_EVAL_DAYS
        today = date.today()
        cutoff = today - timedelta(days=int(eval_days))

        with self.db.get_session() as session:
            pending = session.execute(
                select(DecisionSnapshot).where(
                    and_(
                        DecisionSnapshot.status == "pending",
                        DecisionSnapshot.decision_date <= cutoff,
                    )
                ).order_by(DecisionSnapshot.decision_date)
            ).scalars().all()
            # Detach the lightweight fields we need so we can close the
            # read session before opening write sessions per snapshot.
            pending_meta = [
                {
                    "id": s.id,
                    "code": s.code,
                    "decision_date": s.decision_date,
                    "action": s.action,
                    "conviction": s.conviction,
                    "target_price": s.target_price,
                    "stop_loss": s.stop_loss,
                    "take_profit": s.take_profit,
                    "reasoning": s.reasoning,
                    "analyst_reports_json": s.analyst_reports_json,
                    "debate_summary": s.debate_summary,
                }
                for s in pending
            ]

        processed = 0
        completed = 0
        insufficient = 0
        errors = 0

        for meta in pending_meta:
            processed += 1
            try:
                record = self._review_snapshot(meta, today=today)
                if record is None:
                    insufficient += 1
                    continue
                with self.db.session_scope() as session:
                    session.add(record)
                    session.execute(
                        DecisionSnapshot.__table__.update()
                        .where(DecisionSnapshot.id == meta["id"])
                        .values(status="reviewed")
                    )
                completed += 1
            except Exception as exc:
                errors += 1
                logger.error(
                    "[ExperienceReview] snapshot %s failed: %s",
                    meta.get("id"), exc, exc_info=True,
                )

        return {
            "processed": processed,
            "completed": completed,
            "insufficient": insufficient,
            "errors": errors,
        }

    def _review_snapshot(
        self,
        meta: Dict[str, Any],
        *,
        today: date,
    ) -> Optional[ExperienceRecord]:
        """Build a single experience record for one snapshot, or None if data missing."""
        code = meta["code"]
        decision_date = meta["decision_date"]
        snapshot_id = meta["id"]

        start_daily = self.stock_repo.get_start_daily(
            code=code, analysis_date=decision_date
        )
        if start_daily is None or start_daily.close is None:
            self._try_fill_daily_data(code=code, analysis_date=decision_date)
            start_daily = self.stock_repo.get_start_daily(
                code=code, analysis_date=decision_date
            )
        if start_daily is None or start_daily.close is None:
            return None

        start_price = float(start_daily.close)
        start_date = start_daily.date

        returns: Dict[int, Optional[float]] = {}
        for window in DEFAULT_EVAL_WINDOWS:
            returns[window] = self._compute_return(
                code=code,
                start_date=start_date,
                start_price=start_price,
                window=window,
            )

        # Need at least the shortest window to produce a meaningful record.
        if returns[DEFAULT_EVAL_WINDOWS[0]] is None:
            return None

        label = self._label_decision(
            action=meta["action"],
            conviction=meta["conviction"],
            returns=returns,
        )
        root_cause = self._attribute_root_cause(meta=meta, returns=returns)
        lessons = self._extract_lessons(meta=meta, returns=returns, label=label)
        tags = self._extract_tags(meta=meta, returns=returns)

        return ExperienceRecord(
            decision_snapshot_id=snapshot_id,
            code=code,
            ret_5d=returns.get(5),
            ret_20d=returns.get(20),
            ret_60d=returns.get(60),
            label=label,
            root_cause=root_cause,
            lessons_json=json.dumps(lessons, ensure_ascii=False, default=str),
            tags_json=json.dumps(tags, ensure_ascii=False, default=str),
            confidence=float(meta.get("conviction") or 0.5),
            reviewed_at=datetime.now(),
        )

    def _compute_return(
        self,
        *,
        code: str,
        start_date: date,
        start_price: float,
        window: int,
    ) -> Optional[float]:
        """Return the realised % return ``window`` trading days after start."""
        bars = self.stock_repo.get_forward_bars(
            code=code, analysis_date=start_date, eval_window_days=window
        )
        if len(bars) < window:
            return None
        end_bar = bars[window - 1]
        if end_bar is None or end_bar.close is None:
            return None
        end_price = float(end_bar.close)
        if start_price <= 0:
            return None
        return round((end_price - start_price) / start_price * 100.0, 4)

    # ------------------------------------------------------------------
    # Labelling + attribution helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _label_decision(
        *,
        action: str,
        conviction: Optional[float],
        returns: Dict[int, Optional[float]],
    ) -> str:
        """Classify the decision as correct / partial / wrong."""
        action = (action or "").strip().upper()
        # Use the longest available window as the primary verdict.
        ret = next(
            (returns[w] for w in reversed(sorted(returns)) if returns[w] is not None),
            None,
        )
        if ret is None:
            return "partial"
        if action == "BUY":
            if ret > 2.0:
                return "correct"
            if ret < -2.0:
                return "wrong"
        elif action == "SELL":
            if ret < -2.0:
                return "correct"
            if ret > 2.0:
                return "wrong"
        elif action == "HOLD":
            # Hold is "correct" when the move is small in either direction.
            if -3.0 <= ret <= 3.0:
                return "correct"
            return "partial"
        return "partial"

    @staticmethod
    def _attribute_root_cause(
        *,
        meta: Dict[str, Any],
        returns: Dict[int, Optional[float]],
    ) -> str:
        """Produce a short attribution narrative for the record."""
        action = (meta.get("action") or "").strip().upper()
        r5 = returns.get(5)
        r20 = returns.get(20)
        r60 = returns.get(60)
        parts: List[str] = [f"决策: {action}"]
        if r5 is not None:
            parts.append(f"5日 {r5:+.2f}%")
        if r20 is not None:
            parts.append(f"20日 {r20:+.2f}%")
        if r60 is not None:
            parts.append(f"60日 {r60:+.2f}%")
        # Short-term vs medium-term divergence often points at timing.
        if r5 is not None and r20 is not None:
            if (r5 > 0) != (r20 > 0):
                parts.append("短期与中期方向背离，择时可能偏差。")
        if meta.get("debate_summary"):
            parts.append(f"辩论摘要: {str(meta['debate_summary'])[:120]}")
        return "；".join(parts)

    @staticmethod
    def _extract_lessons(
        *,
        meta: Dict[str, Any],
        returns: Dict[int, Optional[float]],
        label: str,
    ) -> List[str]:
        """Derive a small set of plain-language lessons."""
        lessons: List[str] = []
        action = (meta.get("action") or "").strip().upper()
        r5 = returns.get(5)
        r20 = returns.get(20)
        if label == "wrong":
            lessons.append(f"{action} 决策方向错误，需复盘假设是否失效。")
        elif label == "correct":
            lessons.append(f"{action} 决策方向正确，可复用同类逻辑。")
        else:
            lessons.append(f"{action} 决策方向模糊，建议收紧触发条件。")
        if r5 is not None and r20 is not None and r5 * r20 < 0:
            lessons.append("短期与中期走势相反，注意择时风险。")
        return lessons[:5]

    @staticmethod
    def _extract_tags(*, meta: Dict[str, Any], returns: Dict[int, Optional[float]]) -> List[str]:
        tags = [(meta.get("action") or "").lower()]
        r60 = returns.get(60)
        if r60 is not None:
            if r60 > 10:
                tags.append("big_winner")
            elif r60 < -10:
                tags.append("big_loser")
        return [t for t in tags if t]

    # ------------------------------------------------------------------
    # Data backfill (best-effort, degrades gracefully offline)
    # ------------------------------------------------------------------
    def _try_fill_daily_data(self, *, code: str, analysis_date: date) -> None:
        """Best-effort fetch of missing daily bars; safe to fail offline."""
        try:
            from data_provider.base import DataFetcherManager

            end_date = analysis_date + timedelta(days=90)
            manager = DataFetcherManager()
            df, source = manager.get_daily_data(
                stock_code=code,
                start_date=analysis_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                days=90,
            )
            if df is None or df.empty:
                return
            self.db.save_daily_data(df, code=code, data_source=source)
        except Exception as exc:
            logger.warning("[ExperienceReview] 补全日线数据失败(%s): %s", code, exc)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def get_recent_experiences(
        self,
        *,
        code: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return recent experience records as plain dicts."""
        limit = max(1, min(int(limit), 200))
        with self.db.get_session() as session:
            stmt = select(ExperienceRecord)
            if code:
                stmt = stmt.where(ExperienceRecord.code == code)
            stmt = stmt.order_by(desc(ExperienceRecord.reviewed_at)).limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [self._record_to_dict(r) for r in rows]

    def get_experiences_for_prompt(self, code: str) -> str:
        """Format recent experiences for a stock as text for prompt injection."""
        records = self.get_recent_experiences(code=code, limit=10)
        if not records:
            return ""
        lines = [f"[经验复盘: {code}]"]
        for r in records:
            parts = [
                r.get("label", "unknown"),
            ]
            if r.get("ret_5d") is not None:
                parts.append(f"5D={r['ret_5d']:+.2f}%")
            if r.get("ret_20d") is not None:
                parts.append(f"20D={r['ret_20d']:+.2f}%")
            if r.get("ret_60d") is not None:
                parts.append(f"60D={r['ret_60d']:+.2f}%")
            lines.append("- " + " | ".join(parts))
            lessons = r.get("lessons") or []
            if lessons:
                lines.append("  lessons: " + "; ".join(str(l) for l in lessons[:3]))
        lines.append("Use this experience as context only; do not copy it verbatim.")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    @staticmethod
    def _record_to_dict(record: ExperienceRecord) -> Dict[str, Any]:
        def _loads(value: Optional[str]) -> Any:
            if not value:
                return []
            try:
                return json.loads(value)
            except (TypeError, ValueError):
                return []

        return {
            "id": record.id,
            "decision_snapshot_id": record.decision_snapshot_id,
            "code": record.code,
            "ret_5d": record.ret_5d,
            "ret_20d": record.ret_20d,
            "ret_60d": record.ret_60d,
            "label": record.label,
            "root_cause": record.root_cause,
            "lessons": _loads(record.lessons_json),
            "tags": _loads(record.tags_json),
            "confidence": record.confidence,
            "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
        }
