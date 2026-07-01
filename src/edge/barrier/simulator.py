"""Entrance barrier simulator.

No hardware: state and events are only logged and exposed via the API, as required
by the demo constraints. The barrier closes by itself after a few seconds to
simulate the vehicle passing through.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger("barrier")


class BarrierSimulator:
    def __init__(self, auto_close_after_s: float = 5.0):
        self._lock = threading.Lock()
        self._is_open = False
        self._auto_close_after_s = auto_close_after_s
        self._timer: threading.Timer | None = None
        self.last_event: str | None = None
        self.last_event_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self._is_open

    def open(self, reason: str) -> None:
        """Open the barrier and schedule the automatic close."""
        with self._lock:
            self._is_open = True
            self.last_event = f"OPEN - {reason}"
            self.last_event_at = datetime.now(timezone.utc)
            logger.info("Barrier OPEN (%s)", reason)

            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._auto_close_after_s, self.close)
            self._timer.daemon = True
            self._timer.start()

    def close(self) -> None:
        with self._lock:
            self._is_open = False
            self.last_event = "CLOSED"
            self.last_event_at = datetime.now(timezone.utc)
            logger.info("Barrier CLOSED")

    def status(self) -> dict:
        return {
            "is_open": self._is_open,
            "last_event": self.last_event,
            "last_event_at": self.last_event_at,
        }
