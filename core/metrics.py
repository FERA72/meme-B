"""
Lightweight metrics recorder used to monitor external data source health.

Counters are kept in-memory so we can surface them on demand (dashboard,
/stats endpoint, audit tooling) without introducing a full metrics stack.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import DefaultDict, Dict, Optional


@dataclass
class MetricEntry:
    """Simple accumulator for success/error counts and latency buckets."""

    success: int = 0
    client_error: int = 0
    server_error: int = 0
    rate_limited: int = 0
    exceptions: int = 0
    last_error: Optional[str] = None
    last_status: Optional[int] = None
    last_latency_ms: Optional[float] = None
    total_latency_ms: float = 0.0

    def record(self, status: Optional[int], latency_ms: float, err: Optional[str] = None):
        if status is None:
            self.exceptions += 1
            self.last_error = err
            self.last_latency_ms = latency_ms
            return

        self.last_status = status
        self.last_latency_ms = latency_ms

        if 200 <= status < 300:
            self.success += 1
        elif status == 429:
            self.rate_limited += 1
            self.last_error = err or "rate_limited"
        elif 400 <= status < 500:
            self.client_error += 1
            self.last_error = err
        elif status >= 500:
            self.server_error += 1
            self.last_error = err

        self.total_latency_ms += latency_ms

    def snapshot(self) -> Dict[str, Optional[float]]:
        total_calls = (
            self.success
            + self.client_error
            + self.server_error
            + self.rate_limited
            + self.exceptions
        )
        avg_latency = (self.total_latency_ms / total_calls) if total_calls else None
        return {
            "success": self.success,
            "client_error": self.client_error,
            "server_error": self.server_error,
            "rate_limited": self.rate_limited,
            "exceptions": self.exceptions,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "last_latency_ms": self.last_latency_ms,
            "avg_latency_ms": avg_latency,
        }


class MetricsRecorder:
    """Thread-safe in-memory metrics recorder."""

    def __init__(self):
        self._entries: DefaultDict[str, MetricEntry] = defaultdict(MetricEntry)
        self._lock = threading.Lock()
        self._started_at = time.time()

    def record(self, source: str, status: Optional[int], latency_ms: float, err: Optional[str] = None):
        with self._lock:
            entry = self._entries[source]
            entry.record(status, latency_ms, err)

    def snapshot(self) -> Dict[str, Dict[str, Optional[float]]]:
        with self._lock:
            return {source: entry.snapshot() for source, entry in self._entries.items()}

    def uptime_seconds(self) -> float:
        return time.time() - self._started_at


# Global singleton so components can share without wiring through constructors.
METRICS = MetricsRecorder()

