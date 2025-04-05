"""Tests for the command-line interface."""

import pytest
import yaml
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from nekoconf.cli import (
    _create_parser,
    handle_server_command,
    handle_get_command,
    handle_set_command,
    handle_delete_command,
    handle_import_command,
    handle_validate_command,
    handle_init_command,
    main,
)


def test_create_parser():
    """Test creating the argument parser."""
    parser = _create_parser()

    # Check that all expected commands are present
    commands = ["server", "get", "set", "delete", "import", "validate", "init"]

    for command in commands:
        # Ensure each command has a subparser
        assert any(
            subparser.dest == "command" and command in subparser.choices
            for subparser in parser._subparsers._group_actions
        )


def test_handle_server_command():
    """Test the server command handler with mocks."""
    with patch("nekoconf.cli.WebServer") as mock_web_server:
        # Create args object
        args = MagicMock()
        args.config = "config.yaml"
        args.host = "127.0.0.1"
        args.port = 9000
        args.static_dir = "static"
        args.schema = None
        args.reload = True

        # Handle command
        result = handle_server_command(args)

        # Check server was created and run
        mock_web_server.assert_called_once()
        mock_web_server.return_value.run.assert_called_once_with(
            host="127.0.0.1", port=9000, reload=True
        )

        # Should return success
        assert result == 0


def test_config_modification_commands(config_file):
    """Test commands that modify configuration."""
    # Test set command
    args_set = MagicMock()
    args_set.config = str(config_file)
    args_set.key = "server.host"
    args_set.value = "127.0.0.1"
    args_set.schema = None

    result = handle_set_command(args_set)
    assert result == 0

    # Test delete command
    args_delete = MagicMock()
    args_delete.config = str(config_file)
    args_delete.key = "server.debug"
    args_delete.schema = None

    result = handle_delete_command(args_delete)
    assert result == 0

    # Verify configuration was modified
    with open(config_file) as f:
        config = yaml.safe_load(f)

    assert config["server"]["host"] == "127.0.0.1"
    assert "debug" not in config["server"]


def test_handle_import_command(config_file, tmp_path):
    """Test the import command handler."""
    # Create an import file
    import_data = {"server": {"host": "example.com", "ssl": True}, "new_section": {"key": "value"}}

    import_file = tmp_path / "import.json"
    with open(import_file, "w") as f:
        json.dump(import_data, f)

    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.import_file = str(import_file)
    args.deep_merge = True
    args.schema = None

    # Handle command
    result = handle_import_command(args)

    # Should return success
    assert result == 0

    # Verify the data was imported
    with open(config_file) as f:
        config = yaml.safe_load(f)

    assert config["server"]["host"] == "example.com"
    assert config["server"]["port"] == 8000  # Original value preserved
    assert config["server"]["ssl"] is True  # New value added
    assert config["new_section"]["key"] == "value"  # New section added


@patch("nekoconf.cli.ConfigManager")
def test_handle_validate_command(mock_config_manager, config_file, schema_file):
    """Test the validate command handler."""
    # Setup mock to simulate successful validation
    mock_instance = mock_config_manager.return_value
    mock_instance.validate.return_value = []  # Empty list indicates no errors

    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.schema = str(schema_file)

    # Handle command
    result = handle_validate_command(args)

    # Should return success
    assert result == 0

    # Verify the validation was attempted
    mock_config_manager.assert_called_once_with(Path(str(config_file)), Path(str(schema_file)))
    mock_instance.load.assert_called_once()
    mock_instance.validate.assert_called_once()


def test_handle_init_command(tmp_path):
    """Test the init command handler."""
    # Create path for new config
    new_config = tmp_path / "new_config.yaml"

    # Create args object
    args = MagicMock()
    args.config = str(new_config)
    args.template = None

    # Handle command
    result = handle_init_command(args)

    # Should return success
    assert result == 0

    # Verify file was created
    assert new_config.exists()
    with open(new_config) as f:
        config = yaml.safe_load(f)

    # Empty config might be None or empty dict, both are valid
    assert config is None or config == {}


@patch("nekoconf.cli.handle_server_command")
@patch("nekoconf.cli.handle_get_command")
def test_main_command_routing(mock_get, mock_server):
    """Test that main routes commands to the correct handlers."""
    # Set up return values
    mock_get.return_value = 0
    mock_server.return_value = 0

    # Test routing to get command
    result = main(["get", "--config", "config.yaml", "server.host"])
    mock_get.assert_called_once()
    assert result == 0

    # Test routing to server command
    mock_get.reset_mock()
    result = main(["server", "--config", "config.yaml"])
    mock_server.assert_called_once()
    assert result == 0


def test_main_error():
    """Test the main function with an error."""
    # Call main with invalid arguments
    with patch("nekoconf.cli.handle_get_command") as mock_handler:
        mock_handler.side_effect = Exception("Test error")

        result = main(["get", "--config", "config.yaml"])

    # Should return error
    assert result == 1
