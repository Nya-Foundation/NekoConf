"""Tests for the command-line interface."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from nekoconf.cli.main import (
    _create_parser,
    handle_delete_command,
    handle_get_command,
    handle_import_command,
    handle_init_command,
    handle_server_command,
    handle_set_command,
    handle_validate_command,
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
    with patch("nekoconf.cli.main.NekoConfigServer") as mock_web_server:
        # Create args object
        args = MagicMock()
        args.config = "config.yaml"
        args.host = "127.0.0.1"
        args.port = 9000
        args.schema = None
        args.reload = True
        args.api_key = None

        # Handle command
        result = handle_server_command(args)

        # Check server was created and run
        mock_web_server.assert_called_once()
        mock_web_server.return_value.run.assert_called_once_with(
            host="127.0.0.1", port=9000, reload=True
        )

        # Should return success
        assert result == 0


def test_handle_server_command_with_api_key():
    """Test the server command handler with API key authentication."""
    with patch("nekoconf.cli.main.NekoConfigManager") as mock_config_manager:
        with patch("nekoconf.cli.main.NekoConfigServer") as mock_web_server:
            # Set up mocked instance
            mock_instance = mock_config_manager.return_value

            # Create args object
            args = MagicMock()
            args.config = "config.yaml"
            args.host = "127.0.0.1"
            args.port = 9000
            args.schema = None
            args.reload = True
            args.api_key = "test-api-key"
            args.read_only = False

            # Handle command
            result = handle_server_command(args)
            # Should return success
            assert result == 0


def test_handle_server_command_error():
    """Test the server command handler with an error."""
    with patch("nekoconf.cli.main.NekoConfigServer") as mock_web_server:
        # Make the NekoConfigServer raise an exception
        mock_web_server.side_effect = Exception("Test server error")

        args = MagicMock()
        args.config = "config.yaml"
        args.host = "127.0.0.1"
        args.port = 9000
        args.schema = None
        args.reload = False
        args.api_key = None

        # Handle command
        result = handle_server_command(args)

        # Should return error
        assert result == 1


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


def test_handle_import_command_save_error(config_file, tmp_path):
    """Test the import command handler with save error."""
    # Create an import file
    import_file = tmp_path / "import.json"
    with open(import_file, "w") as f:
        json.dump({"server": {"host": "example.com"}}, f)

    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.import_file = str(import_file)
    args.deep_merge = True
    args.schema = None

    # Mock NekoConfigManager to return False on save
    with patch("nekoconf.cli.main.NekoConfigManager") as mock_config_manager:
        mock_instance = mock_config_manager.return_value
        mock_instance.save.return_value = False  # Indicates save failure

        # Handle command
        result = handle_import_command(args)

        # Should return error
        assert result == 1

        # Verify update and save were called
        mock_instance.update.assert_called_once()
        mock_instance.save.assert_called_once()


def test_handle_import_command_file_not_found(config_file, tmp_path):
    """Test the import command handler with a non-existent import file."""
    # Create args object with a non-existent file
    args = MagicMock()
    args.config = str(config_file)
    args.import_file = str(tmp_path / "nonexistent.json")
    args.deep_merge = True
    args.schema = None

    # Handle command
    result = handle_import_command(args)

    # Should return error
    assert result == 1


def test_handle_import_command_invalid_file(config_file, tmp_path):
    """Test the import command handler with an invalid import file."""
    # Create an invalid JSON file
    import_file = tmp_path / "invalid.json"
    with open(import_file, "w") as f:
        f.write("This is not valid JSON")

    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.import_file = str(import_file)
    args.deep_merge = True
    args.schema = None

    # Mock load_file to raise an exception
    with patch("nekoconf.cli.main.load_file") as mock_load:
        mock_load.side_effect = Exception("Invalid JSON")

        # Handle command
        result = handle_import_command(args)

        # Should return error
        assert result == 1


@patch("nekoconf.cli.main.NekoConfigManager")
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


def test_handle_validate_command_config_not_found(tmp_path):
    """Test the validate command handler with a non-existent config file."""
    # Create args object
    args = MagicMock()
    args.config = str(tmp_path / "nonexistent.yaml")
    args.schema = str(tmp_path / "schema.yaml")

    # Create schema file to pass existence check
    schema_file = tmp_path / "schema.yaml"
    schema_file.touch()

    # Handle command
    result = handle_validate_command(args)

    # Should return error
    assert result == 1


def test_handle_validate_command_schema_not_found(config_file, tmp_path):
    """Test the validate command handler with a non-existent schema file."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.schema = str(tmp_path / "nonexistent.yaml")

    # Handle command
    result = handle_validate_command(args)

    # Should return error
    assert result == 1


@patch("nekoconf.cli.main.NekoConfigManager")
def test_handle_validate_command_with_errors(mock_config_manager, config_file, schema_file):
    """Test the validate command handler with validation errors."""
    # Setup mock to simulate validation errors
    mock_instance = mock_config_manager.return_value
    mock_instance.validate.return_value = ["Error 1", "Error 2"]  # List of error messages

    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.schema = str(schema_file)

    # Handle command
    result = handle_validate_command(args)

    # Should return error
    assert result == 1

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


def test_handle_init_command_existing_file(config_file):
    """Test the init command handler with an existing file."""
    # Create args object with existing file
    args = MagicMock()
    args.config = str(config_file)
    args.template = None

    # Handle command
    result = handle_init_command(args)

    # Should return error
    assert result == 1


def test_handle_init_command_with_template(tmp_path):
    """Test the init command handler with a template."""
    # Create a template file
    template_data = {"server": {"host": "example.com", "port": 9000}}
    template_file = tmp_path / "template.yaml"
    with open(template_file, "w") as f:
        yaml.dump(template_data, f)

    # Create path for new config
    new_config = tmp_path / "new_config.yaml"

    # Create args object
    args = MagicMock()
    args.config = str(new_config)
    args.template = str(template_file)

    # Handle command
    result = handle_init_command(args)

    # Should return success
    assert result == 0

    # Verify file was created with template content
    assert new_config.exists()
    with open(new_config) as f:
        config = yaml.safe_load(f)

    assert config == template_data


def test_handle_init_command_template_not_found(tmp_path):
    """Test the init command handler with a non-existent template."""
    # Create path for new config
    new_config = tmp_path / "new_config.yaml"

    # Create args object with non-existent template
    args = MagicMock()
    args.config = str(new_config)
    args.template = str(tmp_path / "nonexistent.yaml")

    # Handle command
    result = handle_init_command(args)

    # Should return error
    assert result == 1

    # Verify file was not created
    assert not new_config.exists()


def test_handle_init_command_template_error(tmp_path):
    """Test the init command handler with an error loading the template."""
    # Create an invalid template file
    template_file = tmp_path / "invalid.yaml"
    with open(template_file, "w") as f:
        f.write("This is not valid YAML: :")

    # Create path for new config
    new_config = tmp_path / "new_config.yaml"

    # Create args object
    args = MagicMock()
    args.config = str(new_config)
    args.template = str(template_file)

    # Mock load_file to raise an exception
    with patch("nekoconf.cli.main.load_file") as mock_load:
        mock_load.side_effect = Exception("Invalid YAML")

        # Handle command
        result = handle_init_command(args)

        # Should return error
        assert result == 1

        # Verify file was not created
        assert not new_config.exists()


@patch("nekoconf.cli.main.handle_server_command")
@patch("nekoconf.cli.main.handle_get_command")
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
    with patch("nekoconf.cli.main.handle_get_command") as mock_handler:
        mock_handler.side_effect = Exception("Test error")

        result = main(["get", "--config", "config.yaml"])

    # Should return error
    assert result == 1


def test_main_version():
    """Test the main function with --version argument."""
    with patch("nekoconf.cli.main.__version__", "1.0.0"):
        with patch("builtins.print") as mock_print:
            result = main(["--version"])

            # Should print version and return success
            mock_print.assert_called_once_with("NekoConf version 1.0.0")
            assert result == 0


def test_main_no_command():
    """Test the main function with no command."""
    # Create a mock parser
    mock_parser = MagicMock()

    with patch("nekoconf.cli.main._create_parser", return_value=mock_parser):
        # Configure the mock parser
        mock_parser.parse_args.return_value = MagicMock(command=None, version=False)

        # Call main with no args
        result = main([])

        # Should print help and return error
        mock_parser.print_help.assert_called_once()
        assert result == 1


def test_main_unknown_command():
    """Test the main function with an unknown command."""
    # Create a mock parser
    mock_parser = MagicMock()

    with patch("nekoconf.cli.main._create_parser", return_value=mock_parser):
        # Configure the mock parser to return a command that doesn't exist
        mock_parser.parse_args.return_value = MagicMock(command="nonexistent", version=False)

        # Call main with unknown command
        result = main(["nonexistent"])

        # Should return error
        assert result == 1


def test_handle_get_command_with_key(config_file):
    """Test the get command handler with a specific key."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.key = "server.host"
    args.format = "raw"

    # Mock the print function
    with patch("builtins.print") as mock_print:
        # Handle command
        result = handle_get_command(args)

        # Should return success
        assert result == 0

        # Should print the value
        mock_print.assert_called_once()


def test_handle_get_command_all_config(config_file):
    """Test the get command handler to get all config."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.key = None
    args.format = "raw"

    # Mock the print function
    with patch("builtins.print") as mock_print:
        # Handle command
        result = handle_get_command(args)

        # Should return success
        assert result == 0

        # Should print the value
        mock_print.assert_called_once()


def test_handle_get_command_yaml_format(config_file):
    """Test the get command handler with YAML format."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.key = None
    args.format = "yaml"

    # Mock the yaml module
    with patch("yaml.dump", return_value="formatted yaml") as mock_yaml_dump:
        # Mock the print function
        with patch("builtins.print") as mock_print:
            # Handle command
            result = handle_get_command(args)

            # Should return success
            assert result == 0

            # Should print the formatted yaml
            mock_print.assert_called_once_with("formatted yaml")
            mock_yaml_dump.assert_called_once()


def test_handle_get_command_json_format(config_file):
    """Test the get command handler with JSON format."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.key = None
    args.format = "json"

    # Mock the json module
    with patch("json.dumps", return_value="formatted json") as mock_json_dumps:
        # Mock the print function
        with patch("builtins.print") as mock_print:
            # Handle command
            result = handle_get_command(args)

            # Should return success
            assert result == 0

            # Should print the formatted json
            mock_print.assert_called_once_with("formatted json")
            mock_json_dumps.assert_called_once()


def test_handle_get_command_config_load_error():
    """Test the get command handler with config loading error."""
    # Create a temporary config path that we won't actually use
    config_path = Path("/non/existent/path.yaml")

    # Create args object
    args = MagicMock()
    args.config = str(config_path)
    args.key = "server.host"
    args.format = "raw"

    # Mock NekoConfigManager to raise exception on load
    with patch("nekoconf.cli.main.NekoConfigManager") as mock_config_manager:
        mock_instance = mock_config_manager.return_value
        mock_instance.load.side_effect = Exception("Failed to load config")

        # Handle command
        result = handle_get_command(args)

        # Should return error
        assert result == 1


def test_handle_set_command_validation_error(config_file, schema_file):
    """Test the set command handler with validation errors."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.key = "server.host"
    args.value = "127.0.0.1"
    args.schema = str(schema_file)

    # Mock the validation to return errors
    with patch("nekoconf.cli.main.NekoConfigManager") as mock_config_manager:
        mock_instance = mock_config_manager.return_value
        mock_instance.validate.return_value = ["Error 1", "Error 2"]

        # Handle command
        result = handle_set_command(args)

        # Should return error
        assert result == 1

        # Verify validation was called
        mock_instance.validate.assert_called_once()


def test_handle_set_command_save_error(config_file):
    """Test the set command handler with save error."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.key = "server.host"
    args.value = "example.com"
    args.schema = None

    # Mock NekoConfigManager to return False on save
    with patch("nekoconf.cli.main.NekoConfigManager") as mock_config_manager:
        mock_instance = mock_config_manager.return_value
        mock_instance.save.return_value = False  # Indicates save failure

        # Handle command
        result = handle_set_command(args)

        # Should return error
        assert result == 1

        # Verify save was called
        mock_instance.save.assert_called_once()


def test_handle_delete_command_nonexistent_key(config_file):
    """Test the delete command handler with a nonexistent key."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.key = "nonexistent.key"
    args.schema = None

    # Handle command
    result = handle_delete_command(args)

    # Should return success (not finding a key is not an error)
    assert result == 0


def test_handle_delete_command_validation_error(config_file, schema_file):
    """Test the delete command handler with validation errors."""
    # Create args object
    args = MagicMock()
    args.config = str(config_file)
    args.key = "server.host"  # Key exists
    args.schema = str(schema_file)

    # Mock the delete and validate methods
    with patch("nekoconf.cli.main.NekoConfigManager") as mock_config_manager:
        mock_instance = mock_config_manager.return_value
        mock_instance.delete.return_value = True  # Key was deleted
        mock_instance.validate.return_value = ["Error 1", "Error 2"]  # Validation errors

        # Handle command
        result = handle_delete_command(args)

        # Should return error
        assert result == 1

        # Verify delete and validate were called
        mock_instance.delete.assert_called_once_with("server.host")
        mock_instance.validate.assert_called_once()
