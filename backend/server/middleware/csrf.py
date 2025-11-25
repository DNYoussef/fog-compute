"""
CSRF Protection Middleware for FastAPI
Protects against Cross-Site Request Forgery attacks
"""
import secrets
import logging
from typing import Callable, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.datastructures import Headers

logger = logging.getLogger(__name__)

# Safe HTTP methods that don't require CSRF protection
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Routes that use Bearer token authentication (they have their own protection)
# These routes don't need CSRF tokens
BEARER_AUTH_ROUTES = {
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/refresh",
    "/api/auth/logout",
}


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF Protection Middleware

    - Generates CSRF tokens and stores them in secure cookies
    - Validates CSRF token headers on state-changing requests
    - Skips validation for safe methods and Bearer-authenticated routes
    """

    def __init__(
        self,
        app,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        cookie_secure: bool = True,
        cookie_httponly: bool = True,
        cookie_samesite: str = "strict",
    ):
        """
        Initialize CSRF middleware

        Args:
            app: FastAPI application
            cookie_name: Name of the CSRF cookie
            header_name: Name of the CSRF header to validate
            cookie_secure: Whether to set Secure flag (HTTPS only)
            cookie_httponly: Whether to set HttpOnly flag
            cookie_samesite: SameSite cookie attribute (strict/lax/none)
        """
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.cookie_secure = cookie_secure
        self.cookie_httponly = cookie_httponly
        self.cookie_samesite = cookie_samesite

    def _generate_csrf_token(self) -> str:
        """Generate a cryptographically secure CSRF token"""
        return secrets.token_urlsafe(32)

    def _get_csrf_token_from_cookie(self, request: Request) -> Optional[str]:
        """Extract CSRF token from cookie"""
        return request.cookies.get(self.cookie_name)

    def _get_csrf_token_from_header(self, request: Request) -> Optional[str]:
        """Extract CSRF token from request header"""
        return request.headers.get(self.header_name)

    def _should_skip_csrf_check(self, request: Request) -> bool:
        """
        Determine if CSRF check should be skipped for this request

        Skip if:
        - Method is safe (GET, HEAD, OPTIONS)
        - Route uses Bearer token authentication
        - Route is /health or /docs
        """
        # Skip safe methods
        if request.method in SAFE_METHODS:
            return True

        # Skip health check and documentation
        path = request.url.path
        if path in {"/health", "/docs", "/redoc", "/openapi.json"}:
            return True

        # Skip routes that use Bearer token authentication
        if path in BEARER_AUTH_ROUTES:
            return True

        # Check if request has Bearer token (alternative authentication)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return True

        return False

    def _set_csrf_cookie(self, response: Response, token: str) -> None:
        """Set CSRF token in a secure cookie"""
        response.set_cookie(
            key=self.cookie_name,
            value=token,
            httponly=self.cookie_httponly,
            secure=self.cookie_secure,
            samesite=self.cookie_samesite,
            max_age=3600 * 24,  # 24 hours
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and validate CSRF token

        1. For safe methods: Generate/refresh CSRF token
        2. For state-changing methods: Validate CSRF token
        3. Set CSRF cookie in response
        """
        # Check if CSRF validation should be skipped
        if self._should_skip_csrf_check(request):
            response = await call_next(request)

            # Still set CSRF token cookie for safe methods (for future use)
            if request.method in SAFE_METHODS:
                csrf_token = self._get_csrf_token_from_cookie(request)
                if not csrf_token:
                    csrf_token = self._generate_csrf_token()
                self._set_csrf_cookie(response, csrf_token)

            return response

        # State-changing request (POST, PUT, DELETE, PATCH) - validate CSRF token
        cookie_token = self._get_csrf_token_from_cookie(request)
        header_token = self._get_csrf_token_from_header(request)

        # Check if CSRF token is missing
        if not cookie_token or not header_token:
            logger.warning(
                f"CSRF validation failed: Missing token - "
                f"path={request.url.path}, method={request.method}, "
                f"cookie_present={bool(cookie_token)}, header_present={bool(header_token)}"
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "CSRF validation failed",
                    "detail": "CSRF token is missing. Please include X-CSRF-Token header.",
                    "required_header": self.header_name,
                }
            )

        # Validate CSRF token (constant-time comparison to prevent timing attacks)
        if not secrets.compare_digest(cookie_token, header_token):
            logger.warning(
                f"CSRF validation failed: Token mismatch - "
                f"path={request.url.path}, method={request.method}"
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "CSRF validation failed",
                    "detail": "CSRF token mismatch. The token may have expired or is invalid.",
                    "required_header": self.header_name,
                }
            )

        # CSRF token is valid - process request
        logger.debug(f"CSRF validation passed: path={request.url.path}, method={request.method}")
        response = await call_next(request)

        # Refresh CSRF token in response
        self._set_csrf_cookie(response, cookie_token)

        return response
