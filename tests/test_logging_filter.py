"""Tests for the Authorization-header scrub log filter.

Preventative hardening: if a future code path ever logs a request line or
header dict containing ``Authorization: Bearer <token>``, the filter strips
the token bytes before the line hits stdout / log files. Today no log call
includes the header (verified manually during validation), but this guards
against regressions.
"""
import logging

import pytest

from aippt.web.logging_filter import (
    BEARER_REDACTION,
    AuthorizationScrubFilter,
    install_authorization_scrub,
)


@pytest.fixture
def filter_():
    return AuthorizationScrubFilter()


def _make_record(msg, args=()):
    return logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg=msg, args=args, exc_info=None,
    )


class TestAuthorizationScrubFilter:
    def test_passes_unrelated_messages_through_unchanged(self, filter_):
        rec = _make_record("user signed in")
        assert filter_.filter(rec) is True
        assert rec.getMessage() == "user signed in"

    def test_scrubs_bearer_token_from_message(self, filter_):
        rec = _make_record(
            "request: Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
        )
        filter_.filter(rec)
        text = rec.getMessage()
        assert "eyJhbGciOiJIUzI1NiJ9.payload.sig" not in text
        assert BEARER_REDACTION in text

    def test_scrubs_bearer_token_in_lazy_args(self, filter_):
        rec = _make_record(
            "headers=%s",
            ({"Authorization": "Bearer eyJabc.payload.sig"},),
        )
        filter_.filter(rec)
        text = rec.getMessage()
        assert "eyJabc.payload.sig" not in text
        assert BEARER_REDACTION in text

    def test_case_insensitive_on_scheme(self, filter_):
        rec = _make_record("authorization: bearer some.long.jwt-value")
        filter_.filter(rec)
        text = rec.getMessage()
        assert "some.long.jwt-value" not in text

    def test_scrubs_multiple_tokens(self, filter_):
        rec = _make_record(
            "first Bearer abc.def.ghi and second Bearer jkl.mno.pqr",
        )
        filter_.filter(rec)
        text = rec.getMessage()
        assert "abc.def.ghi" not in text
        assert "jkl.mno.pqr" not in text


class TestInstallAuthorizationScrub:
    def test_attaches_filter_to_target_loggers(self):
        # Install onto a freshly-named logger so the test doesn't leak state.
        target = "test.scrub.target"
        install_authorization_scrub(logger_names=(target,))
        logger = logging.getLogger(target)
        try:
            assert any(
                isinstance(f, AuthorizationScrubFilter)
                for f in logger.filters
            )
        finally:
            logger.filters = [
                f for f in logger.filters
                if not isinstance(f, AuthorizationScrubFilter)
            ]

    def test_idempotent(self):
        target = "test.scrub.idempotent"
        install_authorization_scrub(logger_names=(target,))
        install_authorization_scrub(logger_names=(target,))
        logger = logging.getLogger(target)
        try:
            count = sum(
                1 for f in logger.filters
                if isinstance(f, AuthorizationScrubFilter)
            )
            assert count == 1, (
                f"install_authorization_scrub should be idempotent, found {count}"
            )
        finally:
            logger.filters = [
                f for f in logger.filters
                if not isinstance(f, AuthorizationScrubFilter)
            ]
