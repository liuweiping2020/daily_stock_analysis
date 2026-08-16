# -*- coding: utf-8 -*-
"""Shared blackboard for multi-agent collaboration.

Inspired by FinRobot's shared memory architecture, this module provides
a thread-safe blackboard where agents can post findings, read each other's
intermediate conclusions, and avoid redundant computation.

The blackboard is distinct from AgentContext: it focuses on structured
findings and cached tool results, while AgentContext carries the pipeline
state and opinions.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BlackboardEntry:
    """A single entry on the shared blackboard."""
    key: str
    value: Any
    posted_by: str = ""        # agent name
    timestamp: float = 0.0
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class SharedBlackboard:
    """Thread-safe shared blackboard for multi-agent communication.

    Agents can:
    - post(key, value, tags) — write a finding
    - read(key) — read a specific finding
    - query(tags) — find entries by tag
    - has(key) — check if a key exists
    - get_history() — get all entries

    Common use cases:
    - Cache tool results (e.g. "realtime_quote_600519") to avoid duplicate API calls
    - Share intermediate conclusions (e.g. "trend_direction", "pe_ratio")
    - Flag conflicts (e.g. "price_conflict" when agents disagree)
    """

    def __init__(self):
        self._entries: Dict[str, BlackboardEntry] = {}
        self._lock = threading.RLock()
        self._subscribers: List[callable] = []

    def post(self, key: str, value: Any, posted_by: str = "", tags: Optional[List[str]] = None) -> None:
        """Post or update an entry on the blackboard."""
        with self._lock:
            entry = BlackboardEntry(
                key=key,
                value=value,
                posted_by=posted_by,
                tags=tags or [],
            )
            self._entries[key] = entry
            logger.debug("[Blackboard] %s posted '%s' (tags: %s)", posted_by, key, tags or [])

        # Notify subscribers
        for callback in self._subscribers:
            try:
                callback(entry)
            except Exception as e:
                logger.warning("[Blackboard] subscriber callback error: %s", e)

    def read(self, key: str, default: Any = None) -> Any:
        """Read a value from the blackboard."""
        with self._lock:
            entry = self._entries.get(key)
            return entry.value if entry else default

    def has(self, key: str) -> bool:
        """Check if a key exists on the blackboard."""
        with self._lock:
            return key in self._entries

    def query(self, tags: List[str]) -> Dict[str, Any]:
        """Find entries matching any of the given tags."""
        with self._lock:
            results = {}
            for key, entry in self._entries.items():
                if any(tag in entry.tags for tag in tags):
                    results[key] = entry.value
            return results

    def query_by_poster(self, agent_name: str) -> Dict[str, Any]:
        """Get all entries posted by a specific agent."""
        with self._lock:
            return {
                key: entry.value
                for key, entry in self._entries.items()
                if entry.posted_by == agent_name
            }

    def get_history(self) -> List[Dict[str, Any]]:
        """Get all entries as a list of dicts (for logging/debugging)."""
        with self._lock:
            return [
                {
                    "key": e.key,
                    "value": e.value,
                    "posted_by": e.posted_by,
                    "timestamp": e.timestamp,
                    "tags": e.tags,
                }
                for e in sorted(self._entries.values(), key=lambda x: x.timestamp)
            ]

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._entries.clear()

    def subscribe(self, callback: callable) -> None:
        """Subscribe to blackboard updates."""
        self._subscribers.append(callback)

    def summary(self) -> Dict[str, Any]:
        """Get a summary of blackboard state."""
        with self._lock:
            return {
                "total_entries": len(self._entries),
                "keys": list(self._entries.keys()),
                "posters": list(set(e.posted_by for e in self._entries.values())),
                "tag_counts": self._count_tags(),
            }

    def _count_tags(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for entry in self._entries.values():
            for tag in entry.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return counts


# Global blackboard instance (one per analysis run)
# The orchestrator creates a fresh one per run
_blackboard: Optional[SharedBlackboard] = None
_blackboard_lock = threading.Lock()


def get_blackboard() -> SharedBlackboard:
    """Get the global SharedBlackboard instance."""
    global _blackboard
    if _blackboard is None:
        with _blackboard_lock:
            if _blackboard is None:
                _blackboard = SharedBlackboard()
    return _blackboard


def reset_blackboard() -> SharedBlackboard:
    """Reset and return a fresh blackboard (for new analysis runs)."""
    global _blackboard
    with _blackboard_lock:
        _blackboard = SharedBlackboard()
    return _blackboard
