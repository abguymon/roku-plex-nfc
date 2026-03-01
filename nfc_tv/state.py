"""Thread-safe shared state between NFC daemon and web UI."""

import threading
import time
from dataclasses import dataclass, field


@dataclass
class ScanEvent:
    uid: str
    title: str | None
    success: bool
    timestamp: float = field(default_factory=time.time)


class AppState:
    """Shared state accessed by both the daemon thread and FastAPI endpoints."""

    def __init__(self, config: dict):
        self.config = config
        self._lock = threading.Lock()

        # NFC reader status
        self.reader_ok: bool = False
        self.reader_error: str | None = None

        # Recent scan events (ring buffer)
        self._events: list[ScanEvent] = []
        self._max_events = 50

        # Scan rendezvous for card registration
        self._scan_requested = threading.Event()
        self._scan_result: str | None = None
        self._scan_ready = threading.Event()

    def set_reader_status(self, ok: bool, error: str | None = None):
        with self._lock:
            self.reader_ok = ok
            self.reader_error = error

    def add_event(self, uid: str, title: str | None, success: bool):
        event = ScanEvent(uid=uid, title=title, success=success)
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

    def get_events(self) -> list[ScanEvent]:
        with self._lock:
            return list(self._events)

    def request_scan(self, timeout: float = 30.0) -> str | None:
        """Called by the web API to wait for the next card tap.
        Returns the UID or None on timeout."""
        self._scan_result = None
        self._scan_ready.clear()
        self._scan_requested.set()

        got_result = self._scan_ready.wait(timeout=timeout)
        self._scan_requested.clear()

        if got_result:
            return self._scan_result
        return None

    def is_scan_requested(self) -> bool:
        return self._scan_requested.is_set()

    def report_scan(self, uid: str):
        """Called by the daemon thread when a card is tapped during scan mode."""
        self._scan_result = uid
        self._scan_ready.set()

    def update_config(self, config: dict):
        with self._lock:
            self.config = config
