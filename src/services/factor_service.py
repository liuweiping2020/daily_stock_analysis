# -*- coding: utf-8 -*-
"""Factor computation and persistence service."""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.core.factor_engine import FactorEngine, FactorValue, get_factor, list_factors
from src.storage import DatabaseManager, FactorSnapshot, StockDaily

logger = logging.getLogger(__name__)


class FactorService:
    """Service for computing, storing, and retrieving factor values."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()
        self.engine = FactorEngine()

    def compute_and_save(self, code: str, days: int = 60) -> int:
        """Compute all factors for a stock and save to database.

        Returns number of factor snapshots saved.
        """
        with self.db.get_session() as session:
            rows = session.execute(
                select(StockDaily)
                .where(StockDaily.code == code)
                .order_by(StockDaily.date.desc())
                .limit(days)
            ).scalars().all()

        if not rows:
            logger.warning("[FactorService] no daily data for %s", code)
            return 0

        bars = list(reversed(rows))  # oldest first
        factor_values = self.engine.compute_all(bars, code=code)

        if not factor_values:
            return 0

        # Save to database (upsert)
        saved = 0
        with self.db.get_session() as session:
            for fv in factor_values:
                if math.isnan(fv.value):
                    continue
                stmt = sqlite_insert(FactorSnapshot).values(
                    code=code,
                    date=fv.date or date.today(),
                    factor_name=fv.factor_name,
                    factor_category=next((f.category for f in self.engine.factors if f.name == fv.factor_name), "technical"),
                    value=fv.value,
                    raw_data_json=None,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=['code', 'date', 'factor_name'],
                    set_=dict(
                        value=fv.value,
                        factor_category=stmt.excluded.factor_category,
                    ),
                )
                session.execute(stmt)
                saved += 1
            session.commit()

        logger.info("[FactorService] saved %d factor snapshots for %s", saved, code)
        return saved

    def get_factors(
        self,
        code: str,
        factor_names: Optional[List[str]] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Retrieve stored factor values for a stock."""
        with self.db.get_session() as session:
            conditions = [FactorSnapshot.code == code]
            if factor_names:
                conditions.append(FactorSnapshot.factor_name.in_(factor_names))

            cutoff = date.today() - timedelta(days=days)
            conditions.append(FactorSnapshot.date >= cutoff)

            rows = session.execute(
                select(FactorSnapshot)
                .where(and_(*conditions))
                .order_by(FactorSnapshot.date.desc(), FactorSnapshot.factor_name)
            ).scalars().all()

        return [
            {
                "code": r.code,
                "date": str(r.date) if r.date else None,
                "factor_name": r.factor_name,
                "factor_category": r.factor_category,
                "value": r.value,
            }
            for r in rows
        ]

    def get_latest_factors(self, code: str) -> Dict[str, float]:
        """Get latest factor values as a dict {factor_name: value}."""
        with self.db.get_session() as session:
            # Get the most recent date for this stock
            latest = session.execute(
                select(FactorSnapshot.date)
                .where(FactorSnapshot.code == code)
                .order_by(FactorSnapshot.date.desc())
                .limit(1)
            ).scalar_one_or_none()

            if latest is None:
                return {}

            rows = session.execute(
                select(FactorSnapshot)
                .where(and_(FactorSnapshot.code == code, FactorSnapshot.date == latest))
            ).scalars().all()

        return {r.factor_name: r.value for r in rows}

    def list_available_factors(self) -> List[Dict[str, str]]:
        """List all registered factor definitions."""
        return list_factors()
