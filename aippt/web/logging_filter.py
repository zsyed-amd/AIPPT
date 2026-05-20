"""Preventative Authorization-header scrubbing for log records.

Today no log call includes the ``Authorization: Bearer <token>`` header
(verified during manual validation: ``grep -cE "eyJ|Bearer" server.log``
returned 0). This filter exists so a future regression — say someone
debug-logging ``request.headers`` — cannot leak a JWT into stdout / log
files. Applied to ``uvicorn.access``, ``uvicorn.error``, and the root
logger when the FastAPI app starts.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

BEARER_REDACTION = "Bearer <redacted>"

# Match the Bearer scheme (case-insensitive on the keyword) followed by a
# non-whitespace token. Tokens are JWTs in practice — 'eyJ' prefix, dots,
# url-safe base64 — but we deliberately accept any non-whitespace value so
# raw / malformed tokens get scrubbed too.
_BEARER_RE = re.compile(r"(?i)bearer\s+\S+")


def _scrub(text: str) -> str:
    return _BEARER_RE.sub(BEARER_REDACTION, text)


class AuthorizationScrubFilter(logging.Filter):
    """Strip Bearer tokens from log message text and lazy-args.

    Logging records carry both ``record.msg`` (the format string) and
    ``record.args`` (the values that get spliced in at format time). We
    have to rewrite both, or a ``logger.info("headers=%s", headers_dict)``
    call would still leak the token via the args tuple.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        if isinstance(record.msg, str) and "earer" in record.msg.lower():
            record.msg = _scrub(record.msg)
        if record.args:
            record.args = self._scrub_args(record.args)
        return True

    def _scrub_args(self, args):
        if isinstance(args, dict):
            return {k: _scrub_value(v) for k, v in args.items()}
        if isinstance(args, tuple):
            return tuple(_scrub_value(a) for a in args)
        return _scrub_value(args)


def _scrub_value(value):
    if isinstance(value, str):
        return _scrub(value) if "earer" in value.lower() else value
    if isinstance(value, dict):
        return {k: _scrub_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        scrubbed = [_scrub_value(v) for v in value]
        return type(value)(scrubbed)
    return value


_DEFAULT_LOGGERS = ("uvicorn.access", "uvicorn.error", "")


def install_authorization_scrub(
    logger_names: Iterable[str] = _DEFAULT_LOGGERS,
) -> None:
    """Attach the scrub filter to the named loggers (idempotent).

    Logger '' targets the root logger, which catches anything propagated
    up from app code. Re-running this function does not stack duplicate
    filters; the first install wins.
    """
    for name in logger_names:
        target = logging.getLogger(name)
        if any(isinstance(f, AuthorizationScrubFilter) for f in target.filters):
            continue
        target.addFilter(AuthorizationScrubFilter())
