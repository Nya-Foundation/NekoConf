"""Tests for NekoConf authentication."""

import base64

from fastapi.testclient import TestClient

from nekoconf.server.app import NekoConfigServer


def test_no_auth_required(test_client):
    """Test that endpoints work without authentication when no API key is set."""
    # No auth should work when API key is not set
    response = test_client.get("/api/config")
    assert response.status_code == 200


def test_auth_required(web_server_with_auth):
    """Test that endpoints require authentication when API key is set."""
    # Create a client without auth headers
    unauthenticated_client = TestClient(web_server_with_auth.app)

    # Request without auth should fail
    response = unauthenticated_client.get("/api/config")
    assert response.status_code == 403

    # Request with invalid API key should fail
    auth_header = {"Authorization": "wrong-api-key"}
    response = unauthenticated_client.get("/api/config", headers=auth_header)
    assert response.status_code == 403

    # Request with valid API key should succeed
    auth_header = {"Authorization": "test-api-key"}
    response = unauthenticated_client.get("/api/config", headers=auth_header)
    assert response.status_code == 200


def test_auth_required_for_all_endpoints(test_client_with_no_auth):
    """Test that all API endpoints require authentication when API key is set."""
    endpoints = [
        ("/api/config", "GET"),
        ("/api/config/server", "GET"),
        ("/api/config", "POST"),
        ("/api/config/server", "POST"),
        ("/api/config/server", "DELETE"),
        ("/api/config/reload", "POST"),
        ("/api/config/validate", "POST"),
    ]

    for endpoint, method in endpoints:
        request_method = getattr(test_client_with_no_auth, method.lower())
        response = request_method(endpoint)
        assert (
            response.status_code == 403
        ), f"Endpoint {method} {endpoint} should require authentication"

    # Web UI endpoints should also require authentication
    response = test_client_with_no_auth.get("/")
    assert response.status_code == 401


def test_auth_with_bearer_format(config_manager):
    """Test that authentication works with Bearer token format."""
    # Create a server with authentication
    server = NekoConfigServer(config_manager, api_key="secret-token")
    client = TestClient(server.app)

    # Test with Bearer token format
    auth_header = {"Authorization": "Bearer secret-token"}
    response = client.get("/api/config", headers=auth_header)
    assert response.status_code == 200


def test_auth_with_plain_token(config_manager):
    """Test that authentication works with plain token format."""
    # Create a server with authentication
    server = NekoConfigServer(config_manager, api_key="secret-token")
    client = TestClient(server.app)

    # Test with plain token format
    auth_header = {"Authorization": "secret-token"}
    response = client.get("/api/config", headers=auth_header)
    assert response.status_code == 200


def test_auth_works_with_default_credentials(test_client_with_auth):
    """Test that endpoints work with the default auth credentials in the fixture."""
    # This should work because test_client_with_auth already has credentials
    response = test_client_with_auth.get("/api/config")
    assert response.status_code == 200

    # Other endpoints should also work
    response = test_client_with_auth.get("/api/config/server")
    assert response.status_code == 200

    # POST requests should work too
    response = test_client_with_auth.post("/api/config/reload")
    assert response.status_code == 200


def test_auth_with_session_cookie(config_manager):
    """Test that authentication works with session cookie."""
    # Create a server with authentication
    server = NekoConfigServer(config_manager, api_key="cookie-token")
    client = TestClient(server.app)

    # Set session cookie
    client.cookies.set("nekoconf_api_key", "cookie-token")

    # Request should succeed with valid cookie
    response = client.get("/api/config")
    assert response.status_code == 200
