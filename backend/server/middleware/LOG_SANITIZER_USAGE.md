# Log Sanitizer Usage Guide

## Overview

The log sanitizer middleware automatically redacts sensitive data from all application logs to prevent credential leakage and PII exposure.

## Quick Start

### 1. Configure on Application Startup

Add this to your main application file (e.g., `main.py`):

```python
from backend.server.middleware import configure_log_sanitization

# Early in your startup sequence
configure_log_sanitization()
```

This applies sanitization to ALL loggers in the application.

### 2. Normal Logging (Automatic Sanitization)

Once configured, all logs are automatically sanitized:

```python
import logging

logger = logging.getLogger(__name__)

# This will be automatically sanitized
logger.info(f"User login with password={user_password}")
# Output: "User login with password=[REDACTED:password]"

logger.info(f"API request with Authorization: Bearer {token}")
# Output: "API request with Authorization: [REDACTED:authorization]"
```

### 3. Manual Sanitization (Utility Function)

For cases where you need to sanitize strings before logging:

```python
from backend.server.middleware import sanitize_log_string

user_input = "My SSN is 123-45-6789"
safe_message = sanitize_log_string(user_input)
logger.info(safe_message)
# Output: "My SSN is [REDACTED:ssn]"
```

## What Gets Redacted

### Credentials
- **Passwords**: `password=`, `passwd=`, `pwd=`, `secret=`
- **Tokens**: `token=`, `access_token=`, `refresh_token=`, `api_key=`
- **Authorization**: `Authorization: Bearer ...`
- **JWT Tokens**: Any string starting with `eyJ...`

### Personal Identifiable Information (PII)
- **SSN**: `XXX-XX-XXXX` format
- **Credit Cards**: 16-digit numbers (with optional spaces/dashes)
- **Email Addresses**: Redacts username, keeps domain (for debugging)
- **Phone Numbers**: Various formats including (XXX) XXX-XXXX

### Examples

| Original | Redacted |
|----------|----------|
| `password=mysecret123` | `password=[REDACTED:password]` |
| `api_key=sk_live_12345` | `api_key=[REDACTED:token]` |
| `Bearer abc123def456` | `Bearer [REDACTED:authorization]` |
| `eyJhbGci...` (JWT) | `[REDACTED:jwt]` |
| `123-45-6789` | `[REDACTED:ssn]` |
| `4532-1234-5678-9010` | `[REDACTED:credit_card]` |
| `user@example.com` | `[REDACTED:email]@example.com` |
| `(555) 123-4567` | `[REDACTED:phone]` |

## Implementation Details

### Filter Application

The `LogSanitizationFilter` is a standard Python `logging.Filter` that:
1. Intercepts every log record before it's written
2. Sanitizes the message, args, and extra fields
3. Applies pattern matching for sensitive data
4. Replaces matches with `[REDACTED:type]` markers

### Performance

- **Minimal overhead**: Regex patterns are compiled once at initialization
- **Efficient matching**: Only scans string fields in log records
- **No file I/O**: All sanitization happens in-memory before writing

### Security Considerations

1. **Apply Early**: Call `configure_log_sanitization()` as early as possible in your application startup
2. **Log Rotation**: Even with sanitization, rotate logs regularly
3. **Access Control**: Restrict access to log files (even sanitized ones)
4. **Audit**: Periodically review logs to ensure sanitization is working

## Testing

Run the standalone test to verify sanitization:

```bash
cd fog-compute
python test_log_sanitizer.py
```

Or run the pytest test:

```bash
pytest backend/tests/security/test_production_hardening.py::TestMonitoringAndLogging::test_sensitive_data_not_logged -v
```

## Advanced Usage

### Custom Filter

If you need custom sanitization for specific loggers:

```python
from backend.server.middleware import LogSanitizationFilter

# Create custom logger with sanitization
custom_logger = logging.getLogger("my_custom_logger")
custom_logger.addFilter(LogSanitizationFilter())
```

### Excluding Loggers

If you need a logger that doesn't sanitize (NOT recommended for production):

```python
# Create logger without the filter
unsafe_logger = logging.getLogger("unsafe_debug_logger")
unsafe_logger.propagate = False  # Don't propagate to root (which has sanitization)
```

### Adding Custom Patterns

Extend the `SensitivePattern` class:

```python
from backend.server.middleware.log_sanitizer import LogSanitizationFilter, SensitivePattern
import re

# Add custom pattern
SensitivePattern.CUSTOM_SECRET = re.compile(r'my_secret_pattern')

# Create filter with custom pattern
class CustomSanitizer(LogSanitizationFilter):
    def __init__(self):
        super().__init__()
        self.patterns['custom'] = SensitivePattern.CUSTOM_SECRET
```

## Troubleshooting

### Sensitive Data Still Appearing in Logs

1. **Check filter is applied**: Verify `configure_log_sanitization()` was called
2. **Check logger hierarchy**: Ensure logger has `propagate=True` (default)
3. **Check pattern match**: The sensitive data might not match any pattern
4. **Add custom pattern**: See "Adding Custom Patterns" above

### False Positives

If legitimate data is being redacted:

1. **Review patterns**: Check if pattern is too broad
2. **Use manual sanitization**: Pre-process the string before logging
3. **Adjust regex**: Modify the pattern to be more specific

## Security Compliance

This implementation helps meet security requirements for:
- **SEC-06**: Log sanitization (TODO-DEBT-REGISTER.md)
- **OWASP**: Logging and Monitoring best practices
- **PCI-DSS**: Requirement 3.4 (render PAN unreadable)
- **GDPR**: Data minimization in logs
- **HIPAA**: PHI protection in logs

## Support

For issues or questions:
1. Check the test file: `backend/tests/security/test_production_hardening.py`
2. Run standalone test: `python test_log_sanitizer.py`
3. Review the source: `backend/server/middleware/log_sanitizer.py`
