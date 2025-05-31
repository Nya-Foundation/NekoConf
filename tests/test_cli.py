"""Tests for the command-line interface."""

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import yaml

from nekoconf.cli.main import (
    cmd_connect,
    cmd_delete,
    cmd_get,
    cmd_init,
    cmd_server,
    cmd_set,
    cmd_validate,
    create_config,
    create_parser,
    format_output,
    main_cli,
    str2bool,
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


def test_str2bool():
    """Test the str2bool function."""
    # Test truthy values
    assert str2bool("yes") == True
    assert str2bool("true") == True
    assert str2bool("t") == True
    assert str2bool("1") == True
    assert str2bool("YES") == True
    assert str2bool("True") == True

    # Test falsy values
    assert str2bool("no") == False
    assert str2bool("false") == False
    assert str2bool("f") == False
    assert str2bool("0") == False
    assert str2bool("NO") == False
    assert str2bool("False") == False

    # Test invalid values
    with pytest.raises(argparse.ArgumentTypeError):
        str2bool("invalid")
    with pytest.raises(argparse.ArgumentTypeError):
        str2bool("maybe")


def test_create_parser():
    """Test creating the argument parser."""
    parser = create_parser()

    # Check that all expected commands are present
    commands = [
        "server",
        "get",
        "set",
        "delete",
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

    # Test version argument
    with pytest.raises(SystemExit):
        parser.parse_args(["--version"])


def test_create_parser_arguments():
    """Test specific argument parsing for each command."""
    parser = create_parser()

    # Test server command arguments
    args = parser.parse_args(["server", "--host", "127.0.0.1", "--port", "9000"])
    assert args.command == "server"
    assert args.host == "127.0.0.1"
    assert args.port == 9000

    # Test get command arguments
    args = parser.parse_args(["get", "key.path", "--format", "json"])
    assert args.command == "get"
    assert args.key == "key.path"
    assert args.format == "json"

    # Test set command arguments
    args = parser.parse_args(["set", "key", "value"])
    assert args.command == "set"
    assert args.key == "key"
    assert args.value == "value"

    # Test boolean arguments with different formats
    args = parser.parse_args(["server", "--read-only", "true", "--event", "false"])
    assert args.read_only == True
    assert args.event == False


@patch("nekoconf.cli.main.NekoConf")
def test_create_config_defaults(mock_nekoconf):
    """Test create_config with default parameters."""
    create_config()

    mock_nekoconf.assert_called_once()
    args, kwargs = mock_nekoconf.call_args
    assert kwargs["read_only"] == False
    assert kwargs["event_emission_enabled"] == False
    assert kwargs["schema_path"] is None


@patch("nekoconf.cli.main.HAS_REMOTE_DEPS", True)
@patch("nekoconf.cli.main.NekoConf")
def test_create_config_remote_full_params(mock_nekoconf):
    """Test create_config with all remote parameters."""
    # Mock the import inside create_config function
    with patch("nekoconf.storage.remote.RemoteStorageBackend") as mock_remote_backend:
        create_config(
            config_path="ignored",  # Should be ignored when remote_url is provided
            schema="schema.json",
            read_only=True,
            remote_url="https://api.example.com",
            remote_app_name="my-app",
            api_key="secret-key",
            event=True,
        )

        # Should create RemoteStorageBackend
        mock_remote_backend.assert_called_once_with(
            remote_url="https://api.example.com",
            app_name="my-app",
            api_key="secret-key",
            logger=mock_nekoconf.call_args[1]["logger"],
        )

        # NekoConf should be called with remote storage
        mock_nekoconf.assert_called_once()
        args, kwargs = mock_nekoconf.call_args
        assert kwargs["storage"] == mock_remote_backend.return_value
        assert kwargs["read_only"] == True
        assert kwargs["event_emission_enabled"] == True


@patch("nekoconf.cli.main.HAS_REMOTE_DEPS", False)
def test_create_config_remote_missing_deps():
    """Test create_config with remote storage when dependencies are missing."""
    with pytest.raises(ImportError, match="Remote features require"):
        create_config(remote_url="http://example.com")


@patch("nekoconf.cli.main.NekoConf")
def test_create_config_local(mock_nekoconf):
    """Test create_config with local storage."""
    create_config(config_path="config.yaml", schema="schema.json", read_only=True, event=False)

    mock_nekoconf.assert_called_once()
    args, kwargs = mock_nekoconf.call_args
    assert kwargs["read_only"] == True
    assert kwargs["event_emission_enabled"] == False


# Test server command when dependencies are available
@patch("nekoconf.cli.main.HAS_SERVER_DEPS", True)
@patch("nekoconf.cli.main.NekoConfOrchestrator")
def test_cmd_server_with_deps(mock_orchestrator):
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
    args.event = False

    # Handle command
    result = cmd_server(args)

    # Check orchestrator was created and run
    mock_orchestrator.assert_called_once()
    mock_orchestrator.return_value.run.assert_called_once_with(
        host="0.0.0.0", port=8000, reload=False
    )

    # Should return success
    assert result == 0


# Test server command when dependencies are missing
@patch("nekoconf.cli.main.HAS_SERVER_DEPS", False)
def test_cmd_server_missing_deps():
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
    with patch("builtins.print") as mock_print:
        result = cmd_server(args)

    # Should return error code
    assert result == 1
    mock_print.assert_called_once_with("Server features require: pip install nekoconf[server]")


def test_cmd_get(config_file):
    """Test the get command handler."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.key = "server.host"
    args.format = "raw"
    args.remote = None
    args.api_key = None

    # Mock the create_config function call parameters
    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        mock_instance = mock_create_config.return_value
        mock_instance.get.return_value = "localhost"

        with patch("builtins.print") as mock_print:
            # Handle command
            result = cmd_get(args)

            # Should return success
            assert result == 0

            # Should print the value
            mock_print.assert_called_once()


def test_cmd_get_all_config(config_file):
    """Test the get command without specific key (get all)."""
    args = MagicMock()
    args.config = str(config_file)
    args.key = None  # No specific key
    args.format = "json"
    args.remote = None
    args.api_key = None

    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        mock_instance = mock_create_config.return_value
        mock_instance.get_all.return_value = {"server": {"host": "localhost"}}

        with patch("builtins.print") as mock_print:
            result = cmd_get(args)
            assert result == 0
            mock_instance.get_all.assert_called_once()


def test_cmd_get_error():
    """Test the get command with error handling."""
    args = MagicMock()
    args.config = "nonexistent.yaml"
    args.key = "test.key"
    args.format = "raw"
    args.remote = None
    args.api_key = None

    with patch("nekoconf.cli.main.create_config", side_effect=Exception("File not found")):
        with patch("builtins.print") as mock_print:
            result = cmd_get(args)
            assert result == 1
            mock_print.assert_called_with("Error: File not found")


def test_cmd_set(config_file):
    """Test the set command handler."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.key = "server.host"
    args.value = "0.0.0.0"
    args.schema = None
    args.remote = None
    args.api_key = None

    # Mock create_config to avoid validation issues
    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        with patch("nekoconf.cli.main.parse_value", return_value="0.0.0.0") as mock_parse:
            mock_instance = mock_create_config.return_value

            with patch("builtins.print") as mock_print:
                # Handle command
                result = cmd_set(args)

                # Should return success
                assert result == 0

                # Should call set and save
                mock_instance.set.assert_called_once_with("server.host", "0.0.0.0")
                mock_instance.save.assert_called_once()

                # Should print confirmation
                mock_print.assert_called_once_with("Set server.host = 0.0.0.0")


def test_cmd_set_with_schema_validation(config_file):
    """Test the set command with schema validation."""
    args = MagicMock()
    args.config = str(config_file)
    args.key = "server.port"
    args.value = "8080"
    args.schema = "schema.json"
    args.remote = None
    args.api_key = None

    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        with patch("nekoconf.cli.main.parse_value", return_value=8080):
            mock_instance = mock_create_config.return_value
            mock_instance.validate.return_value = True

            result = cmd_set(args)
            assert result == 0
            mock_instance.validate.assert_called_once()


def test_cmd_set_validation_failure(config_file):
    """Test the set command with validation failure."""
    args = MagicMock()
    args.config = str(config_file)
    args.key = "server.port"
    args.value = "invalid"
    args.schema = "schema.json"
    args.remote = None
    args.api_key = None

    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        with patch("nekoconf.cli.main.parse_value", return_value="invalid"):
            mock_instance = mock_create_config.return_value
            mock_instance.validate.return_value = False

            with patch("builtins.print") as mock_print:
                result = cmd_set(args)
                assert result == 1
                mock_print.assert_called_with("Validation failed")


def test_cmd_set_error():
    """Test the set command with error handling."""
    args = MagicMock()
    args.config = "nonexistent.yaml"
    args.key = "test.key"
    args.value = "test_value"
    args.schema = None
    args.remote = None
    args.api_key = None

    with patch("nekoconf.cli.main.create_config", side_effect=Exception("File not found")):
        with patch("builtins.print") as mock_print:
            result = cmd_set(args)
            assert result == 1
            mock_print.assert_called_with("Error: File not found")


def test_cmd_delete(config_file):
    """Test the delete command handler."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.key = "server.debug"
    args.schema = None
    args.remote = None
    args.api_key = None

    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        mock_instance = mock_create_config.return_value
        mock_instance.delete.return_value = True

        with patch("builtins.print") as mock_print:
            # Handle command
            result = cmd_delete(args)

            # Should return success
            assert result == 0
            mock_instance.delete.assert_called_once_with("server.debug")
            mock_instance.save.assert_called_once()


def test_cmd_delete_key_not_found(config_file):
    """Test the delete command when key is not found."""
    args = MagicMock()
    args.config = str(config_file)
    args.key = "nonexistent.key"
    args.schema = None
    args.remote = None
    args.api_key = None

    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        mock_instance = mock_create_config.return_value
        mock_instance.delete.return_value = False

        with patch("builtins.print") as mock_print:
            result = cmd_delete(args)
            assert result == 0
            mock_print.assert_called_with("Key 'nonexistent.key' not found")


def test_cmd_delete_with_validation(config_file):
    """Test the delete command with schema validation."""
    args = MagicMock()
    args.config = str(config_file)
    args.key = "server.debug"
    args.schema = "schema.json"
    args.remote = None
    args.api_key = None

    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        mock_instance = mock_create_config.return_value
        mock_instance.delete.return_value = True
        mock_instance.validate.return_value = True

        result = cmd_delete(args)
        assert result == 0
        mock_instance.validate.assert_called_once()


def test_cmd_delete_validation_failure(config_file):
    """Test the delete command with validation failure."""
    args = MagicMock()
    args.config = str(config_file)
    args.key = "server.host"
    args.schema = "schema.json"
    args.remote = None
    args.api_key = None

    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        mock_instance = mock_create_config.return_value
        mock_instance.delete.return_value = True
        mock_instance.validate.return_value = False

        with patch("builtins.print") as mock_print:
            result = cmd_delete(args)
            assert result == 1
            mock_print.assert_called_with("Validation failed")


def test_cmd_delete_error():
    """Test the delete command with error handling."""
    args = MagicMock()
    args.config = "nonexistent.yaml"
    args.key = "test.key"
    args.schema = None
    args.remote = None
    args.api_key = None

    with patch("nekoconf.cli.main.create_config", side_effect=Exception("File not found")):
        with patch("builtins.print") as mock_print:
            result = cmd_delete(args)
            assert result == 1
            mock_print.assert_called_with("Error: File not found")


# Test validate command when schema dependencies are available
@patch("nekoconf.cli.main.HAS_SCHEMA_DEPS", True)
def test_cmd_validate_success(config_file, schema_file):
    """Test the validate command handler with successful validation."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.schema = str(schema_file)
    args.remote = None
    args.api_key = None

    # Mock the validation method
    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        mock_instance = mock_create_config.return_value
        mock_instance.validate.return_value = []  # No validation errors

        with patch("builtins.print") as mock_print:
            # Handle command
            result = cmd_validate(args)

            # Should return success
            assert result == 0
            mock_print.assert_called_with("Validation successful")

            # Verify validation was called
            mock_instance.validate.assert_called_once()


# Test validate command when schema dependencies are available but validation fails
@patch("nekoconf.cli.main.HAS_SCHEMA_DEPS", True)
def test_cmd_validate_failure(config_file, schema_file):
    """Test the validate command handler with validation errors."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.schema = str(schema_file)
    args.remote = None
    args.api_key = None

    # Mock the validation method
    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        mock_instance = mock_create_config.return_value
        mock_instance.validate.return_value = [
            "Error 1",
            "Error 2",
        ]  # Validation errors

        with patch("builtins.print") as mock_print:
            # Handle command
            result = cmd_validate(args)

            # Should return error
            assert result == 1

            # Verify validation was called
            mock_instance.validate.assert_called_once()

            # Check error messages were printed
            expected_calls = [call("Validation failed:"), call("  - Error 1"), call("  - Error 2")]
            mock_print.assert_has_calls(expected_calls)


# Test validate command when schema dependencies are missing
@patch("nekoconf.cli.main.HAS_SCHEMA_DEPS", False)
def test_cmd_validate_missing_deps(config_file, schema_file):
    """Test the validate command handler with missing schema dependencies."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.schema = str(schema_file)
    args.remote = None
    args.api_key = None

    with patch("builtins.print") as mock_print:
        # Handle command with missing dependencies
        result = cmd_validate(args)

        # Should return error due to missing schema dependencies
        assert result == 1
        mock_print.assert_called_with("Schema validation requires: pip install nekoconf[schema]")


@patch("nekoconf.cli.main.HAS_SCHEMA_DEPS", True)
def test_cmd_validate_error():
    """Test the validate command with error handling."""
    args = MagicMock()
    args.config = "nonexistent.yaml"
    args.schema = "schema.json"
    args.remote = None
    args.api_key = None

    with patch("nekoconf.cli.main.create_config", side_effect=Exception("File not found")):
        with patch("builtins.print") as mock_print:
            result = cmd_validate(args)
            assert result == 1
            mock_print.assert_called_with("Error: File not found")


def test_cmd_init(tmp_path):
    """Test the init command handler."""
    # Create path for new config
    new_config = tmp_path / "new_config.yaml"

    # Create args object
    args = MagicMock()
    args.config = str(new_config)
    args.template = None

    # Handle command
    result = cmd_init(args)

    # Should return success
    assert result == 0

    # Verify file was created
    assert new_config.exists()
    with open(new_config) as f:
        config = yaml.safe_load(f)

    # Empty config should be an empty dict
    assert config == {}


def test_cmd_init_with_template(tmp_path):
    """Test the init command with template."""
    # Create template file
    template_path = tmp_path / "template.yaml"
    template_data = {"app": {"name": "example", "version": "1.0"}}
    with open(template_path, "w") as f:
        yaml.dump(template_data, f)

    # Create path for new config
    new_config = tmp_path / "new_config.yaml"

    args = MagicMock()
    args.config = str(new_config)
    args.template = str(template_path)

    with patch("nekoconf.cli.main.load_file", return_value=template_data):
        with patch("nekoconf.cli.main.save_file") as mock_save:
            result = cmd_init(args)
            assert result == 0
            mock_save.assert_called_once()


def test_cmd_init_file_exists(tmp_path):
    """Test the init command when file already exists."""
    existing_config = tmp_path / "existing.yaml"
    existing_config.write_text("existing: content")

    args = MagicMock()
    args.config = str(existing_config)
    args.template = None

    with patch("builtins.print") as mock_print:
        result = cmd_init(args)
        assert result == 1
        mock_print.assert_called_with(f"Configuration file already exists: {existing_config}")


def test_cmd_init_template_not_found(tmp_path):
    """Test the init command with non-existent template."""
    new_config = tmp_path / "new_config.yaml"
    nonexistent_template = tmp_path / "nonexistent.yaml"

    args = MagicMock()
    args.config = str(new_config)
    args.template = str(nonexistent_template)

    with patch("builtins.print") as mock_print:
        result = cmd_init(args)
        assert result == 1
        mock_print.assert_called_with(f"Template file not found: {nonexistent_template}")


def test_cmd_init_error():
    """Test the init command with error handling."""
    args = MagicMock()
    args.config = "/invalid/path/config.yaml"
    args.template = None

    with patch("nekoconf.cli.main.save_file", side_effect=Exception("Permission denied")):
        with patch("builtins.print") as mock_print:
            result = cmd_init(args)
            assert result == 1
            mock_print.assert_called_with("Error: Permission denied")


# Test connect command when remote dependencies are missing
@patch("nekoconf.cli.main.HAS_REMOTE_DEPS", False)
def test_cmd_connect_missing_deps():
    """Test the connect command when remote dependencies are missing."""
    # Create args object
    args = MagicMock()
    args.remote = "http://example.com"
    args.api_key = "test-api-key"
    args.app_name = None
    args.format = "json"

    # Handle command
    with patch("builtins.print") as mock_print:
        result = cmd_connect(args)

    # Should return error due to missing dependencies
    assert result == 1
    mock_print.assert_called_once_with("Remote connection requires: pip install nekoconf[remote]")


# Test connect command when remote URL is missing
@patch("nekoconf.cli.main.HAS_REMOTE_DEPS", True)
def test_cmd_connect_missing_url():
    """Test the connect command when remote URL is missing."""
    # Create args object
    args = MagicMock()
    args.remote = None
    args.api_key = "test-api-key"
    args.app_name = None
    args.format = "json"

    # Handle command
    with patch("builtins.print") as mock_print:
        result = cmd_connect(args)

    # Should return error due to missing URL
    assert result == 1
    mock_print.assert_called_once_with("Remote URL is required for connection")


@patch("nekoconf.cli.main.HAS_REMOTE_DEPS", True)
def test_cmd_connect_success():
    """Test the connect command with successful connection."""
    args = MagicMock()
    args.remote = "http://example.com"
    args.api_key = "test-api-key"
    args.app_name = "test-app"
    args.format = "json"

    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        mock_instance = mock_create_config.return_value
        mock_instance.get_all.return_value = {"key": "value"}

        with patch(
            "nekoconf.cli.main.format_output", return_value='{"key":"value"}'
        ) as mock_format:
            with patch("builtins.print") as mock_print:
                result = cmd_connect(args)
                assert result == 0
                mock_instance.get_all.assert_called_once()
                mock_format.assert_called_once()


@patch("nekoconf.cli.main.HAS_REMOTE_DEPS", True)
def test_cmd_connect_error():
    """Test the connect command with connection error."""
    args = MagicMock()
    args.remote = "http://example.com"
    args.api_key = "test-api-key"
    args.app_name = None
    args.format = "json"

    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        mock_create_config.side_effect = Exception("Connection failed")

        # Since cmd_connect doesn't handle exceptions, it should raise
        with pytest.raises(Exception, match="Connection failed"):
            cmd_connect(args)


@patch("nekoconf.cli.main.create_parser")
def test_main_no_command(mock_create_parser):
    """Test the main function with no command."""
    # Set up mock parser
    mock_parser = MagicMock()
    mock_parser.parse_args.return_value = MagicMock(command=None)
    mock_create_parser.return_value = mock_parser

    # Call main with no command
    result = main_cli()

    # Should print help and return error
    mock_parser.print_help.assert_called_once()
    assert result == 1


def test_cli_debug_flag_handling():
    """Test CLI debug flag handling."""
    original_argv = sys.argv[:]
    try:
        sys.argv = ["nekoconf", "--debug", "get", "test.key"]
        with patch("logging.basicConfig") as mock_basic_config:
            with patch("nekoconf.cli.main.create_parser") as mock_create_parser:
                mock_parser = MagicMock()
                mock_parser.parse_args.return_value = MagicMock(command="get")
                mock_create_parser.return_value = mock_parser

                with patch("nekoconf.cli.main.cmd_get", return_value=0):
                    main_cli()

                mock_basic_config.assert_called_once()
    finally:
        sys.argv = original_argv


def test_cli_unknown_command():
    """Test CLI with unknown command."""
    with patch("nekoconf.cli.main.create_parser") as mock_create_parser:
        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = MagicMock(command="unknown")
        mock_create_parser.return_value = mock_parser

        with patch("builtins.print") as mock_print:
            result = main_cli()
            assert result == 1
            mock_print.assert_called_with("Unknown command: unknown")


def test_format_output_json():
    """Test the format_output function with JSON format."""
    data = {"name": "test", "value": 123}

    with patch("json.dumps", return_value='{"name":"test","value":123}') as mock_dumps:
        result = format_output(data, "json")
        mock_dumps.assert_called_once_with(data, indent=2)
        assert result == '{"name":"test","value":123}'


def test_format_output_yaml():
    """Test the format_output function with YAML format."""
    data = {"name": "test", "value": 123}

    with patch("yaml.dump", return_value="name: test\nvalue: 123\n") as mock_dump:
        result = format_output(data, "yaml")
        mock_dump.assert_called_once()
        assert result == "name: test\nvalue: 123\n"


def test_format_output_raw():
    """Test the format_output function with raw format."""
    # For dictionaries and lists, should use JSON
    dict_data = {"name": "test", "value": 123}
    with patch("json.dumps", return_value='{"name":"test","value":123}') as mock_dumps:
        result = format_output(dict_data, "raw")
        mock_dumps.assert_called_once_with(dict_data, indent=2)
        assert result == '{"name":"test","value":123}'

    # For simple values, should use str()
    assert format_output("test", "raw") == "test"
    assert format_output(123, "raw") == "123"
    assert format_output(True, "raw") == "True"


@patch("nekoconf.cli.main.cmd_server")
@patch("nekoconf.cli.main.cmd_get")
@patch("nekoconf.cli.main.cmd_set")
@patch("nekoconf.cli.main.create_parser")
def test_main_command_routing(mock_create_parser, mock_set, mock_get, mock_server):
    """Test that main routes commands to the correct handlers."""
    # Set up return values
    mock_get.return_value = 0
    mock_set.return_value = 0
    mock_server.return_value = 0

    # Test routing to get command
    mock_parser = MagicMock()
    mock_parser.parse_args.return_value = MagicMock(command="get")
    mock_create_parser.return_value = mock_parser

    result = main_cli()
    mock_get.assert_called_once()
    assert result == 0

    # Test routing to set command
    mock_get.reset_mock()
    mock_parser.parse_args.return_value = MagicMock(command="set")

    result = main_cli()
    mock_set.assert_called_once()
    assert result == 0

    # Test routing to server command
    mock_set.reset_mock()
    mock_parser.parse_args.return_value = MagicMock(command="server")

    result = main_cli()
    mock_server.assert_called_once()
    assert result == 0


# Additional edge case tests
def test_create_parser_edge_cases():
    """Test edge cases in argument parsing."""
    parser = create_parser()

    # Test with minimal arguments
    args = parser.parse_args(["get"])
    assert args.command == "get"
    assert args.key is None

    # Test server with all optional arguments
    args = parser.parse_args(
        [
            "server",
            "--host",
            "localhost",
            "--port",
            "3000",
            "--config",
            "test.yaml",
            "--schema",
            "test.json",
            "--api-key",
            "secret",
            "--event",
            "true",
            "--read-only",
            "false",
            "--reload",
            "yes",
        ]
    )
    assert args.host == "localhost"
    assert args.port == 3000
    assert args.config == "test.yaml"
    assert args.schema == "test.json"
    assert args.api_key == "secret"
    assert args.event == True
    assert args.read_only == False
    assert args.reload == True


def test_str2bool_edge_cases():
    """Test edge cases for str2bool function."""
    # Test with mixed case
    assert str2bool("YeS") == True
    assert str2bool("tRuE") == True
    assert str2bool("nO") == False
    assert str2bool("fAlSe") == False

    # Test with whitespace (should fail)
    with pytest.raises(argparse.ArgumentTypeError):
        str2bool(" true ")
    with pytest.raises(argparse.ArgumentTypeError):
        str2bool("true\n")


@patch("nekoconf.cli.main.HAS_REMOTE_DEPS", True)
@patch("nekoconf.cli.main.NekoConf")
def test_create_config_schema_path_conversion(mock_nekoconf):
    """Test that schema string is properly converted to Path."""
    create_config(schema="schema.json")

    # Check that Path object was created for schema
    args, kwargs = mock_nekoconf.call_args
    schema_path = kwargs["schema_path"]
    assert isinstance(schema_path, Path)
    assert str(schema_path) == "schema.json"


def test_format_output_edge_cases():
    """Test edge cases for format_output function."""
    # Test with None
    assert format_output(None, "raw") == "None"

    # Test with empty containers
    assert format_output({}, "raw") == "{}"
    assert format_output([], "raw") == "[]"

    # Test YAML with complex data
    complex_data = {"list": [1, 2, 3], "nested": {"key": "value"}}
    with patch("yaml.dump") as mock_dump:
        format_output(complex_data, "yaml")
        mock_dump.assert_called_once_with(complex_data, default_flow_style=False)


@patch("nekoconf.cli.main.HAS_SERVER_DEPS", True)
@patch("nekoconf.cli.main.NekoConfOrchestrator")
def test_cmd_server_without_config(mock_orchestrator):
    """Test server command without config file."""
    args = MagicMock()
    args.config = None  # No config file
    args.host = "127.0.0.1"
    args.port = 9000
    args.schema = None
    args.reload = True
    args.api_key = "test-key"
    args.read_only = True
    args.event = False
    args.app_name = None  # This will default to "default"

    result = cmd_server(args)

    # Should create orchestrator with empty apps dict
    mock_orchestrator.assert_called_once()
    call_args = mock_orchestrator.call_args
    assert call_args[1]["apps"] == {"default": None}
    assert call_args[1]["api_key"] == "test-key"
    assert call_args[1]["read_only"] == True

    mock_orchestrator.return_value.run.assert_called_once_with(
        host="127.0.0.1", port=9000, reload=True
    )
    assert result == 0


def test_cmd_get_with_remote_params():
    """Test get command with remote parameters."""
    args = MagicMock()
    args.config = "config.yaml"
    args.key = "test.key"
    args.format = "yaml"
    args.remote = "http://remote.server"
    args.api_key = "remote-key"

    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        mock_instance = mock_create_config.return_value
        mock_instance.get.return_value = {"test": "value"}

        with patch("nekoconf.cli.main.format_output", return_value="test: value\n"):
            with patch("builtins.print") as mock_print:
                result = cmd_get(args)

                # Verify create_config was called with remote params
                mock_create_config.assert_called_once_with(
                    "config.yaml", remote_url="http://remote.server", api_key="remote-key"
                )
                assert result == 0


def test_cmd_set_with_remote_params():
    """Test set command with remote parameters."""
    args = MagicMock()
    args.config = "config.yaml"
    args.key = "test.key"
    args.value = "test_value"
    args.schema = "schema.json"
    args.remote = "http://remote.server"
    args.api_key = "remote-key"

    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        with patch("nekoconf.cli.main.parse_value", return_value="test_value"):
            mock_instance = mock_create_config.return_value
            mock_instance.validate.return_value = True

            with patch("builtins.print"):
                result = cmd_set(args)

                # Verify create_config was called with all params
                mock_create_config.assert_called_once_with(
                    "config.yaml",
                    schema="schema.json",
                    remote_url="http://remote.server",
                    api_key="remote-key",
                )
                assert result == 0


# Integration and edge case tests
def test_cli_integration_with_debug():
    """Test CLI integration with debug flag."""
    original_argv = sys.argv[:]
    try:
        sys.argv = ["nekoconf", "--debug", "get", "test.key", "--format", "json"]
        with patch("logging.basicConfig") as mock_basic_config:
            with patch("nekoconf.cli.main.create_parser") as mock_create_parser:
                mock_parser = MagicMock()
                mock_args = MagicMock()
                mock_args.command = "get"
                mock_args.key = "test.key"
                mock_args.format = "json"
                mock_args.config = "config.yaml"
                mock_args.remote = None
                mock_args.api_key = None
                mock_parser.parse_args.return_value = mock_args
                mock_create_parser.return_value = mock_parser

                with patch("nekoconf.cli.main.cmd_get", return_value=0) as mock_get:
                    result = main_cli()
                    assert result == 0
                    mock_get.assert_called_once_with(mock_args)
                    mock_basic_config.assert_called_once()
    finally:
        sys.argv = original_argv


def test_create_config_with_all_params():
    """Test create_config with all possible parameters."""
    with patch("nekoconf.cli.main.NekoConf") as mock_nekoconf:
        create_config(config_path="test.yaml", schema="schema.json", read_only=True, event=True)

        mock_nekoconf.assert_called_once()
        args, kwargs = mock_nekoconf.call_args
        assert kwargs["storage"] == "test.yaml"
        assert isinstance(kwargs["schema_path"], Path)
        assert kwargs["read_only"] == True
        assert kwargs["event_emission_enabled"] == True
        assert kwargs["logger"] is not None


def test_cmd_connect_with_default_format():
    """Test connect command with default format handling."""
    args = MagicMock()
    args.remote = "http://example.com"
    args.api_key = "test-key"
    args.app_name = "test-app"
    args.format = None  # Should default to json

    with patch("nekoconf.cli.main.HAS_REMOTE_DEPS", True):
        with patch("nekoconf.cli.main.create_config") as mock_create_config:
            mock_instance = mock_create_config.return_value
            mock_instance.get_all.return_value = {"key": "value"}

            with patch("nekoconf.cli.main.format_output", return_value='{"key":"value"}'):
                with patch("builtins.print") as mock_print:
                    result = cmd_connect(args)
                    assert result == 0


def test_cmd_set_without_schema():
    """Test set command without schema validation."""
    args = MagicMock()
    args.config = "config.yaml"
    args.key = "test.key"
    args.value = "test_value"
    args.schema = None
    args.remote = None
    args.api_key = None

    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        with patch("nekoconf.cli.main.parse_value", return_value="test_value"):
            mock_instance = mock_create_config.return_value

            with patch("builtins.print") as mock_print:
                result = cmd_set(args)
                assert result == 0
                # Should not call validate when schema is None
                mock_instance.validate.assert_not_called()


def test_cmd_delete_without_schema():
    """Test delete command without schema validation."""
    args = MagicMock()
    args.config = "config.yaml"
    args.key = "test.key"
    args.schema = None
    args.remote = None
    args.api_key = None

    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        mock_instance = mock_create_config.return_value
        mock_instance.delete.return_value = True

        with patch("builtins.print"):
            result = cmd_delete(args)
            assert result == 0
            # Should not call validate when schema is None
            mock_instance.validate.assert_not_called()


def test_format_output_with_list():
    """Test format_output with list data."""
    list_data = [1, 2, 3, {"nested": "value"}]

    # JSON format
    with patch("json.dumps", return_value='[1,2,3,{"nested":"value"}]') as mock_dumps:
        result = format_output(list_data, "json")
        mock_dumps.assert_called_once_with(list_data, indent=2)
        assert result == '[1,2,3,{"nested":"value"}]'

    # Raw format should also use JSON for lists
    with patch("json.dumps", return_value='[1,2,3,{"nested":"value"}]') as mock_dumps:
        result = format_output(list_data, "raw")
        mock_dumps.assert_called_once_with(list_data, indent=2)
        assert result == '[1,2,3,{"nested":"value"}]'


def test_create_parser_complete_coverage():
    """Test argument parser with all possible argument combinations."""
    parser = create_parser()

    # Test connect command with all arguments
    args = parser.parse_args(
        [
            "connect",
            "--remote",
            "http://example.com",
            "--app-name",
            "my-app",
            "--api-key",
            "secret",
            "--format",
            "yaml",
        ]
    )
    assert args.command == "connect"
    assert args.remote == "http://example.com"
    assert args.app_name == "my-app"
    assert args.api_key == "secret"
    assert args.format == "yaml"

    # Test validate command
    args = parser.parse_args(
        [
            "validate",
            "--config",
            "test.yaml",
            "--schema",
            "schema.json",
            "--remote",
            "http://example.com",
            "--api-key",
            "key",
        ]
    )
    assert args.command == "validate"
    assert args.config == "test.yaml"
    assert args.schema == "schema.json"
    assert args.remote == "http://example.com"
    assert args.api_key == "key"

    # Test init command with template
    args = parser.parse_args(["init", "new_config.yaml", "--template", "template.yaml"])
    assert args.command == "init"
    assert args.config == "new_config.yaml"
    assert args.template == "template.yaml"


def test_error_handling_consistency():
    """Test that all commands handle errors consistently."""
    error_msg = "Test error"

    # Test that all command functions handle exceptions properly
    commands_to_test = [
        (
            cmd_get,
            {
                "config": "test.yaml",
                "key": "test",
                "format": "raw",
                "remote": None,
                "api_key": None,
            },
        ),
        (
            cmd_set,
            {
                "config": "test.yaml",
                "key": "test",
                "value": "value",
                "schema": None,
                "remote": None,
                "api_key": None,
            },
        ),
        (
            cmd_delete,
            {"config": "test.yaml", "key": "test", "schema": None, "remote": None, "api_key": None},
        ),
    ]

    for cmd_func, args_dict in commands_to_test:
        args = MagicMock()
        for key, value in args_dict.items():
            setattr(args, key, value)

        with patch("nekoconf.cli.main.create_config", side_effect=Exception(error_msg)):
            with patch("builtins.print") as mock_print:
                result = cmd_func(args)
                assert result == 1
                mock_print.assert_called_with(f"Error: {error_msg}")


@patch("nekoconf.cli.main.HAS_SERVER_DEPS", True)
@patch("nekoconf.cli.main.NekoConfOrchestrator")
def test_cmd_server_with_all_options(mock_orchestrator):
    """Test server command with all possible options."""
    args = MagicMock()
    args.config = "config.yaml"
    args.host = "localhost"
    args.port = 8080
    args.schema = "schema.json"
    args.reload = True
    args.api_key = "test-key"
    args.read_only = True
    args.event = True
    args.app_name = "my-app"  # Set explicit app name

    with patch("nekoconf.cli.main.create_config") as mock_create_config:
        result = cmd_server(args)

        # Verify create_config was called with correct parameters
        mock_create_config.assert_called_once_with(
            "config.yaml", schema="schema.json", api_key="test-key", read_only=True, event=True
        )

        # Verify orchestrator was configured correctly
        mock_orchestrator.assert_called_once()
        call_args = mock_orchestrator.call_args[1]
        assert "my-app" in call_args["apps"]
        assert call_args["api_key"] == "test-key"
        assert call_args["read_only"] == True

        assert result == 0


def test_cli_command_dispatch_completeness():
    """Test that all commands are properly dispatched."""
    commands = ["server", "connect", "get", "set", "delete", "validate", "init"]

    for command in commands:
        with patch("nekoconf.cli.main.create_parser") as mock_create_parser:
            mock_parser = MagicMock()
            mock_parser.parse_args.return_value = MagicMock(command=command)
            mock_create_parser.return_value = mock_parser

            # Mock the corresponding command function
            with patch(f"nekoconf.cli.main.cmd_{command}", return_value=0) as mock_cmd:
                result = main_cli()
                assert result == 0
                mock_cmd.assert_called_once()


def test_schema_path_handling():
    """Test schema path conversion in create_config."""
    with patch("nekoconf.cli.main.NekoConf") as mock_nekoconf:
        # Test with string schema
        create_config(schema="test_schema.json")
        args, kwargs = mock_nekoconf.call_args
        assert isinstance(kwargs["schema_path"], Path)
        assert str(kwargs["schema_path"]) == "test_schema.json"

        # Test with None schema
        mock_nekoconf.reset_mock()
        create_config(schema=None)
        args, kwargs = mock_nekoconf.call_args
        assert kwargs["schema_path"] is None
