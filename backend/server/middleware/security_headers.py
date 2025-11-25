"""
Security Headers Middleware for FastAPI
Adds security headers to all responses to protect against common web vulnerabilities
"""
import logging
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Security Headers Middleware

    Adds comprehensive security headers to all HTTP responses:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking attacks
    - X-XSS-Protection: Enables browser XSS protection
    - Strict-Transport-Security: Enforces HTTPS connections
    - Content-Security-Policy: Controls resource loading
    - Referrer-Policy: Controls referrer information leakage
    - Permissions-Policy: Restricts browser features
    """

    def __init__(
        self,
        app,
        content_type_options: str = "nosniff",
        frame_options: str = "DENY",
        xss_protection: str = "1; mode=block",
        hsts_max_age: int = 31536000,
        hsts_include_subdomains: bool = True,
        csp_policy: str = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
        referrer_policy: str = "strict-origin-when-cross-origin",
        permissions_policy: str = "geolocation=(), microphone=(), camera=()",
    ):
        """
        Initialize Security Headers Middleware

        Args:
            app: FastAPI application
            content_type_options: X-Content-Type-Options header value
            frame_options: X-Frame-Options header value (DENY, SAMEORIGIN, or ALLOW-FROM)
            xss_protection: X-XSS-Protection header value
            hsts_max_age: HSTS max-age in seconds (default: 1 year)
            hsts_include_subdomains: Whether to include subdomains in HSTS
            csp_policy: Content Security Policy directives
            referrer_policy: Referrer-Policy header value
            permissions_policy: Permissions-Policy header value
        """
        super().__init__(app)
        self.content_type_options = content_type_options
        self.frame_options = frame_options
        self.xss_protection = xss_protection
        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.csp_policy = csp_policy
        self.referrer_policy = referrer_policy
        self.permissions_policy = permissions_policy

    def _add_security_headers(self, response: Response) -> None:
        """
        Add all security headers to the response

        Args:
            response: Response object to add headers to
        """
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = self.content_type_options

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = self.frame_options

        # Enable XSS protection (legacy header, but still used by older browsers)
        response.headers["X-XSS-Protection"] = self.xss_protection

        # Enforce HTTPS (only add if not localhost)
        hsts_value = f"max-age={self.hsts_max_age}"
        if self.hsts_include_subdomains:
            hsts_value += "; includeSubDomains"
        response.headers["Strict-Transport-Security"] = hsts_value

        # Content Security Policy
        response.headers["Content-Security-Policy"] = self.csp_policy

        # Control referrer information
        response.headers["Referrer-Policy"] = self.referrer_policy

        # Restrict browser features (geolocation, camera, microphone)
        response.headers["Permissions-Policy"] = self.permissions_policy

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and add security headers to response

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response with security headers added
        """
        # Process the request
        response = await call_next(request)

        # Add security headers to all responses
        self._add_security_headers(response)

        logger.debug(
            f"Security headers added: path={request.url.path}, "
            f"method={request.method}, status={response.status_code}"
        )

        return response
