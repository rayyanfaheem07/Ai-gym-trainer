from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that appends security headers to all HTTP responses.
    Carefully configured to support local development, Next.js, WebSockets, and camera permissions.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking / iframe embedding
        response.headers["X-Frame-Options"] = "DENY"

        # Referrer privacy policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Legacy XSS filter protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Permissions policy explicitly allowing camera for web pose detection
        response.headers["Permissions-Policy"] = "camera=(self)"

        # Only add HSTS when request is over HTTPS to avoid breaking local HTTP development
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
