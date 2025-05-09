"""Tests for the web server authentication module."""

from unittest.mock import MagicMock, mock_open, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from nekoconf.server.auth import AuthMiddleware, NekoAuthGuard


@pytest.fixture
def auth_guard():
    """Create an authentication guard for testing."""
    return NekoAuthGuard(api_key="test_key")


@pytest.fixture
def auth_middleware(auth_guard):
    """Create an authentication middleware for testing."""
    return AuthMiddleware(app=MagicMock(), auth=auth_guard)


@pytest.fixture
def authenticated_app():
    """Create a FastAPI app with authentication for testing."""
    app = FastAPI()
    guard = NekoAuthGuard(api_key="test_key")
    app.add_middleware(AuthMiddleware, auth=guard)

    @app.get("/test")
    def test_endpoint():
        return {"status": "ok"}

    @app.get("/")
    def root_endpoint():
        return {"status": "ok"}

    @app.get("/login.html")
    def login_page():
        return JSONResponse(
            content={"message": "Login page"},
            status_code=302,
            headers={"Location": "/test/login.html"},
        )

    return TestClient(app)


class TestAuthGuard:
    """Tests for the NekoAuthGuard class."""

    def test_init_with_api_key(self):
        """Test initializing with an API key."""
        guard = NekoAuthGuard(api_key="test_key")
        assert guard.api_key == "test_key"

    def test_init_without_api_key(self):
        """Test initializing without an API key."""
        guard = NekoAuthGuard()
        assert guard.api_key is None

    def test_set_api_key(self):
        """Test setting an API key."""
        guard = NekoAuthGuard()
        guard.set_api_key("new_key")
        assert guard.api_key == "new_key"

    def test_set_empty_api_key(self):
        """Test setting an empty API key."""
        guard = NekoAuthGuard(api_key="test_key")
        with pytest.raises(ValueError):
            guard.set_api_key("")

    def test_verify_session_cookie(self):
        """Test verifying a session cookie."""
        guard = NekoAuthGuard(api_key="test_key")
        request = MagicMock()
        request.cookies = {"nekoconf_api_key": "test_key"}
        assert guard.verify_session_cookie(request) is True

    def test_verify_session_cookie_wrong_key(self):
        """Test verifying a session cookie with wrong key."""
        guard = NekoAuthGuard(api_key="test_key")
        request = MagicMock()
        request.cookies = {"nekoconf_api_key": "wrong_key"}
        assert guard.verify_session_cookie(request) is False

    def test_verify_session_cookie_no_key_needed(self):
        """Test verifying a session cookie when no key is needed."""
        guard = NekoAuthGuard()
        request = MagicMock()
        request.cookies = {}
        assert guard.verify_session_cookie(request) is True

    @pytest.mark.asyncio
    async def test_verify_api_key(self, auth_guard):
        """Test verifying an API key."""
        # Valid key
        assert await auth_guard.verify_api_key("test_key") is True
        # Bearer prefix
        assert await auth_guard.verify_api_key("Bearer test_key") is True

    @pytest.mark.asyncio
    async def test_verify_api_key_wrong_key(self, auth_guard):
        """Test verifying a wrong API key."""
        with pytest.raises(Exception) as excinfo:
            await auth_guard.verify_api_key("wrong_key")
        assert "Unauthorized" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_verify_api_key_no_key_provided(self, auth_guard):
        """Test verifying when no API key is provided."""
        with pytest.raises(Exception) as excinfo:
            await auth_guard.verify_api_key(None)
        assert "Unauthorized" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_verify_api_key_no_key_needed(self):
        """Test verifying an API key when no key is needed."""
        guard = NekoAuthGuard()
        assert await guard.verify_api_key(None) is True
        assert await guard.verify_api_key("any_key") is True


async def test_response_handler(request: Request):
    """Mock response handler for testing."""
    return "success"


class TestAuthMiddleware:
    """Tests for the AuthMiddleware class."""

    @pytest.mark.asyncio
    async def test_dispatch_no_auth_needed(self):
        """Test dispatching a request when no auth is needed."""
        guard = NekoAuthGuard()  # No API key configured
        app = MagicMock()
        middleware = AuthMiddleware(app=app, auth=guard)
        request = MagicMock()
        result = await middleware.dispatch(request, test_response_handler)
        app.assert_not_called()  # App shouldn't be called directly

        assert result is "success"

    @pytest.mark.asyncio
    async def test_dispatch_with_options_request(self, auth_middleware):
        """Test dispatching an OPTIONS request for CORS preflight."""
        request = MagicMock()
        request.method = "OPTIONS"
        result = await auth_middleware.dispatch(request, test_response_handler)
        # The next handler should be called without checking auth

        assert result is "success"

    @pytest.mark.asyncio
    async def test_dispatch_excluded_path(self, auth_middleware):
        """Test dispatching a request to an excluded path."""
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/docs"
        result = await auth_middleware.dispatch(request, test_response_handler)
        # The next handler should be called without checking auth
        assert result is "success"

    def test_api_endpoint_no_auth(self, authenticated_app):
        """Test accessing an API endpoint without authentication."""
        response = authenticated_app.get("/test")
        assert response.status_code == 403
        assert "Unauthorized" in response.text

    def test_api_endpoint_with_auth_header(self, authenticated_app):
        """Test accessing an API endpoint with authentication header."""
        response = authenticated_app.get("/test", headers={"Authorization": "Bearer test_key"})
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_api_endpoint_with_auth_cookie(self, authenticated_app):
        """Test accessing an API endpoint with authentication cookie."""
        authenticated_app.cookies.set("nekoconf_api_key", "test_key")
        response = authenticated_app.get("/test")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_root_path_no_auth(self, authenticated_app):
        """Test accessing the root path without authentication."""
        response = authenticated_app.get("/")
        assert response.status_code == 403
        assert "Unauthorized" in response.text

    @pytest.mark.asyncio
    async def test_login_page_redirect(self, auth_middleware):
        """Test generating a login page."""
        request = MagicMock()
        request.url.path = "/test"

        # Use patch to mock the importlib.resources.files function
        html_content = "<html>{{ return_path }}</html>"

        with patch("importlib.resources.files") as mock_files:
            # Mock the file path and its open method
            mock_file_path = MagicMock()
            mock_file_path.open.return_value.__enter__.return_value.read.return_value = html_content
            mock_files.return_value.__truediv__.return_value.__truediv__.return_value = (
                mock_file_path
            )

            # Generate the login page
            response = auth_middleware._generate_login_page(request)

            # Check response content, redirection, and status code
            assert response.status_code == 302
            assert response.headers["Location"] == "/test/login.html"
