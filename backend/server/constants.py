"""
Shared constants for the backend server.

This module centralizes commonly used values to avoid magic numbers and make
unit conversions explicit across the codebase.
"""

# File size constants
ONE_KB = 1024
ONE_MB = ONE_KB * 1024
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

# Betanet service constants
BETANET_CONNECTION_TIMEOUT = 5
BETANET_READ_TIMEOUT = 5
BETANET_MAX_RETRIES = 3
BETANET_BUFFER_SIZE = ONE_KB

# Resource threshold constants
CPU_THRESHOLD_WARNING = 80
CPU_THRESHOLD_CRITICAL = 95
MEMORY_THRESHOLD_WARNING = 80
MEMORY_THRESHOLD_CRITICAL = 90

# Scheduler constants
SCHEDULER_CHECK_INTERVAL = 1.0
SCHEDULER_CLEANUP_INTERVAL = 60
SCHEDULER_MAX_CONCURRENT_JOBS = 0

# Metrics aggregation constants
METRICS_BATCH_SIZE = 1000
METRICS_FLUSH_INTERVAL = ONE_MINUTE
