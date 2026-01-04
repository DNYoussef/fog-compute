"""
Shared constants for the backend server.

This module centralizes commonly used values to avoid magic numbers and make
unit conversions explicit across the codebase.
"""

# File size constants
ONE_KB = 1024
ONE_MB = ONE_KB * 1024
FIVE_MB = ONE_MB * 5
TEN_MB = ONE_MB * 10
ONE_GB = ONE_MB * 1024

# Time constants
ONE_SECOND = 1
ONE_MINUTE = 60 * ONE_SECOND
ONE_HOUR = 60 * ONE_MINUTE
ONE_DAY = 24 * ONE_HOUR
ONE_WEEK = 7 * ONE_DAY
ONE_MONTH = 30 * ONE_DAY
ONE_YEAR = 365 * ONE_DAY

# Domain-specific constants
HSTS_MAX_AGE = ONE_YEAR
MAX_MESSAGE_SIZE = ONE_MB
MAX_ATTACHMENT_SIZE = ONE_GB
DEFAULT_CHUNK_SIZE = ONE_MB
