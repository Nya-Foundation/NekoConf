import os
from pathlib import Path

import pytest

from nekoconf import NekoConfigManager
from nekoconf.utils.helper import save_file

# --- Test Fixtures ---


@pytest.fixture
def temp_config_file(tmp_path):
    """Creates a temporary config file for testing."""
    config_path = tmp_path / "test_config.yaml"
    initial_data = {
        "service": {
            "name": "TestService",
            "port": 8080,
            "enabled": True,
            "timeouts": {"read": 5, "write": 10},
        },
        "database": {
            "host": "localhost",
            "port": 5432,
            "credentials": {"user": "default_user"},
        },
        "feature_flags": ["flag1", "flag2"],
        "debug_mode": False,
        "log_level": "INFO",
    }
    save_file(config_path, initial_data)
    return config_path


@pytest.fixture(autouse=True)
def manage_environment_variables():
    """Cleans up environment variables before and after each test."""
    original_environ = os.environ.copy()
    yield  # Run the test
    os.environ.clear()
    os.environ.update(original_environ)


# --- Test Cases ---


def test_basic_override(temp_config_file):
    """Test basic environment variable override."""
    os.environ["NEKOCONF_SERVICE_PORT"] = "9090"  # String value
    os.environ["NEKOCONF_DEBUG_MODE"] = "true"  # String value for boolean

    manager = NekoConfigManager(temp_config_file)  # Default prefix NEKOCONF_

    assert manager.get("service.port") == 9090  # Parsed as int
    assert manager.get("debug.mode") is True  # Parsed as bool
    assert manager.get("service.name") == "TestService"  # Unchanged


def test_nested_override(temp_config_file):
    """Test override of a nested key."""
    os.environ["NEKOCONF_DATABASE_CREDENTIALS_USER"] = "test_user"

    manager = NekoConfigManager(temp_config_file)

    assert manager.get("database.credentials.user") == "test_user"
    assert manager.get("database.host") == "localhost"  # Unchanged parent


def test_custom_prefix(temp_config_file):
    """Test using a custom prefix for environment variables."""
    os.environ["MYAPP_SERVICE_PORT"] = "9999"
    os.environ["NEKOCONF_SERVICE_PORT"] = "1111"  # Should be ignored

    manager = NekoConfigManager(temp_config_file, env_prefix="MYAPP")

    assert manager.get("service.port") == 9999


def test_custom_delimiter(temp_config_file):
    """Test using a custom delimiter for nested keys."""
    os.environ["NEKOCONF_SERVICE_PORT"] = "7777"  # Using single underscore

    manager = NekoConfigManager(temp_config_file, env_nested_delimiter="_")

    assert manager.get("service.port") == 7777


def test_override_disabled(temp_config_file):
    """Test that overrides are disabled when requested."""
    os.environ["NEKOCONF_SERVICE_PORT"] = "9090"

    manager = NekoConfigManager(temp_config_file, env_override_enabled=False)

    assert manager.get("service.port") == 8080  # Original value


def test_type_parsing(temp_config_file):
    """Test parsing of various types from environment variables."""
    os.environ["NEKOCONF_SERVICE_PORT"] = "9091"
    os.environ["NEKOCONF_SERVICE_ENABLED"] = "false"
    os.environ["NEKOCONF_DATABASE_PORT"] = "5433.5"  # Float
    os.environ["NEKOCONF_FEATURE_FLAGS"] = '["new_flag", "flag3"]'  # JSON list
    os.environ["NEKOCONF_DATABASE_CREDENTIALS"] = (
        '{"user": "env_user", "pass": "env_pass"}'  # JSON dict
    )

    manager = NekoConfigManager(temp_config_file)

    assert manager.get("service.port") == 9091
    assert manager.get("service.enabled") is False
    assert manager.get("database.port") == 5433.5
    assert manager.get("feature.flags") == ["new_flag", "flag3"]
    assert manager.get("database.credentials") == {
        "user": "env_user",
        "pass": "env_pass",
    }


def test_exclusion(temp_config_file):
    """Test excluding specific keys from override."""
    os.environ["NEKOCONF_SERVICE_PORT"] = "9090"
    os.environ["NEKOCONF_DATABASE_HOST"] = "remote-db"
    os.environ["NEKOCONF_DATABASE_PORT"] = "9999"  # This should be excluded

    manager = NekoConfigManager(
        temp_config_file,
        env_exclude_paths=[
            "database.port",
            "service.name",
        ],  # Exclude specific key and another non-set one
    )

    assert manager.get("service.port") == 9090  # Overridden
    assert manager.get("database.host") == "remote-db"  # Overridden
    assert manager.get("database.port") == 5432  # Excluded, keeps original value


def test_exclusion_nested_parent(temp_config_file):
    """Test excluding a parent key excludes children."""
    os.environ["NEKOCONF_DATABASE_HOST"] = "remote-db"
    os.environ["NEKOCONF_DATABASE_CREDENTIALS_USER"] = "env_user"  # Child of excluded parent

    manager = NekoConfigManager(
        temp_config_file,
        env_exclude_paths=["database"],  # Exclude the whole database section
    )

    assert manager.get("database.host") == "localhost"  # Excluded
    assert manager.get("database.credentials.user") == "default_user"  # Excluded (child)


def test_inclusion(temp_config_file):
    """Test including only specific keys for override."""
    os.environ["NEKOCONF_SERVICE_PORT"] = "9090"  # Included
    os.environ["NEKOCONF_DATABASE_HOST"] = "remote-db"  # Not included
    os.environ["NEKOCONF_DEBUG_MODE"] = "true"  # Included

    manager = NekoConfigManager(
        temp_config_file,
        env_include_paths=["service.port", "debug.mode"],  # Only allow these
    )

    assert manager.get("service.port") == 9090  # Included -> Overridden
    assert manager.get("database.host") == "localhost"  # Not included -> Original
    assert manager.get("debug_mode") is False  # Included -> Overridden


def test_inclusion_nested_parent(temp_config_file):
    """Test including a parent key allows children to be overridden."""
    os.environ["NEKOCONF_DATABASE_HOST"] = "remote-db"  # Child of included parent
    os.environ["NEKOCONF_DATABASE_CREDENTIALS_USER"] = "env_user"  # Child of included parent
    os.environ["NEKOCONF_SERVICE_PORT"] = "9090"  # Not included

    manager = NekoConfigManager(
        temp_config_file,
        env_include_paths=["database"],  # Include the whole database section
    )

    assert manager.get("database.host") == "remote-db"  # Included (child) -> Overridden
    assert manager.get("database.credentials.user") == "env_user"  # Included (child) -> Overridden
    assert manager.get("service.port") == 8080  # Not included -> Original


def test_include_exclude_precedence(temp_config_file):
    """Test that exclusion takes precedence over inclusion."""
    os.environ["NEKOCONF_DATABASE_HOST"] = (
        "remote-db"  # Included by 'database', Excluded by 'database.host'
    )
    os.environ["NEKOCONF_DATABASE_PORT"] = "9999"  # Included by 'database'

    manager = NekoConfigManager(
        temp_config_file,
        env_include_paths=["database"],  # Include database section
        env_exclude_paths=["database.host"],  # Exclude specific host key
    )

    assert manager.get("database.host") == "localhost"  # Excluded wins -> Original
    assert manager.get("database.port") == 9999  # Included, not excluded -> Overridden


def test_reload_applies_overrides(temp_config_file):
    """Test that calling load() again re-applies overrides."""
    manager = NekoConfigManager(temp_config_file)
    assert manager.get("service.port") == 8080

    # Set env var *after* initial load
    os.environ["NEKOCONF_SERVICE_PORT"] = "7070"

    # Reload the configuration
    manager.load()

    assert manager.get("service.port") == 7070  # Should now reflect the override
