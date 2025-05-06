"""
Authentication module for NekoConf.
Provides authentication mechanisms and middleware.
"""

import importlib.resources
import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, JSONResponse

from nekoconf.utils.helper import getLogger


class NekoAuthGuard:
    """Centralized authentication manager for NekoConfigServer"""

    def __init__(self, api_key=None):
        """
        Initialize the authentication manager.

        Args:
            api_key: Optional API key for authentication. If not provided, no key is required.
        """
        self.api_key: str = api_key

    def set_api_key(self, api_key: str):
        """
        Set the API key for authentication.

        Args:
            api_key: The API key
        """
        if not api_key:
            raise ValueError("API key cannot be empty")
        self.api_key = api_key

    async def verify_api_key(
        self,
        api_key: str = Depends(APIKeyHeader(name="Authorization", auto_error=False)),
    ):
        """
        Verify the API key if one is configured.

        Returns:
            bool: True if valid or no key configured, False otherwise
        """
        configured_key = self.api_key

        # No API key required if none is configured
        if not configured_key:
            return True

        # API key required but not provided
        if not api_key:
            raise HTTPException(status_code=401, detail="Unauthorized: API key required")

        # Strip "Bearer " prefix if present
        if api_key.startswith("Bearer "):
            api_key = api_key[7:]

        # API key provided but invalid
        if api_key != configured_key:
            raise HTTPException(status_code=403, detail="Unauthorized: Insufficient Permissions")

        return True

    def create_middleware(self):
        """
        Create a new instance of AuthMiddleware.

        Returns:
            AuthMiddleware: A middleware instance configured with this auth manager
        """
        return lambda app: AuthMiddleware(app, self)

    def verify_session_cookie(self, request: Request):
        """
        Verify if the session cookie contains a valid API key.

        Args:
            request: The FastAPI request

        Returns:
            bool: True if valid, False otherwise
        """
        configured_key = self.api_key
        if not configured_key:
            return True

        # Get API key from session cookie
        cookie_key = request.cookies.get("nekoconf_api_key", "")

        # Trim any whitespace that might be added by some browsers
        cookie_key = cookie_key.strip() if cookie_key else ""

        # Validate the key
        return cookie_key == configured_key


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for FastAPI applications"""

    def __init__(self, app, auth: NekoAuthGuard, logger: Optional[logging.Logger] = None):
        super().__init__(app)
        self.auth = auth
        self.logger = logger or getLogger(__name__)

    async def dispatch(self, request: Request, call_next):
        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip auth for specific paths if needed
        excluded_paths = ["/docs", "/redoc", "/openapi.json", "/health"]
        if any(request.url.path.startswith(path) for path in excluded_paths):
            return await call_next(request)

        configured_key = self.auth.api_key

        # No API key required if none is configured
        if not configured_key:
            return await call_next(request)

        # First, check for valid session cookie
        if self.auth.verify_session_cookie(request):
            return await call_next(request)

        # Then, check for valid Authorization header
        api_key = request.headers.get("Authorization", "")
        if api_key.startswith("Bearer "):
            api_key = api_key[7:]

        if api_key and api_key == configured_key:
            return await call_next(request)

        # Check if the path is a root-level config UI "http://<host>" path
        path = request.url.path
        if not path or path == "/":
            # For Config UI access, redirect to login page
            return self._generate_login_page(request)

        # For API and other paths, return JSON error
        return JSONResponse(
            status_code=403,
            content={"error": "Unauthorized: NekoConf - Invalid API key"},
        )

    def _generate_login_page(self, request: Request):
        """Generate a login page for the config ui"""
        # load the login HTML template using importlib.resources
        try:
            # Adjusted path for the 'web' subpackage
            template_path = importlib.resources.files("nekoconf.server") / "html" / "login.html"
            with template_path.open("r") as f:
                html_content = f.read()
        except (FileNotFoundError, TypeError, ImportError) as e:
            # Log an error and return a generic error response
            self.logger.error(
                f"Login page template not found or cannot be loaded - {e} traceback: {e.__traceback__}"
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error: Login page unavailable"},
            )

        # Replace placeholders in the HTML template
        html_content = html_content.replace("{{ return_path }}", request.url.path)
        return HTMLResponse(content=html_content, status_code=401)
