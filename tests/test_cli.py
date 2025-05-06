"""Tests for the command-line interface."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from nekoconf.cli.main import (
    _create_parser,
    _format_output,
    handle_connect_command,
    handle_delete_command,
    handle_get_command,
    handle_import_command,
    handle_init_command,
    handle_server_command,
    handle_set_command,
    handle_validate_command,
    main,
)


@pytest.fixture
def config_file(tmp_path):
    """Create a temporary config file for testing."""
    config_data = {
        "server": {
            "host": "localhost",
            "port": 8000,
            "debug": True,
        },
        "database": {
            "host": "localhost",
            "port": 5432,
            "name": "testdb",
            "username": "user",
            "password": "pass",
        },
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    return config_file


@pytest.fixture
def schema_file(tmp_path):
    """Create a temporary schema file for testing."""
    schema_data = {
        "type": "object",
        "properties": {
            "server": {
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                    "debug": {"type": "boolean"},
                },
                "required": ["host", "port"],
            },
        },
    }
    schema_file = tmp_path / "schema.json"
    with open(schema_file, "w") as f:
        json.dump(schema_data, f)
    return schema_file


@pytest.fixture
def logger():
    """Create a logger fixture for testing."""
    return MagicMock()


def test_create_parser():
    """Test creating the argument parser."""
    parser = _create_parser()

    # Check that all expected commands are present
    commands = [
        "server",
        "get",
        "set",
        "delete",
        "import",
        "validate",
        "init",
        "connect",
    ]

    for command in commands:
        # Ensure each command has a subparser
        assert any(
            subparser.dest == "command" and command in subparser.choices
            for subparser in parser._subparsers._group_actions
        )


# Test server command when dependencies are available
@patch("nekoconf.cli.main.HAS_SERVER_DEPS", True)
@patch("nekoconf.cli.main.NekoConfigManager")
@patch("nekoconf.cli.main.NekoConfigServer")
def test_handle_server_command_with_deps(mock_server, mock_config_manager, logger):
    """Test the server command handler with available dependencies."""
    # Create args object
    args = MagicMock()
    args.config = "config.yaml"
    args.host = "0.0.0.0"
    args.port = 8000
    args.schema = None
    args.reload = False
    args.api_key = None
    args.read_only = False

    # Handle command
    result = handle_server_command(args, logger)

    # Check server was created and run
    mock_server.assert_called_once()
    mock_server.return_value.run.assert_called_once_with(host="0.0.0.0", port=8000, reload=False)

    # Should return success
    assert result == 0


# Test server command when dependencies are missing
@patch("nekoconf.cli.main.HAS_SERVER_DEPS", False)
def test_handle_server_command_missing_deps(logger):
    """Test the server command handler when server dependencies are missing."""
    # Create args object
    args = MagicMock()
    args.config = "config.yaml"
    args.host = "0.0.0.0"
    args.port = 8000
    args.schema = None
    args.reload = False
    args.api_key = None
    args.read_only = False

    # Handle command
    result = handle_server_command(args, logger)

    # Should return error code
    assert result == 1


def test_handle_get_command(config_file, logger):
    """Test the get command handler."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.key = "server.host"
    args.format = "raw"
    args.remote_url = None
    args.remote_api_key = None
    args.in_memory = False

    # Mock the print function
    with patch("builtins.print") as mock_print:
        # Handle command
        result = handle_get_command(args, logger)

        # Should return success
        assert result == 0

        # Should print the value
        mock_print.assert_called_once()


def test_handle_set_command(config_file, logger):
    """Test the set command handler."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.key = "server.host"
    args.value = "0.0.0.0"
    args.schema = None
    args.remote_url = None
    args.remote_api_key = None
    args.remote_read_only = False
    args.in_memory = False

    # Handle command
    result = handle_set_command(args, logger)

    # Should return success
    assert result == 0

    # Verify configuration was updated
    with open(config_file) as f:
        config = yaml.safe_load(f)

    assert config["server"]["host"] == "0.0.0.0"


def test_handle_delete_command(config_file, logger):
    """Test the delete command handler."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.key = "server.debug"
    args.schema = None
    args.remote_url = None
    args.remote_api_key = None
    args.remote_read_only = False
    args.in_memory = False

    # Handle command
    result = handle_delete_command(args, logger)

    # Should return success
    assert result == 0

    # Verify key was deleted
    with open(config_file) as f:
        config = yaml.safe_load(f)

    assert "debug" not in config["server"]


def test_handle_import_command(config_file, tmp_path, logger):
    """Test the import command handler."""
    # Create an import file
    import_data = {
        "server": {"host": "example.com", "ssl": True},
        "new_section": {"key": "value"},
    }

    import_file = tmp_path / "import.json"
    with open(import_file, "w") as f:
        json.dump(import_data, f)

    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.import_file = str(import_file)
    args.schema = None
    args.remote_url = None
    args.remote_api_key = None
    args.remote_read_only = False
    args.in_memory = False

    # Handle command
    result = handle_import_command(args, logger)

    # Should return success
    assert result == 0

    # Verify the data was imported
    with open(config_file) as f:
        config = yaml.safe_load(f)

    assert config["server"]["host"] == "example.com"
    assert config["server"]["port"] == 8000  # Original value preserved
    assert config["server"]["ssl"] is True  # New value added
    assert config["new_section"]["key"] == "value"  # New section added


# Test validate command when schema dependencies are available
@patch("nekoconf.cli.main.HAS_SCHEMA_DEPS", True)
def test_handle_validate_command_success(config_file, schema_file, logger):
    """Test the validate command handler with successful validation."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.schema = str(schema_file)
    args.remote_url = None
    args.remote_api_key = None
    args.in_memory = False

    # Mock the validation method
    with patch("nekoconf.cli.main.NekoConfigManager") as mock_config_manager:
        mock_instance = mock_config_manager.return_value
        mock_instance.validate.return_value = []  # No validation errors

        # Handle command
        result = handle_validate_command(args, logger)

        # Should return success
        assert result == 0

        # Verify validation was called
        mock_instance.validate.assert_called_once()


# Test validate command when schema dependencies are available but validation fails
@patch("nekoconf.cli.main.HAS_SCHEMA_DEPS", True)
def test_handle_validate_command_failure(config_file, schema_file, logger):
    """Test the validate command handler with validation errors."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.schema = str(schema_file)
    args.remote_url = None
    args.remote_api_key = None
    args.in_memory = False

    # Mock the validation method
    with patch("nekoconf.cli.main.NekoConfigManager") as mock_config_manager:
        mock_instance = mock_config_manager.return_value
        mock_instance.validate.return_value = [
            "Error 1",
            "Error 2",
        ]  # Validation errors

        # Handle command
        result = handle_validate_command(args, logger)

        # Should return error
        assert result == 1

        # Verify validation was called
        mock_instance.validate.assert_called_once()


# Test validate command when schema dependencies are missing
@patch("nekoconf.cli.main.HAS_SCHEMA_DEPS", False)
def test_handle_validate_command_missing_deps(config_file, schema_file, logger):
    """Test the validate command handler with missing schema dependencies."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.schema = str(schema_file)
    args.remote_url = None
    args.remote_api_key = None
    args.in_memory = False

    # Handle command with missing dependencies
    result = handle_validate_command(args, logger)

    # Should return error due to missing schema dependencies
    assert result == 1


def test_handle_init_command(tmp_path, logger):
    """Test the init command handler."""
    # Create path for new config
    new_config = tmp_path / "new_config.yaml"

    # Create args object
    args = MagicMock()
    args.config = str(new_config)
    args.template = None

    # Handle command
    result = handle_init_command(args, logger)

    # Should return success
    assert result == 0

    # Verify file was created
    assert new_config.exists()
    with open(new_config) as f:
        config = yaml.safe_load(f)

    # Empty config should be an empty dict
    assert config == {}


# Test connect command when remote dependencies are available
@patch("nekoconf.cli.main.HAS_REMOTE_DEPS", True)
def test_handle_connect_command_with_deps(logger):
    """Test the connect command handler with available dependencies."""
    # Create args object
    args = MagicMock()
    args.remote_url = "http://example.com"
    args.api_key = "test-api-key"
    args.config = None  # In-memory mode
    args.read_only = True
    args.watch = False
    args.format = "json"

    # Mock the NekoConfigManager
    with patch("nekoconf.cli.main.NekoConfigManager") as mock_config_manager:
        mock_instance = mock_config_manager.return_value
        mock_instance.get.return_value = {"test": "data"}

        # Mock print formatting
        with patch("nekoconf.cli.main._print_formatted") as mock_print:
            # Handle command
            result = handle_connect_command(args, logger)

            # Should return success
            assert result == 0

            # Should create config manager with correct parameters
            mock_config_manager.assert_called_once_with(
                config_path=None,
                remote_url="http://example.com",
                remote_api_key="test-api-key",
                remote_read_only=True,
                in_memory=True,
                logger=logger,
            )

            # Should print the configuration
            mock_print.assert_called_once_with({"test": "data"}, "json")


# Test connect command when remote dependencies are missing
@patch("nekoconf.cli.main.HAS_REMOTE_DEPS", False)
def test_handle_connect_command_missing_deps(logger):
    """Test the connect command when remote dependencies are missing."""
    # Create args object
    args = MagicMock()
    args.remote_url = "http://example.com"
    args.api_key = "test-api-key"
    args.config = None
    args.read_only = True
    args.watch = False
    args.format = "json"

    # Handle command
    result = handle_connect_command(args, logger)

    # Should return error due to missing dependencies
    assert result == 1


@patch("nekoconf.cli.main._create_parser")
def test_main_version(mock_create_parser):
    """Test the main function with the version flag."""
    # Set up mock parser
    mock_parser = MagicMock()
    mock_parser.parse_args.return_value = MagicMock(version=True, command=None)
    mock_create_parser.return_value = mock_parser

    # Call main with version flag
    with patch("builtins.print") as mock_print:
        with patch("nekoconf.cli.main.__version__", "1.0.0"):
            result = main(["--version"])

    # Should print version and return success
    mock_print.assert_called_once_with("NekoConf version 1.0.0")
    assert result == 0


@patch("nekoconf.cli.main._create_parser")
def test_main_no_command(mock_create_parser):
    """Test the main function with no command."""
    # Set up mock parser
    mock_parser = MagicMock()
    mock_parser.parse_args.return_value = MagicMock(version=False, command=None)
    mock_create_parser.return_value = mock_parser

    # Call main with no command
    result = main([])

    # Should print help and return error
    mock_parser.print_help.assert_called_once()
    assert result == 1


def test_format_output_json():
    """Test the _format_output function with JSON format."""
    data = {"name": "test", "value": 123}

    with patch("json.dumps", return_value='{"name":"test","value":123}') as mock_dumps:
        result = _format_output(data, "json")
        mock_dumps.assert_called_once_with(data, indent=2)
        assert result == '{"name":"test","value":123}'


@patch("nekoconf.cli.main.HAS_YAML", True)
def test_format_output_yaml():
    """Test the _format_output function with YAML format."""
    data = {"name": "test", "value": 123}

    with patch("yaml.dump", return_value="name: test\nvalue: 123\n") as mock_dump:
        result = _format_output(data, "yaml")
        mock_dump.assert_called_once()
        assert result == "name: test\nvalue: 123\n"


@patch("nekoconf.cli.main.HAS_YAML", False)
def test_format_output_yaml_missing_deps():
    """Test the _format_output function with YAML format but missing YAML dependencies."""
    data = {"name": "test", "value": 123}

    # Should raise ImportError when YAML format requested but yaml not available
    with pytest.raises(ImportError):
        _format_output(data, "yaml")


def test_format_output_raw():
    """Test the _format_output function with raw format."""
    # For dictionaries and lists, should use JSON
    dict_data = {"name": "test", "value": 123}
    with patch("json.dumps", return_value='{"name":"test","value":123}') as mock_dumps:
        result = _format_output(dict_data, "raw")
        mock_dumps.assert_called_once_with(dict_data, indent=2)
        assert result == '{"name":"test","value":123}'

    # For simple values, should use str()
    assert _format_output("test", "raw") == "test"
    assert _format_output(123, "raw") == "123"
    assert _format_output(True, "raw") == "True"


@patch("nekoconf.cli.main.handle_server_command")
@patch("nekoconf.cli.main.handle_get_command")
@patch("nekoconf.cli.main.handle_set_command")
@patch("nekoconf.cli.main._create_parser")
def test_main_command_routing(mock_create_parser, mock_set, mock_get, mock_server):
    """Test that main routes commands to the correct handlers."""
    # Set up return values
    mock_get.return_value = 0
    mock_set.return_value = 0
    mock_server.return_value = 0

    # Test routing to get command
    mock_parser = MagicMock()
    mock_parser.parse_args.return_value = MagicMock(version=False, command="get")
    mock_create_parser.return_value = mock_parser

    result = main(["get", "test.key"])
    mock_get.assert_called_once()
    assert result == 0

    # Test routing to set command
    mock_get.reset_mock()
    mock_parser.parse_args.return_value = MagicMock(version=False, command="set")

    result = main(["set", "test.key", "value"])
    mock_set.assert_called_once()
    assert result == 0

    # Test routing to server command
    mock_set.reset_mock()
    mock_parser.parse_args.return_value = MagicMock(version=False, command="server")

    result = main(["server"])
    mock_server.assert_called_once()
    assert result == 0
