# -*- coding: utf-8 -*-
"""Data source health tracking and circuit breaker.

Monitors fetcher success rates, latency, and rate-limit events.
Dynamically adjusts effective priority based on health metrics.
"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class FetcherHealth:
    """Health metrics for a single data source fetcher."""
    name: str
    total_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    rate_limit_count: int = 0
    avg_latency_ms: float = 0.0
    last_success_ts: float = 0.0
    last_failure_ts: float = 0.0
    consecutive_failures: int = 0
    circuit_state: str = "closed"  # closed/open/half_open
    circuit_opened_at: float = 0.0
    latency_history: deque = field(default_factory=lambda: deque(maxlen=50))

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.success_count / self.total_calls

    @property
    def is_healthy(self) -> bool:
        if self.circuit_state == "open":
            return False
        if self.consecutive_failures >= 5:
            return False
        if self.total_calls > 10 and self.success_rate < 0.3:
            return False
        return True


class DataSourceHealthTracker:
    """Tracks health metrics for all data source fetchers.

    Provides circuit-breaker semantics and dynamic priority adjustment.
    A fetcher that consistently fails gets its effective priority lowered,
    allowing healthier sources to be tried first.
    """

    # Circuit breaker thresholds
    FAILURE_THRESHOLD = 5          # consecutive failures to open circuit
    RECOVERY_TIMEOUT_S = 300       # 5 minutes before half-open retry
    HALF_OPEN_MAX_PROBES = 1       # allow 1 probe request in half-open state
    MIN_CALLS_BEFORE_HEALTH = 3    # need at least 3 calls before health-based reordering

    def __init__(self):
        self._health: Dict[str, FetcherHealth] = {}
        self._lock = threading.RLock()

    def get_health(self, fetcher_name: str) -> FetcherHealth:
        with self._lock:
            if fetcher_name not in self._health:
                self._health[fetcher_name] = FetcherHealth(name=fetcher_name)
            return self._health[fetcher_name]

    def record_success(self, fetcher_name: str, latency_ms: float) -> None:
        with self._lock:
            h = self.get_health(fetcher_name)
            h.total_calls += 1
            h.success_count += 1
            h.consecutive_failures = 0
            h.last_success_ts = time.time()
            h.latency_history.append(latency_ms)
            h.avg_latency_ms = sum(h.latency_history) / len(h.latency_history)
            if h.circuit_state in ("open", "half_open"):
                h.circuit_state = "closed"
                h.circuit_opened_at = 0.0
                logger.info("[HealthTracker] circuit closed for %s (recovered)", fetcher_name)

    def record_failure(self, fetcher_name: str, is_rate_limit: bool = False) -> None:
        with self._lock:
            h = self.get_health(fetcher_name)
            h.total_calls += 1
            h.failure_count += 1
            h.consecutive_failures += 1
            h.last_failure_ts = time.time()
            if is_rate_limit:
                h.rate_limit_count += 1
            if h.consecutive_failures >= self.FAILURE_THRESHOLD:
                if h.circuit_state != "open":
                    h.circuit_state = "open"
                    h.circuit_opened_at = time.time()
                    logger.warning(
                        "[HealthTracker] circuit opened for %s (%d consecutive failures)",
                        fetcher_name, h.consecutive_failures,
                    )

    def should_try(self, fetcher_name: str) -> bool:
        """Check if a fetcher should be attempted (circuit breaker logic)."""
        with self._lock:
            h = self.get_health(fetcher_name)
            if h.circuit_state == "closed":
                return True
            if h.circuit_state == "open":
                elapsed = time.time() - h.circuit_opened_at
                if elapsed >= self.RECOVERY_TIMEOUT_S:
                    h.circuit_state = "half_open"
                    logger.info("[HealthTracker] circuit half-open for %s (probing)", fetcher_name)
                    return True
                return False
            if h.circuit_state == "half_open":
                return True  # allow probe
            return True

    def get_effective_priority(self, fetcher_name: str, base_priority: int) -> int:
        """Return adjusted priority based on health.

        Lower number = higher priority. Unhealthy fetchers get penalty.
        """
        with self._lock:
            h = self.get_health(fetcher_name)
            if not h.is_healthy:
                return base_priority + 100  # large penalty
            if h.total_calls < self.MIN_CALLS_BEFORE_HEALTH:
                return base_priority
            # Small penalty for low success rate
            if h.success_rate < 0.8:
                penalty = int((1.0 - h.success_rate) * 10)
                return base_priority + penalty
            # Small penalty for high latency
            if h.avg_latency_ms > 3000:
                return base_priority + 2
            return base_priority

    def get_health_summary(self) -> List[Dict]:
        """Return health status for all tracked fetchers."""
        with self._lock:
            results = []
            for name, h in self._health.items():
                results.append({
                    "name": name,
                    "total_calls": h.total_calls,
                    "success_rate": round(h.success_rate, 4),
                    "avg_latency_ms": round(h.avg_latency_ms, 2),
                    "circuit_state": h.circuit_state,
                    "consecutive_failures": h.consecutive_failures,
                    "rate_limit_count": h.rate_limit_count,
                    "is_healthy": h.is_healthy,
                })
            return results

    def reset(self, fetcher_name: Optional[str] = None) -> None:
        """Reset health data for one or all fetchers."""
        with self._lock:
            if fetcher_name:
                self._health.pop(fetcher_name, None)
            else:
                self._health.clear()


# Global singleton instance
_health_tracker: Optional[DataSourceHealthTracker] = None
_health_tracker_lock = threading.Lock()


def get_health_tracker() -> DataSourceHealthTracker:
    """Get the global DataSourceHealthTracker singleton."""
    global _health_tracker
    if _health_tracker is None:
        with _health_tracker_lock:
            if _health_tracker is None:
                _health_tracker = DataSourceHealthTracker()
    return _health_tracker
