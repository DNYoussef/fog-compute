"""
Audit Middleware
Automatically logs all API requests for security audit trail
"""
import time
import uuid
import logging
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..services.audit_service import log_audit_event
from ..auth.jwt_utils import verify_token

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically audit all API requests
    Captures request metadata and response status
    """

    def __init__(
        self,
        app: ASGIApp,
        excluded_paths: Optional[list] = None,
        log_successful_reads: bool = False,
    ):
        """
        Initialize audit middleware

        Args:
            app: FastAPI application
            excluded_paths: List of paths to exclude from auditing (e.g., /health, /metrics)
            log_successful_reads: Whether to log successful GET requests (can be verbose)
        """
        super().__init__(app)
        self.excluded_paths = excluded_paths or ['/health', '/metrics', '/docs', '/openapi.json']
        self.log_successful_reads = log_successful_reads

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log audit event"""

        # Skip excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        # Extract request metadata
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get('User-Agent', 'Unknown')
        method = request.method
        path = request.url.path

        # Extract user from token (if present)
        user_id = None
        try:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
                payload = verify_token(token)
                if payload:
                    user_id = payload.get('sub')
        except Exception:
            pass  # Continue without user_id if token is invalid

        # Measure request duration
        start_time = time.time()

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            success = 200 <= status_code < 400
            status = 'success' if success else 'failure'
        except Exception as e:
            # Log failed requests
            status_code = 500
            status = 'failure'
            await self._log_event(
                event_type='api_request_error',
                ip_address=ip_address,
                user_agent=user_agent,
                action=method,
                status='failure',
                user_id=user_id,
                correlation_id=correlation_id,
                metadata={
                    'method': method,
                    'path': path,
                    'status_code': status_code,
                    'error': str(e),
                }
            )
            raise

        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000

        # Add correlation ID to response headers
        response.headers['X-Correlation-ID'] = correlation_id

        # Determine if we should log this request
        should_log = self._should_log_request(method, status_code)

        if should_log:
            # Determine event type based on method and path
            event_type = self._classify_event(method, path, status_code)

            # Extract resource information from path
            resource_type, resource_id = self._extract_resource(path)

            await self._log_event(
                event_type=event_type,
                ip_address=ip_address,
                user_agent=user_agent,
                action=method.lower(),
                status=status,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                metadata={
                    'method': method,
                    'path': path,
                    'status_code': status_code,
                    'response_time_ms': round(response_time_ms, 2),
                }
            )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for proxied requests
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()

        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip

        # Fallback to direct connection
        if request.client:
            return request.client.host

        return 'unknown'

    def _should_log_request(self, method: str, status_code: int) -> bool:
        """Determine if request should be logged"""
        # Always log failed requests
        if status_code >= 400:
            return True

        # Always log write operations
        if method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return True

        # Log read operations only if configured
        if method == 'GET':
            return self.log_successful_reads

        return True

    def _classify_event(self, method: str, path: str, status_code: int) -> str:
        """Classify event type based on request characteristics"""
        # Authentication endpoints
        if '/auth/login' in path:
            return 'login' if status_code < 400 else 'login_failed'
        if '/auth/logout' in path:
            return 'logout'
        if '/auth/register' in path:
            return 'user_created'

        # Permission denied
        if status_code == 403:
            return 'permission_denied'

        # Admin actions
        if '/admin' in path or '/audit' in path:
            return 'admin_action'

        # Data operations
        if method == 'GET':
            return 'data_access'
        elif method == 'POST':
            return 'data_create'
        elif method in ['PUT', 'PATCH']:
            return 'data_modify'
        elif method == 'DELETE':
            return 'data_delete'

        return 'api_request'

    def _extract_resource(self, path: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extract resource type and ID from path
        Examples:
            /api/users/123 -> ('user', '123')
            /api/jobs/abc-def -> ('job', 'abc-def')
        """
        parts = path.strip('/').split('/')

        # Look for common patterns: /api/{resource}/{id}
        if len(parts) >= 3 and parts[0] == 'api':
            resource_type = parts[1].rstrip('s')  # Remove plural 's'
            resource_id = parts[2] if len(parts) > 2 else None
            return resource_type, resource_id

        # Look for patterns: /{resource}/{id}
        if len(parts) >= 2:
            resource_type = parts[0].rstrip('s')
            resource_id = parts[1]
            return resource_type, resource_id

        return None, None

    async def _log_event(
        self,
        event_type: str,
        ip_address: str,
        user_agent: str,
        action: str,
        status: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        """Log audit event (non-blocking)"""
        try:
            await log_audit_event(
                event_type=event_type,
                ip_address=ip_address,
                user_agent=user_agent,
                action=action,
                status=status,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                metadata=metadata,
            )
        except Exception as e:
            # Never fail request due to audit logging errors
            logger.error(f"Failed to log audit event: {e}")
