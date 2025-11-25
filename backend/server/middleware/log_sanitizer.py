"""
Log Sanitization Middleware
Redacts sensitive data from logs to prevent credential leakage
"""
import logging
import re
from typing import Any, Dict, Pattern


class SensitivePattern:
    """Patterns for detecting and redacting sensitive data"""

    # Password-related patterns
    PASSWORD_KEYS = re.compile(
        r'(password|passwd|pwd|secret|secret_key)[\'":\s]*[=:]\s*["\']?([^"\'\s,}]+)',
        re.IGNORECASE
    )

    # Token patterns
    TOKEN_KEYS = re.compile(
        r'(token|access_token|refresh_token|api_key|apikey|auth_token)[\'":\s]*[=:]\s*["\']?([^"\'\s,}]+)',
        re.IGNORECASE
    )

    # Authorization header
    AUTHORIZATION = re.compile(
        r'(authorization[\'":\s]*[=:]\s*["\']?)(bearer\s+)?([a-zA-Z0-9_\-\.]+)',
        re.IGNORECASE
    )

    # JWT tokens (starts with eyJ)
    JWT_TOKEN = re.compile(
        r'eyJ[a-zA-Z0-9_\-]+\.eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+'
    )

    # SSN pattern (XXX-XX-XXXX)
    SSN = re.compile(
        r'\b\d{3}-\d{2}-\d{4}\b'
    )

    # Credit card pattern (16 digits with optional spaces/dashes)
    CREDIT_CARD = re.compile(
        r'\b(?:\d{4}[\s\-]?){3}\d{4}\b'
    )

    # Email addresses (optional - can preserve domain)
    EMAIL = re.compile(
        r'\b([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
    )

    # Phone numbers (various formats)
    PHONE = re.compile(
        r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
    )

    # Generic secrets in key-value format
    SECRET_VALUE = re.compile(
        r'(["\'](?:secret|password|token|key)["\']:\s*["\'])([^"\']+)(["\'])',
        re.IGNORECASE
    )


class LogSanitizationFilter(logging.Filter):
    """
    Logging filter that sanitizes sensitive data from log records.

    This filter is applied to all loggers to prevent accidental logging
    of passwords, tokens, API keys, PII, and other sensitive information.
    """

    def __init__(self, name: str = ""):
        """
        Initialize the sanitization filter

        Args:
            name: Optional filter name
        """
        super().__init__(name)
        self.patterns: Dict[str, Pattern] = {
            'password': SensitivePattern.PASSWORD_KEYS,
            'token': SensitivePattern.TOKEN_KEYS,
            'authorization': SensitivePattern.AUTHORIZATION,
            'jwt': SensitivePattern.JWT_TOKEN,
            'ssn': SensitivePattern.SSN,
            'credit_card': SensitivePattern.CREDIT_CARD,
            'email': SensitivePattern.EMAIL,
            'phone': SensitivePattern.PHONE,
            'secret': SensitivePattern.SECRET_VALUE,
        }

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Sanitize sensitive data from log record.

        Args:
            record: Log record to sanitize

        Returns:
            True (always allows record through after sanitization)
        """
        # Sanitize the main message
        if isinstance(record.msg, str):
            record.msg = self.sanitize_string(record.msg)

        # Sanitize args if present
        if record.args:
            if isinstance(record.args, dict):
                record.args = self._sanitize_dict(record.args)
            elif isinstance(record.args, (tuple, list)):
                record.args = tuple(
                    self.sanitize_string(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )

        # Sanitize extra fields
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if isinstance(value, str):
                    setattr(record, key, self.sanitize_string(value))
                elif isinstance(value, dict):
                    setattr(record, key, self._sanitize_dict(value))

        return True

    def sanitize_string(self, text: str) -> str:
        """
        Sanitize a string by redacting sensitive patterns.

        Args:
            text: String to sanitize

        Returns:
            Sanitized string with sensitive data redacted
        """
        if not text:
            return text

        sanitized = text

        # Redact password-like keys
        sanitized = self.patterns['password'].sub(
            r'\1=[REDACTED:password]',
            sanitized
        )

        # Redact token-like keys
        sanitized = self.patterns['token'].sub(
            r'\1=[REDACTED:token]',
            sanitized
        )

        # Redact authorization headers
        sanitized = self.patterns['authorization'].sub(
            r'\1[REDACTED:authorization]',
            sanitized
        )

        # Redact JWT tokens
        sanitized = self.patterns['jwt'].sub(
            '[REDACTED:jwt]',
            sanitized
        )

        # Redact SSN
        sanitized = self.patterns['ssn'].sub(
            '[REDACTED:ssn]',
            sanitized
        )

        # Redact credit card numbers
        sanitized = self.patterns['credit_card'].sub(
            '[REDACTED:credit_card]',
            sanitized
        )

        # Redact email addresses (preserve domain for debugging)
        sanitized = self.patterns['email'].sub(
            r'[REDACTED:email]@\2',
            sanitized
        )

        # Redact phone numbers
        sanitized = self.patterns['phone'].sub(
            '[REDACTED:phone]',
            sanitized
        )

        # Redact secret values in JSON-like structures
        sanitized = self.patterns['secret'].sub(
            r'\1[REDACTED]\3',
            sanitized
        )

        return sanitized

    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively sanitize dictionary values.

        Args:
            data: Dictionary to sanitize

        Returns:
            Sanitized dictionary
        """
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = self.sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, (list, tuple)):
                sanitized[key] = [
                    self.sanitize_string(v) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                sanitized[key] = value
        return sanitized


def sanitize_log_string(text: str) -> str:
    """
    Utility function to sanitize an arbitrary string.

    This can be used in code where you need to manually sanitize
    data before logging (e.g., user input, API responses).

    Args:
        text: String to sanitize

    Returns:
        Sanitized string with sensitive data redacted

    Example:
        >>> from backend.server.middleware.log_sanitizer import sanitize_log_string
        >>> safe_msg = sanitize_log_string(f"User login: {user_email}")
        >>> logger.info(safe_msg)
    """
    sanitizer = LogSanitizationFilter()
    return sanitizer.sanitize_string(text)


def configure_log_sanitization():
    """
    Configure log sanitization for all loggers in the application.

    This should be called during application startup to ensure
    all logs are sanitized before being written.

    Example:
        >>> from backend.server.middleware.log_sanitizer import configure_log_sanitization
        >>> configure_log_sanitization()
    """
    # Create sanitization filter
    sanitizer = LogSanitizationFilter()

    # Apply to root logger (will propagate to all child loggers)
    root_logger = logging.getLogger()
    root_logger.addFilter(sanitizer)

    # Also explicitly apply to common loggers
    for logger_name in ['uvicorn', 'uvicorn.access', 'uvicorn.error',
                        'fastapi', 'backend', '__main__']:
        logger = logging.getLogger(logger_name)
        logger.addFilter(sanitizer)

    logging.info("Log sanitization configured for all loggers")


# Convenience function for importing
__all__ = [
    'LogSanitizationFilter',
    'sanitize_log_string',
    'configure_log_sanitization',
    'SensitivePattern'
]
