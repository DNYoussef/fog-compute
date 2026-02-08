"""
Mock guard utilities (SIN-032).

Provides a single check that code paths can use before returning mock/stub data.
In production (APP_ENV=production, ALLOW_MOCKS=false) any mock fallback raises
instead of silently returning fake data.
"""
import os
import logging

logger = logging.getLogger(__name__)

_APP_ENV = os.getenv("APP_ENV", "development")
_ALLOW_MOCKS = os.getenv("ALLOW_MOCKS", "true").lower() == "true"


class MockNotAllowedError(RuntimeError):
    """Raised when mock data is requested in a production environment."""


def allow_mock_fallback() -> bool:
    """Return True only when mock data is permitted."""
    return _ALLOW_MOCKS and _APP_ENV != "production"


def guard_mock(context: str = "") -> None:
    """Raise if we are about to serve mock data in production.

    Call this at the top of any mock-returning code path.
    In development/staging with ALLOW_MOCKS=true this is a no-op.
    """
    if not allow_mock_fallback():
        msg = f"Mock data requested in {_APP_ENV} with ALLOW_MOCKS={_ALLOW_MOCKS}"
        if context:
            msg = f"{msg} (context: {context})"
        raise MockNotAllowedError(msg)
    if context:
        logger.warning("Serving mock data: %s", context)
