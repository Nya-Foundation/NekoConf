"""Shared test fixtures for NekoConf tests."""

import json
import os
import pytest
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from nekoconf.config_manager import ConfigManager
from nekoconf.schema_validator import SchemaValidator
from nekoconf.web_server import WebServer
from nekoconf.api import ConfigAPI
from fastapi.testclient import TestClient

from tests.test_helpers import ConfigTestHelper, SyncObserver, AsyncObserver


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


# Core component fixtures
@pytest.fixture
def config_manager(config_file) -> ConfigManager:
    """Create a ConfigManager instance for testing."""
    manager = ConfigManager(config_file)
    manager.load()
    return manager


@pytest.fixture
def config_manager_with_schema(config_file, schema_file) -> ConfigManager:
    """Create a ConfigManager instance with schema for testing."""
    manager = ConfigManager(config_file, schema_file)
    manager.load()
    return manager


@pytest.fixture
def validator(sample_schema) -> SchemaValidator:
    """Create a SchemaValidator instance."""
    return SchemaValidator(sample_schema)


@pytest.fixture
def web_server(config_manager) -> WebServer:
    """Create a WebServer instance for testing."""
    return WebServer(config_manager)


@pytest.fixture
def test_client(web_server) -> TestClient:
    """Create a TestClient instance for the FastAPI app."""
    return TestClient(web_server.app)


@pytest.fixture
def config_api(config_file) -> ConfigAPI:
    """Create a ConfigAPI instance for testing."""
    return ConfigAPI(config_file)


@pytest.fixture
def config_api_with_schema(config_file, schema_file) -> ConfigAPI:
    """Create a ConfigAPI instance with schema for testing."""
    return ConfigAPI(config_file, schema_file)


# Observer fixtures
@pytest.fixture
def sync_observer() -> SyncObserver:
    """Create a SyncObserver instance for testing."""
    return SyncObserver()


@pytest.fixture
def async_observer() -> AsyncObserver:
    """Create an AsyncObserver instance for testing."""
    return AsyncObserver()


# Cleanup fixture to reset observers between tests
@pytest.fixture(autouse=True)
def reset_observers(sync_observer, async_observer):
    """Reset observers between tests."""
    yield
    if hasattr(sync_observer, "reset"):
        sync_observer.reset()
    if hasattr(async_observer, "reset"):
        async_observer.reset()


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
