"""
Shared constants used across backend test modules.

Decouples tests from scattered literals to improve readability and ease of
updates when requirements change.
"""
from backend.server.constants import (
    ONE_MB,
    FIVE_MB,
    TEN_MB,
    ONE_GB,
    ONE_MINUTE,
    ONE_HOUR,
    ONE_DAY,
)

# File sizes
TEST_SMALL_FILE_SIZE = ONE_MB
TEST_MEDIUM_FILE_SIZE = FIVE_MB
TEST_LARGE_FILE_SIZE = TEN_MB
TEST_MAX_FILE_SIZE = ONE_GB
TEST_FILE_CONTENT = b"x" * 1024

# Timeouts
TEST_TIMEOUT_SHORT = 5
TEST_TIMEOUT_MEDIUM = 30
TEST_TIMEOUT_LONG = 120

# User credentials
TEST_USER_EMAIL = "testuser@example.com"
TEST_USER_PASSWORD = "TestUserPass123!"
TEST_ADMIN_EMAIL = "admin@example.com"

# Network targets
TEST_PORT = 8000
TEST_HOST = "127.0.0.1"
TEST_BASE_URL = f"http://{TEST_HOST}:{TEST_PORT}"

# Pagination and limits
TEST_PAGE_SIZE = 10
TEST_MAX_RESULTS = 100

# Security thresholds
TEST_MAX_LOGIN_ATTEMPTS = 5
TEST_LOCKOUT_DURATION = 300
TEST_TOKEN_LENGTH = 32
