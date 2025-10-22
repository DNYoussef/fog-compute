"""
Enhanced Error Handling Middleware
Provides standardized error responses, circuit breaker pattern, and comprehensive logging
"""
import logging
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
from collections import defaultdict
from enum import Enum

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Error categories for better tracking"""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATABASE = "database"
    EXTERNAL_SERVICE = "external_service"
    INTERNAL = "internal"
    RATE_LIMIT = "rate_limit"
    NOT_FOUND = "not_found"


class ErrorResponse(BaseModel):
    """Standardized error response model"""
    error: str
    detail: str
    error_id: str
    timestamp: str
    category: ErrorCategory
    severity: ErrorSeverity
    retry_after: Optional[int] = None
    suggestions: Optional[list[str]] = None


class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker pattern implementation to prevent cascading failures.

    Opens circuit after threshold failures, blocks requests for timeout period,
    then enters half-open state to test recovery.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_max_requests: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout_seconds)
        self.half_open_max_requests = half_open_max_requests

        # State per service
        self.state: Dict[str, CircuitBreakerState] = defaultdict(lambda: CircuitBreakerState.CLOSED)
        self.failure_count: Dict[str, int] = defaultdict(int)
        self.last_failure_time: Dict[str, datetime] = {}
        self.half_open_requests: Dict[str, int] = defaultdict(int)

    def call(self, service_name: str, func: Callable, *args, **kwargs):
        """
        Execute function with circuit breaker protection

        Args:
            service_name: Name of service (for tracking state)
            func: Function to execute
            *args, **kwargs: Arguments for function

        Returns:
            Function result or raises CircuitBreakerOpenError

        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        current_state = self.state[service_name]

        # Check if circuit is open
        if current_state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset(service_name):
                self._transition_to_half_open(service_name)
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker open for {service_name}")

        # Check if in half-open state
        if current_state == CircuitBreakerState.HALF_OPEN:
            if self.half_open_requests[service_name] >= self.half_open_max_requests:
                raise CircuitBreakerOpenError(f"Circuit breaker half-open limit reached for {service_name}")
            self.half_open_requests[service_name] += 1

        try:
            result = func(*args, **kwargs)
            self._on_success(service_name)
            return result
        except Exception as e:
            self._on_failure(service_name)
            raise

    def _should_attempt_reset(self, service_name: str) -> bool:
        """Check if enough time has passed to attempt reset"""
        if service_name not in self.last_failure_time:
            return True
        return datetime.utcnow() - self.last_failure_time[service_name] >= self.timeout

    def _transition_to_half_open(self, service_name: str):
        """Transition circuit to half-open state"""
        logger.info(f"Circuit breaker transitioning to HALF_OPEN for {service_name}")
        self.state[service_name] = CircuitBreakerState.HALF_OPEN
        self.half_open_requests[service_name] = 0

    def _on_success(self, service_name: str):
        """Handle successful request"""
        if self.state[service_name] == CircuitBreakerState.HALF_OPEN:
            logger.info(f"Circuit breaker CLOSED for {service_name} (recovery successful)")
            self.state[service_name] = CircuitBreakerState.CLOSED
            self.failure_count[service_name] = 0
            self.half_open_requests[service_name] = 0
        elif self.state[service_name] == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.failure_count[service_name] = 0

    def _on_failure(self, service_name: str):
        """Handle failed request"""
        self.failure_count[service_name] += 1
        self.last_failure_time[service_name] = datetime.utcnow()

        if self.failure_count[service_name] >= self.failure_threshold:
            logger.warning(
                f"Circuit breaker OPEN for {service_name} "
                f"(failures: {self.failure_count[service_name]})"
            )
            self.state[service_name] = CircuitBreakerState.OPEN

    def get_state(self, service_name: str) -> CircuitBreakerState:
        """Get current circuit breaker state for service"""
        return self.state[service_name]

    def reset(self, service_name: str):
        """Manually reset circuit breaker for service"""
        logger.info(f"Manually resetting circuit breaker for {service_name}")
        self.state[service_name] = CircuitBreakerState.CLOSED
        self.failure_count[service_name] = 0
        self.half_open_requests[service_name] = 0


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class RetryStrategy:
    """
    Retry strategy with exponential backoff
    """

    @staticmethod
    def calculate_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
        """
        Calculate delay for exponential backoff

        Args:
            attempt: Attempt number (0-indexed)
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds

        Returns:
            Delay in seconds
        """
        delay = min(base_delay * (2 ** attempt), max_delay)
        return delay


# Global circuit breaker instance
global_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout_seconds=60,
    half_open_max_requests=3
)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive error handling middleware with:
    - Standardized error responses
    - Error correlation IDs
    - Structured logging
    - Circuit breaker integration
    - User-friendly messages
    """

    async def dispatch(self, request: Request, call_next):
        """Process request with comprehensive error handling"""

        # Generate correlation ID for request tracing
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        try:
            response = await call_next(request)

            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id

            return response

        except CircuitBreakerOpenError as e:
            return await self._handle_circuit_breaker_error(e, correlation_id)

        except Exception as e:
            return await self._handle_unexpected_error(e, correlation_id, request)

    async def _handle_circuit_breaker_error(
        self,
        error: CircuitBreakerOpenError,
        correlation_id: str
    ) -> JSONResponse:
        """Handle circuit breaker open errors"""
        logger.warning(f"Circuit breaker open: {error} (correlation_id: {correlation_id})")

        error_response = ErrorResponse(
            error="Service Temporarily Unavailable",
            detail="The service is currently experiencing issues. Please try again later.",
            error_id=correlation_id,
            timestamp=datetime.utcnow().isoformat(),
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.HIGH,
            retry_after=60,
            suggestions=[
                "Wait 60 seconds before retrying",
                "Check system status page",
                "Contact support if issue persists"
            ]
        )

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response.dict(),
            headers={
                "X-Correlation-ID": correlation_id,
                "Retry-After": "60"
            }
        )

    async def _handle_unexpected_error(
        self,
        error: Exception,
        correlation_id: str,
        request: Request
    ) -> JSONResponse:
        """Handle unexpected errors with comprehensive logging"""

        # Log full error details for debugging
        logger.error(
            f"Unexpected error in {request.method} {request.url.path}",
            extra={
                "correlation_id": correlation_id,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "traceback": traceback.format_exc(),
                "request_method": request.method,
                "request_path": request.url.path,
                "client_host": request.client.host if request.client else None
            }
        )

        # Determine error category and severity
        category, severity = self._categorize_error(error)

        # Create user-friendly error response (no stack traces!)
        error_response = ErrorResponse(
            error="Internal Server Error",
            detail=self._get_user_friendly_message(error, category),
            error_id=correlation_id,
            timestamp=datetime.utcnow().isoformat(),
            category=category,
            severity=severity,
            suggestions=self._get_suggestions(category)
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.dict(),
            headers={"X-Correlation-ID": correlation_id}
        )

    def _categorize_error(self, error: Exception) -> tuple[ErrorCategory, ErrorSeverity]:
        """Categorize error for better tracking"""
        error_type = type(error).__name__

        # Database errors
        if any(db_error in error_type for db_error in ["SQLAlchemy", "Database", "Connection"]):
            return ErrorCategory.DATABASE, ErrorSeverity.CRITICAL

        # Authentication/Authorization errors
        if any(auth_error in error_type for auth_error in ["Auth", "Permission", "Forbidden"]):
            return ErrorCategory.AUTHENTICATION, ErrorSeverity.MEDIUM

        # Validation errors
        if any(val_error in error_type for val_error in ["Validation", "Pydantic"]):
            return ErrorCategory.VALIDATION, ErrorSeverity.LOW

        # Default to internal error
        return ErrorCategory.INTERNAL, ErrorSeverity.HIGH

    def _get_user_friendly_message(self, error: Exception, category: ErrorCategory) -> str:
        """Generate user-friendly error message (no technical details)"""
        messages = {
            ErrorCategory.DATABASE: "We're having trouble accessing our database. Please try again in a moment.",
            ErrorCategory.AUTHENTICATION: "There was an issue with your authentication. Please log in again.",
            ErrorCategory.AUTHORIZATION: "You don't have permission to perform this action.",
            ErrorCategory.VALIDATION: "The data provided was invalid. Please check your input and try again.",
            ErrorCategory.EXTERNAL_SERVICE: "An external service is temporarily unavailable. Please try again later.",
            ErrorCategory.RATE_LIMIT: "You've made too many requests. Please slow down.",
            ErrorCategory.NOT_FOUND: "The requested resource was not found.",
            ErrorCategory.INTERNAL: "An unexpected error occurred. Our team has been notified."
        }
        return messages.get(category, "An error occurred. Please try again.")

    def _get_suggestions(self, category: ErrorCategory) -> list[str]:
        """Get helpful suggestions based on error category"""
        suggestions_map = {
            ErrorCategory.DATABASE: [
                "Try again in a few moments",
                "Check if your internet connection is stable",
                "Contact support if the issue persists"
            ],
            ErrorCategory.AUTHENTICATION: [
                "Log out and log back in",
                "Clear your browser cache",
                "Reset your password if needed"
            ],
            ErrorCategory.VALIDATION: [
                "Review the input requirements",
                "Check for missing required fields",
                "Ensure data formats are correct"
            ],
            ErrorCategory.EXTERNAL_SERVICE: [
                "Wait a few minutes and retry",
                "Check the service status page",
                "Contact support if urgent"
            ],
            ErrorCategory.RATE_LIMIT: [
                "Wait before making more requests",
                "Reduce request frequency",
                "Contact support for higher limits"
            ]
        }
        return suggestions_map.get(category, ["Try again later", "Contact support if issue persists"])


def handle_validation_error(error: Exception) -> JSONResponse:
    """Handle Pydantic validation errors"""
    correlation_id = str(uuid.uuid4())

    error_response = ErrorResponse(
        error="Validation Error",
        detail=str(error),
        error_id=correlation_id,
        timestamp=datetime.utcnow().isoformat(),
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.LOW,
        suggestions=[
            "Check that all required fields are provided",
            "Verify data types and formats",
            "Review the API documentation"
        ]
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.dict(),
        headers={"X-Correlation-ID": correlation_id}
    )


def handle_authentication_error(detail: str = "Authentication required") -> JSONResponse:
    """Handle authentication errors"""
    correlation_id = str(uuid.uuid4())

    error_response = ErrorResponse(
        error="Authentication Error",
        detail=detail,
        error_id=correlation_id,
        timestamp=datetime.utcnow().isoformat(),
        category=ErrorCategory.AUTHENTICATION,
        severity=ErrorSeverity.MEDIUM,
        suggestions=[
            "Log in with valid credentials",
            "Check if your session has expired",
            "Reset your password if you've forgotten it"
        ]
    )

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=error_response.dict(),
        headers={
            "X-Correlation-ID": correlation_id,
            "WWW-Authenticate": "Bearer"
        }
    )


def handle_authorization_error(detail: str = "Insufficient permissions") -> JSONResponse:
    """Handle authorization errors"""
    correlation_id = str(uuid.uuid4())

    error_response = ErrorResponse(
        error="Authorization Error",
        detail=detail,
        error_id=correlation_id,
        timestamp=datetime.utcnow().isoformat(),
        category=ErrorCategory.AUTHORIZATION,
        severity=ErrorSeverity.MEDIUM,
        suggestions=[
            "Contact your administrator for access",
            "Verify you have the required permissions",
            "Log in with an account that has appropriate privileges"
        ]
    )

    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=error_response.dict(),
        headers={"X-Correlation-ID": correlation_id}
    )


def handle_not_found_error(resource: str = "Resource") -> JSONResponse:
    """Handle not found errors"""
    correlation_id = str(uuid.uuid4())

    error_response = ErrorResponse(
        error="Not Found",
        detail=f"{resource} not found",
        error_id=correlation_id,
        timestamp=datetime.utcnow().isoformat(),
        category=ErrorCategory.NOT_FOUND,
        severity=ErrorSeverity.LOW,
        suggestions=[
            "Check the URL or ID is correct",
            "Verify the resource exists",
            "Contact support if you believe this is an error"
        ]
    )

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=error_response.dict(),
        headers={"X-Correlation-ID": correlation_id}
    )
