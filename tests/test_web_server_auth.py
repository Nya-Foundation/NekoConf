"""Tests for NekoConf authentication."""

import base64

from fastapi.testclient import TestClient

from nekoconf.server import NekoConf


def test_no_auth_required(test_client):
    """Test that endpoints work without authentication when no password is set."""
    # No auth should work when password is not set
    response = test_client.get("/api/config")
    assert response.status_code == 200


def test_auth_required(web_server_with_auth):
    """Test that endpoints require authentication when password is set."""
    # Create a client without auth headers
    unauthenticated_client = TestClient(web_server_with_auth.app)

    # Request without auth should fail
    response = unauthenticated_client.get("/api/config")
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    assert response.headers["WWW-Authenticate"] == "Basic"

    # Request with invalid credentials should fail
    auth_header = {"Authorization": f"Basic {base64.b64encode(b'wrong:credentials').decode()}"}
    response = unauthenticated_client.get("/api/config", headers=auth_header)
    assert response.status_code == 401

    # Request with valid credentials should succeed
    auth_header = {"Authorization": f"Basic {base64.b64encode(b'testuser:testpass').decode()}"}
    response = unauthenticated_client.get("/api/config", headers=auth_header)
    assert response.status_code == 200


def test_auth_required_for_all_endpoints(test_client_with_no_auth):
    """Test that all API endpoints require authentication when password is set."""
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
            response.status_code == 401
        ), f"Endpoint {method} {endpoint} should require authentication"

    # Web UI endpoints should also require authentication
    response = test_client_with_no_auth.get("/")
    assert response.status_code == 401


def test_auth_with_curl_compatible_format(config_manager):
    """Test that authentication works with curl-compatible format."""
    # Create a server with authentication
    server = NekoConf(config_manager, username="admin", password="secret")
    client = TestClient(server.app)

    # Test with curl-compatible auth format
    auth_header = {"Authorization": "Basic YWRtaW46c2VjcmV0"}  # base64 of "admin:secret"
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
