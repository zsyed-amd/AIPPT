"""In-memory ring buffer of recent log records for in-browser triage.

Pods on the SLAI platform use ephemeral storage and the operator does not
expose ``kubectl logs`` to deck authors. This handler keeps the most
recent N records in a deque so ``GET /api/logs`` can surface them without
needing pod shell access. Records are captured after
``install_authorization_scrub`` runs, so Bearer tokens are already
redacted by the time they land in the buffer.
"""
from __future__ import annotations

import itertools
import logging
import threading
import time
from collections import deque
from typing import Deque, Dict, Iterable, List, Optional


DEFAULT_CAPACITY = 2000


class RingBufferLogHandler(logging.Handler):
    """Logging handler that retains the last ``capacity`` records in memory.

    Each captured record is stored as a small dict (id, ts, level, logger,
    message) — formatting happens at capture time so the buffer is safe to
    serialize directly to JSON, and freeing the original ``LogRecord``
    avoids pinning large arg tuples.
    """

    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        super().__init__()
        self._buf: Deque[Dict[str, object]] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._counter = itertools.count(1)
        self.capacity = capacity

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:
            # A bad %-format in app code must not crash the handler.
            message = str(record.msg)
        entry = {
            "id": next(self._counter),
            "ts": record.created,
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }
        with self._lock:
            self._buf.append(entry)

    def snapshot(
        self,
        *,
        limit: int = 200,
        level: Optional[str] = None,
        since: Optional[int] = None,
        logger_prefix: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        """Return the most recent matching records, oldest first within the slice.

        Args:
            limit: cap on records returned (clamped to capacity).
            level: minimum level name (e.g. ``"WARNING"``); records below are
                filtered out. Unknown names disable level filtering.
            since: only return records whose id is greater than this. Lets a
                caller poll for "new since last call" without re-fetching.
            logger_prefix: only return records whose logger name starts with
                this string (e.g. ``"aippt"`` to drop uvicorn noise).
        """
        with self._lock:
            records = list(self._buf)
        if since is not None:
            records = [r for r in records if r["id"] > since]
        if level:
            min_level = logging.getLevelName(level.upper())
            if isinstance(min_level, int):
                records = [
                    r for r in records
                    if logging.getLevelName(r["level"]) >= min_level
                ]
        if logger_prefix:
            records = [
                r for r in records
                if str(r["logger"]).startswith(logger_prefix)
            ]
        if limit > 0:
            records = records[-limit:]
        return records

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()


def install_ring_buffer(
    capacity: int = DEFAULT_CAPACITY,
    *,
    logger_names: Iterable[str] = ("", "uvicorn.access", "uvicorn.error"),
) -> RingBufferLogHandler:
    """Attach a single ``RingBufferLogHandler`` to the named loggers.

    Idempotent within a process: if any of the target loggers already has a
    ``RingBufferLogHandler`` attached, the existing instance is reused so
    repeated ``create_app`` calls (e.g. in tests) do not stack duplicate
    handlers that double-count every record.
    """
    existing: Optional[RingBufferLogHandler] = None
    for name in logger_names:
        target = logging.getLogger(name)
        for h in target.handlers:
            if isinstance(h, RingBufferLogHandler):
                existing = h
                break
        if existing:
            break

    handler = existing or RingBufferLogHandler(capacity=capacity)

    # Python's logger-level filters do NOT run for records propagated up
    # from child loggers — only handler-level filters do. So attach the
    # Bearer scrub filter directly to this handler. Otherwise a child
    # logger emitting "Authorization: Bearer <jwt>" would land in the
    # buffer unredacted, bypassing the protection that
    # install_authorization_scrub provides for root-emitted records.
    from aippt.web.logging_filter import AuthorizationScrubFilter
    if not any(
        isinstance(f, AuthorizationScrubFilter) for f in handler.filters
    ):
        handler.addFilter(AuthorizationScrubFilter())
    for name in logger_names:
        target = logging.getLogger(name)
        if handler not in target.handlers:
            target.addHandler(handler)
        # Ensure the root logger will actually receive INFO records from
        # child loggers — uvicorn sets the root level to WARNING by default,
        # and pytest can do the same, which would silently drop our app's
        # INFO logs before the handler ever sees them. Only widen, never
        # narrow, so an explicit DEBUG choice still wins.
        if name == "" and (
            target.level == logging.NOTSET or target.level > logging.INFO
        ):
            target.setLevel(logging.INFO)
    return handler
