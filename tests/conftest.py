"""Shared test fixtures for NekoConf tests."""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
from fastapi.testclient import TestClient

from nekoconf.core.client import NekoConfigClient
from nekoconf.core.config import NekoConfigManager
from nekoconf.core.eval import NekoSchemaValidator
from nekoconf.server.app import NekoConfigServer
from tests.test_helpers import ConfigTestHelper

# Configure pytest to handle async by default
pytest_plugins = ["pytest_asyncio"]


# Set asyncio mode
@pytest.fixture(autouse=True)
def anyio_backend():
    """Set the anyio backend to asyncio."""
    return "asyncio"


# Test constants
TEST_API_KEY = "test-api-key"
TEST_TIMEOUT = 0.2


# Example file fixtures - session scoped for efficiency
@pytest.fixture(scope="session")
def examples_dir() -> Path:
    """Get the path to the examples directory."""
    return Path(__file__).parent.parent / "examples"


@pytest.fixture(scope="session")
def example_configs(examples_dir) -> Dict[str, Path]:
    """Get all example configuration files."""
    return ConfigTestHelper.get_example_configs()


@pytest.fixture(scope="session")
def example_schemas(examples_dir) -> Dict[str, Path]:
    """Get all example schema files."""
    return ConfigTestHelper.get_example_schemas()


@pytest.fixture
def example_config_path(example_configs) -> Optional[Path]:
    """Get the path to the default example config file."""
    if not example_configs:
        return None
    return example_configs.get("app_config", next(iter(example_configs.values()), None))


@pytest.fixture
def example_schema_path(example_schemas) -> Optional[Path]:
    """Get the path to the default example schema file."""
    if not example_schemas:
        return None
    return example_schemas.get("app_config", next(iter(example_schemas.values()), None))


# Sample configuration fixtures
@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Create a sample configuration for testing."""
    return {
        "server": {"host": "localhost", "port": 8000, "debug": True},
        "database": {"url": "sqlite:///test.db", "pool_size": 5},
    }


@pytest.fixture
def complex_sample_config() -> Dict[str, Any]:
    """Create a more complex sample configuration for testing."""
    return {
        "server": {
            "host": "localhost",
            "port": 8080,
            "debug": True,
            "timeout": 30.5,
            "features": ["api", "admin", "docs"],
            "settings": {"cache": True, "max_connections": 100},
        },
        "database": {
            "url": "sqlite:///test.db",
            "pool_size": 5,
            "credentials": {"username": "admin", "password": "secret"},
        },
        "logging": {"level": "INFO", "file": "/var/log/app.log"},
    }


@pytest.fixture
def sample_schema() -> Dict[str, Any]:
    """Create a sample JSON Schema for testing."""
    return {
        "type": "object",
        "required": ["server"],
        "properties": {
            "server": {
                "type": "object",
                "required": ["host", "port"],
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                    "debug": {"type": "boolean"},
                },
            },
            "database": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "pool_size": {"type": "integer", "minimum": 1},
                },
            },
            "logging": {
                "type": "object",
                "properties": {
                    "level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR"]}
                },
            },
        },
    }


# Temporary file fixtures
@pytest.fixture
def config_file(tmp_path, sample_config) -> Path:
    """Create a temporary configuration file."""
    return ConfigTestHelper.create_temp_config(tmp_path, sample_config)


@pytest.fixture
def complex_config_file(tmp_path, complex_sample_config) -> Path:
    """Create a temporary configuration file with complex data."""
    return ConfigTestHelper.create_temp_config(tmp_path, complex_sample_config)


@pytest.fixture
def temp_json_file(tmp_path, sample_config) -> Path:
    """Create a temporary JSON configuration file."""
    return ConfigTestHelper.create_temp_json_config(tmp_path, sample_config)


@pytest.fixture
def schema_file(tmp_path, sample_schema) -> Path:
    """Create a temporary schema file."""
    return ConfigTestHelper.create_temp_schema(tmp_path, sample_schema)


@pytest.fixture
def test_config_file():
    """Fixture providing a temporary configuration file."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)

    # Yield the path for use in the test
    yield Path(path)

    # Cleanup after the test
    try:
        os.unlink(path)
    except (OSError, PermissionError):
        pass


@pytest.fixture
def error_config() -> Dict[str, Any]:
    """Create an invalid configuration that should raise multiple validation errors."""
    return {
        "server": {
            "host": 123,  # Should be string
            "port": "8000",  # Should be integer
            "debug": "invalid",  # Should be boolean
        },
        "database": {
            "url": "not-a-url",  # Invalid URL format
            "pool_size": -1,  # Should be positive
            "timeout": "invalid",  # Should be number
        },
    }


@pytest.fixture
def edge_case_config() -> Dict[str, Any]:
    """Create a configuration with edge cases for testing."""
    return {
        "empty_dict": {},
        "empty_list": [],
        "null_value": None,
        "nested": {"very": {"deep": {"structure": True}}},
        "special_chars": "!@#$%^&*()",
        "unicode": "こんにちは",
        "numbers": {"zero": 0, "negative": -1, "float": 3.14159, "scientific": 1e-10},
    }


@pytest.fixture
def error_schema() -> Dict[str, Any]:
    """Create an invalid schema for testing error handling."""
    return {
        "type": "invalid_type",
        "properties": {
            "test": {
                "type": "string",
                "pattern": "[",  # Invalid regex pattern
            }
        },
    }


# Core component fixtures
@pytest.fixture
def config_manager(test_config_file, sample_config):
    """Create a NekoConfig instance for testing."""

    # Initialize the config manager with the test file
    config = NekoConfigManager(config_path=test_config_file)
    config.update(sample_config)
    config.save()

    return config


@pytest.fixture
def config_manager_with_schema(config_file, schema_file):
    """Create a NekoConfig instance with schema for testing."""
    manager = NekoConfigManager(config_file, schema_file)
    manager.load()
    return manager


@pytest.fixture
def validator(sample_schema) -> NekoSchemaValidator:
    """Create a NekoValidator instance."""
    return NekoSchemaValidator(sample_schema)


@pytest.fixture
def web_server(config_manager) -> NekoConfigServer:
    """Create a NekoConf instance for testing."""
    return NekoConfigServer(config_manager)


@pytest.fixture
def web_server_with_auth(config_manager) -> NekoConfigServer:
    """Create a NekoConf instance with authentication for testing."""
    return NekoConfigServer(config_manager, api_key="test-api-key")


@pytest.fixture
def test_client(web_server) -> TestClient:
    """Create a TestClient instance for the FastAPI app without authentication."""
    return TestClient(web_server.app)


@pytest.fixture
def test_client_with_no_auth(web_server_with_auth) -> TestClient:
    """Create a TestClient instance for the FastAPI app without authentication."""
    return TestClient(web_server_with_auth.app)


@pytest.fixture
def test_client_with_auth(web_server_with_auth) -> TestClient:
    """Create a TestClient instance for the FastAPI app with authentication."""
    client = TestClient(web_server_with_auth.app)
    # Add default authentication headers to every request
    client.headers.update({"Authorization": "test-api-key"})
    return client


@pytest.fixture
def config_api(config_file) -> NekoConfigClient:
    """Create a NekoConfigClient instance for testing."""
    return NekoConfigClient(config_file)


@pytest.fixture
def config_api_with_schema(config_file, schema_file) -> NekoConfigClient:
    """Create a NekoConfigClient instance with schema for testing."""
    return NekoConfigClient(config_file, schema_file)


@pytest.fixture
def valid_config():
    """Create a valid configuration according to the sample schema."""
    return {
        "server": {"host": "localhost", "port": 8000, "debug": True},
        "database": {"url": "sqlite:///test.db", "pool_size": 5},
        "logging": {"level": "INFO"},
    }


@pytest.fixture
def invalid_config():
    """Create an invalid configuration with various errors."""
    return {
        "server": {
            "host": "localhost",
            "port": "8000",  # Should be integer
            "debug": "true",  # Should be boolean
        },
        "database": {"url": "invalid url", "pool_size": 0},  # Should be >= 1
        "logging": {"level": "TRACE"},  # Not in enum
    }
