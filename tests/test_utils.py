"""Tests for the utilities module.

This module provides comprehensive test coverage for the utility functions in NekoConf,
including file operations, data parsing, dictionary operations, and other helper functions.
"""

import logging
import os
from unittest.mock import Mock

import pytest
import yaml

from nekoconf.utils.helper import (
    create_file_if_not_exists,
    deep_merge,
    get_nested_value,
    getLogger,
    is_async_callable,
    load_file,
    parse_value,
    save_file,
    set_nested_value,
)


class TestFileOperations:
    """Test suite for file operation utility functions."""

    def test_create_file_if_not_exists(self, tmp_path):
        """Test creating a file if it doesn't exist.

        Verifies that:
        1. New file is created when it doesn't exist
        2. Existing files are not modified
        3. Parent directories are created as needed
        """
        # Test creating a new file
        new_file = tmp_path / "new_config.yaml"
        create_file_if_not_exists(new_file)
        assert new_file.exists()
        assert new_file.read_text() == ""  # Should be empty

        # Test with an existing file (shouldn't change content)
        existing_file = tmp_path / "existing_config.yaml"
        with open(existing_file, "w") as f:
            f.write("existing content")

        create_file_if_not_exists(existing_file)
        assert existing_file.exists()
        assert existing_file.read_text() == "existing content"

        # Test with nested directories that don't exist yet
        nested_file = tmp_path / "nested" / "dirs" / "config.yaml"
        create_file_if_not_exists(nested_file)
        assert nested_file.exists()

        # Test with permission errors
        if os.name != "nt":  # Skip on Windows where permissions work differently
            restricted_dir = tmp_path / "restricted"
            restricted_dir.mkdir(mode=0o000)  # No permissions

            try:
                restricted_file = restricted_dir / "config.yaml"
                with pytest.raises(IOError):
                    create_file_if_not_exists(restricted_file)
            finally:
                # Reset permissions so the directory can be cleaned up
                restricted_dir.chmod(0o755)

    def test_load_file_yaml(self, tmp_path):
        """Test loading YAML files.

        Verifies that:
        1. Valid YAML files are loaded correctly
        2. Invalid YAML files return empty dict and log error
        3. Non-existent files return empty dict and log warning
        """
        # Create and test a valid YAML file
        yaml_file = tmp_path / "config.yaml"
        test_data = {"server": {"host": "localhost", "port": 8000}}
        with open(yaml_file, "w") as f:
            yaml.dump(test_data, f)

        result = load_file(yaml_file)
        assert result == test_data

        # Test with invalid YAML
        invalid_file = tmp_path / "invalid.yaml"
        with open(invalid_file, "w") as f:
            f.write("server: {host: localhost, port: broken:}")

        # Create a mock logger and pass it directly to load_file
        mock_logger = Mock(spec=logging.Logger)
        result = load_file(invalid_file, logger=mock_logger)
        assert result == {}  # Should return empty dict
        mock_logger.error.assert_called_once()  # Should log an error

        # Test with non-existent file
        nonexistent = tmp_path / "nonexistent.yaml"
        mock_logger = Mock(spec=logging.Logger)
        result = load_file(nonexistent, logger=mock_logger)
        assert result == {}  # Should return empty dict
        mock_logger.warning.assert_called_once()  # Should log a warning

    def test_load_file_json(self, tmp_path):
        """Test loading JSON files.

        Verifies that:
        1. Valid JSON files are loaded correctly
        2. Invalid JSON files return empty dict and log error
        """
        # Create and test a valid JSON file
        json_file = tmp_path / "config.json"
        test_data = {"server": {"host": "localhost", "port": 8000}}
        with open(json_file, "w") as f:
            import json

            json.dump(test_data, f)

        result = load_file(json_file)
        assert result == test_data

        # Test with invalid JSON
        invalid_file = tmp_path / "invalid.json"
        with open(invalid_file, "w") as f:
            f.write('{"server": {"host": "localhost", "port": 8000,}}')  # Extra comma

        # Create a mock logger and pass it directly to load_file
        mock_logger = Mock(spec=logging.Logger)
        result = load_file(invalid_file, logger=mock_logger)
        assert result == {}  # Should return empty dict
        mock_logger.error.assert_called_once()  # Should log an error

    def test_load_file_toml(self, tmp_path):
        """Test loading TOML files if tomli/tomllib is available."""
        try:
            # Try importing tomli or tomllib
            try:
                import tomli
            except ImportError:
                try:
                    import tomllib as tomli
                except ImportError:
                    pytest.skip("TOML support not available")

            # Create a test TOML file
            toml_file = tmp_path / "config.toml"
            with open(toml_file, "w") as f:
                f.write(
                    """
                [server]
                host = "localhost"
                port = 8000
                
                [database]
                url = "sqlite:///test.db"
                """
                )

            # Load the TOML file
            result = load_file(toml_file)

            # Check the content
            assert result.get("server", {}).get("host") == "localhost"
            assert result.get("server", {}).get("port") == 8000
            assert result.get("database", {}).get("url") == "sqlite:///test.db"

            # Test with invalid TOML
            invalid_file = tmp_path / "invalid.toml"
            with open(invalid_file, "w") as f:
                f.write('[server]\nhost = "localhost"\nport = ')  # Incomplete assignment

            mock_logger = Mock(spec=logging.Logger)
            result = load_file(invalid_file, logger=mock_logger)
            assert result == {}
            mock_logger.error.assert_called_once()  # Should log an error

        except ImportError:
            pytest.skip("TOML support not available")

    def test_load_file_unknown_extension(self, tmp_path):
        """Test loading files with unknown extension.

        Verifies that files with unknown extensions are handled gracefully
        by trying to parse them as YAML.
        """
        # Create a file with unknown extension but valid YAML content
        unknown_file = tmp_path / "config.xyz"
        test_data = {"server": {"host": "localhost", "port": 8000}}
        with open(unknown_file, "w") as f:
            yaml.dump(test_data, f)

        result = load_file(unknown_file)
        assert result == test_data

    def test_save_file_yaml(self, tmp_path):
        """Test saving data to YAML files.

        Verifies that:
        1. Data is correctly saved to YAML files
        2. Parent directories are created as needed
        """
        test_data = {"server": {"host": "localhost", "port": 8000}}

        # Test saving to a YAML file
        yaml_file = tmp_path / "config.yaml"
        assert save_file(yaml_file, test_data)

        # Verify the content
        with open(yaml_file) as f:
            loaded_data = yaml.safe_load(f)
        assert loaded_data == test_data

        # Test saving to a nested path (should create parent directories)
        nested_file = tmp_path / "nested" / "dirs" / "config.yaml"
        assert save_file(nested_file, test_data)
        assert nested_file.exists()

        # Verify the content
        with open(nested_file) as f:
            loaded_data = yaml.safe_load(f)
        assert loaded_data == test_data

    def test_save_file_json(self, tmp_path):
        """Test saving data to JSON files.

        Verifies that data is correctly saved to JSON files.
        """
        test_data = {"server": {"host": "localhost", "port": 8000}}

        # Test saving to a JSON file
        json_file = tmp_path / "config.json"
        assert save_file(json_file, test_data)

        # Verify the content
        with open(json_file) as f:
            import json

            loaded_data = json.load(f)
        assert loaded_data == test_data

    def test_save_file_toml(self, tmp_path):
        """Test saving data to TOML files if tomli_w is available."""
        try:
            import tomli_w

            test_data = {"server": {"host": "localhost", "port": 8000}}

            # Test saving to a TOML file
            toml_file = tmp_path / "config.toml"
            assert save_file(toml_file, test_data)

            # Verify the content
            try:
                import tomli

                with open(toml_file, "rb") as f:
                    loaded_data = tomli.load(f)
            except ImportError:
                try:
                    import tomllib

                    with open(toml_file, "rb") as f:
                        loaded_data = tomllib.load(f)
                except ImportError:
                    pytest.skip("TOML read support not available")

            assert loaded_data == test_data

        except ImportError:
            pytest.skip("TOML write support not available")

    def test_save_file_errors(self, tmp_path):
        """Test error handling when saving files.

        Verifies that:
        1. Permission errors are handled properly
        2. Other IO errors are handled properly
        """
        test_data = {"server": {"host": "localhost", "port": 8000}}

        # Test with permission errors
        if os.name != "nt":  # Skip on Windows where permissions work differently
            restricted_dir = tmp_path / "restricted"
            restricted_dir.mkdir(mode=0o400)  # Read-only

            try:
                restricted_file = restricted_dir / "config.yaml"
                # Create a mock logger and pass it directly to save_file
                mock_logger = Mock(spec=logging.Logger)
                result = save_file(restricted_file, test_data, logger=mock_logger)
                assert not result  # Should return False
                mock_logger.error.assert_called_once()  # Should log an error
            finally:
                # Reset permissions so the directory can be cleaned up
                restricted_dir.chmod(0o755)


class TestDataParsing:
    """Test suite for data parsing utility functions."""

    def test_parse_value_numbers(self):
        """Test parsing numeric string values.

        Verifies proper parsing of:
        1. Integers (positive, negative, zero)
        2. Floats (positive, negative)
        """
        # Test integer parsing
        assert parse_value("42") == 42
        assert parse_value("-42") == -42
        assert parse_value("0") == 0

        # Test float parsing
        assert parse_value("3.14") == 3.14
        assert parse_value("-3.14") == -3.14
        assert parse_value("0.0") == 0.0
        assert parse_value(".5") == 0.5

    def test_parse_value_booleans(self):
        """Test parsing boolean string values.

        Verifies proper parsing of:
        1. True values (true, True, TRUE)
        2. False values (false, False, FALSE)
        """
        # Test boolean parsing - case insensitive
        assert parse_value("true") is True
        assert parse_value("True") is True
        assert parse_value("TRUE") is True

        assert parse_value("false") is False
        assert parse_value("False") is False
        assert parse_value("FALSE") is False

    def test_parse_value_none(self):
        """Test parsing null/None string values.

        Verifies proper parsing of:
        1. Null values (null, NULL, none, None)
        2. Empty strings
        """
        # Test null parsing - case insensitive
        assert parse_value("null") is None
        assert parse_value("NULL") is None
        assert parse_value("None") is None
        assert parse_value("none") is None

        # Test empty string
        assert parse_value("") == ""

    def test_parse_value_json(self):
        """Test parsing JSON string values.

        Verifies proper parsing of:
        1. JSON objects
        2. JSON arrays
        3. JSON strings (quoted)
        """
        # Test JSON parsing
        assert parse_value('{"a": 1, "b": 2}') == {"a": 1, "b": 2}
        assert parse_value("[1, 2, 3]") == [1, 2, 3]
        assert parse_value('"string"') == "string"

        # Test nested JSON
        assert parse_value('{"a": {"b": [1, 2, 3]}}') == {"a": {"b": [1, 2, 3]}}

    def test_parse_value_strings(self):
        """Test parsing string values.

        Verifies proper handling of:
        1. Regular strings
        2. Mixed content strings
        3. Special characters
        """
        # Regular strings should remain as strings
        assert parse_value("hello") == "hello"
        assert parse_value("12abc") == "12abc"  # Not a pure number

        # Special characters and patterns
        assert parse_value("hello:world") == "hello:world"
        assert parse_value("127.0.0.1") == "127.0.0.1"  # IP address-like
        assert parse_value("2023-01-01") == "2023-01-01"  # Date-like


class TestDictionaryOperations:
    """Test suite for dictionary operation utility functions."""

    def test_deep_merge_basic(self):
        """Test basic deep merging of dictionaries.

        Verifies:
        1. Simple key merging
        2. Source values override destination values
        3. Source and destination are not modified
        """
        # Basic merge
        a = {"a": 1, "b": 2}
        b = {"b": 3, "c": 4}

        result = deep_merge(b, a)

        # b values should override a values
        assert result == {"a": 1, "b": 3, "c": 4}

        # Original dictionaries should not be modified
        assert a == {"a": 1, "b": 2}
        assert b == {"b": 3, "c": 4}

    def test_deep_merge_nested(self):
        """Test deep merging of nested dictionaries.

        Verifies:
        1. Nested dictionaries are recursively merged
        2. Values at all levels are properly overridden
        """
        # Nested merge
        a = {"server": {"host": "localhost", "port": 8000}, "client": {"timeout": 30}}
        b = {
            "server": {"port": 9000, "debug": True},
            "database": {"url": "sqlite:///test.db"},
        }

        result = deep_merge(b, a)

        # Check nested merging
        assert result["server"]["host"] == "localhost"  # From a
        assert result["server"]["port"] == 9000  # From b (override)
        assert result["server"]["debug"] is True  # From b (new key)
        assert result["client"]["timeout"] == 30  # From a
        assert result["database"]["url"] == "sqlite:///test.db"  # From b

        # Original dictionaries should not be modified
        assert a["server"] == {"host": "localhost", "port": 8000}
        assert b["server"] == {"port": 9000, "debug": True}

    def test_deep_merge_with_lists(self):
        """Test deep merging with lists.

        Verifies:
        1. Lists are replaced, not merged
        2. Lists inside dictionaries are handled correctly
        """
        # Merge with lists
        a = {"list": [1, 2, 3], "dict": {"list": [4, 5, 6]}}
        b = {"list": [7, 8, 9], "dict": {"list": [10, 11, 12]}}

        result = deep_merge(b, a)

        # Lists should be replaced, not merged
        assert result["list"] == [7, 8, 9]  # From b (replace)
        assert result["dict"]["list"] == [10, 11, 12]  # From b (replace)

    def test_deep_merge_edge_cases(self):
        """Test deep merging edge cases.

        Verifies:
        1. Non-dictionary values are handled correctly
        2. None values are handled correctly
        3. Empty dictionaries are handled correctly
        """
        # Test with non-dict values
        assert deep_merge("source", {"key": "value"}) == "source"
        assert deep_merge(123, {"key": "value"}) == 123
        assert deep_merge(None, {"key": "value"}) is None

        # Test with one empty dict
        assert deep_merge({}, {"key": "value"}) == {"key": "value"}
        assert deep_merge({"key": "value"}, {}) == {"key": "value"}

        # Test with both empty dicts
        assert deep_merge({}, {}) == {}

        # Test with None values in dict
        a = {"a": None, "b": 2}
        b = {"b": None, "c": 3}
        result = deep_merge(b, a)
        assert result == {"a": None, "b": None, "c": 3}

    def test_get_nested_value_basic(self):
        """Test basic retrieval of nested values.

        Verifies:
        1. Top-level key access
        2. Nested key access with dot notation
        3. Default values for missing keys
        """
        data = {
            "server": {"host": "localhost", "port": 8000, "debug": True},
            "database": {"url": "sqlite:///test.db", "pool_size": 5},
        }

        # Top-level keys
        assert get_nested_value(data, "server") == data["server"]
        assert get_nested_value(data, "database") == data["database"]

        # Nested keys
        assert get_nested_value(data, "server.host") == "localhost"
        assert get_nested_value(data, "server.port") == 8000
        assert get_nested_value(data, "server.debug") is True
        assert get_nested_value(data, "database.url") == "sqlite:///test.db"
        assert get_nested_value(data, "database.pool_size") == 5

        # Missing keys
        assert get_nested_value(data, "nonexistent") is None
        assert get_nested_value(data, "server.nonexistent") is None
        assert get_nested_value(data, "nonexistent.key") is None

        # Default values
        assert get_nested_value(data, "nonexistent", "default") == "default"
        assert get_nested_value(data, "server.nonexistent", 42) == 42

    def test_set_nested_value_basic(self):
        """Test basic setting of nested values.

        Verifies:
        1. Setting top-level keys
        2. Setting nested keys with dot notation
        3. Setting values in empty dictionaries
        """
        # Start with empty dict
        data = {}

        # Set a top-level key
        set_nested_value(data, "name", "test")
        assert data == {"name": "test"}

        # Set a nested key
        set_nested_value(data, "server.host", "localhost")
        assert data["server"] == {"host": "localhost"}

        # Set another nested key in existing section
        set_nested_value(data, "server.port", 8000)
        assert data["server"] == {"host": "localhost", "port": 8000}

        # Set a deeply nested key
        set_nested_value(data, "database.credentials.username", "admin")
        assert data["database"]["credentials"]["username"] == "admin"

        # Update an existing value
        set_nested_value(data, "server.host", "0.0.0.0")
        assert data["server"]["host"] == "0.0.0.0"

        # Set a None value
        set_nested_value(data, "debug", None)
        assert data["debug"] is None

    def test_set_nested_value_return_value(self):
        """Test return value of set_nested_value.

        Verifies:
        1. Returns True when value changes
        2. Returns False when value doesn't change
        """
        data = {"server": {"host": "localhost"}}

        # Setting a new value should return True
        assert set_nested_value(data, "server.port", 8000) is True

        # Setting an existing value to the same value should return False
        assert set_nested_value(data, "server.host", "localhost") is False

        # Setting an existing value to a different value should return True
        assert set_nested_value(data, "server.host", "0.0.0.0") is True

        # Setting a value at a new path should return True
        assert set_nested_value(data, "database.url", "sqlite:///test.db") is True

        # Empty key should return False
        assert set_nested_value(data, "", "value") is False

    def test_set_nested_value_complex_paths(self):
        """Test setting values with complex nested paths.

        Verifies:
        1. Deep nesting works correctly
        2. Intermediate dictionaries are created as needed
        """
        data = {}

        # Set a deeply nested path
        set_nested_value(data, "a.b.c.d.e.f", "value")
        assert data["a"]["b"]["c"]["d"]["e"]["f"] == "value"

        # Update a middle section
        set_nested_value(data, "a.b.new", "middle")
        assert data["a"]["b"]["new"] == "middle"
        assert data["a"]["b"]["c"]["d"]["e"]["f"] == "value"  # Original still intact

        # Ensure all intermediate dictionaries were created
        assert isinstance(data["a"], dict)
        assert isinstance(data["a"]["b"], dict)
        assert isinstance(data["a"]["b"]["c"], dict)
        assert isinstance(data["a"]["b"]["c"]["d"], dict)
        assert isinstance(data["a"]["b"]["c"]["d"]["e"], dict)


class TestAsyncUtils:
    """Test suite for async-related utility functions."""

    def test_is_async_callable_functions(self):
        """Test async detection for regular and async functions.

        Verifies that:
        1. Async functions are correctly identified
        2. Regular functions are correctly identified as non-async
        """

        # Regular function
        def regular_func():
            pass

        # Async function
        async def async_func():
            pass

        assert not is_async_callable(regular_func)
        assert is_async_callable(async_func)

    def test_is_async_callable_methods(self):
        """Test async detection for class methods.

        Verifies that:
        1. Async methods are correctly identified
        2. Regular methods are correctly identified as non-async
        """

        class TestClass:
            def regular_method(self):
                pass

            async def async_method(self):
                pass

        obj = TestClass()
        assert not is_async_callable(obj.regular_method)
        assert is_async_callable(obj.async_method)

    def test_is_async_callable_callable_objects(self):
        """Test async detection for callable objects.

        Verifies that:
        1. Objects with async __call__ are identified as async
        2. Objects with regular __call__ are identified as non-async
        """

        class RegularCallable:
            def __call__(self):
                pass

        class AsyncCallable:
            async def __call__(self):
                pass

        assert not is_async_callable(RegularCallable())
        assert is_async_callable(AsyncCallable())

    def test_is_async_callable_lambdas_and_other(self):
        """Test async detection for lambdas and other callables.

        Verifies that:
        1. Lambdas are correctly identified as non-async
        2. Built-in functions are correctly identified
        """
        # Lambda function (always non-async)
        lambda_func = lambda: None
        assert not is_async_callable(lambda_func)

        # Built-in function
        assert not is_async_callable(len)

        # Non-callable
        assert not is_async_callable("string")
        assert not is_async_callable(123)

    def test_is_async_callable_awaitable(self):
        """Test async detection for awaitable objects.

        Verifies that objects implementing __await__ are identified as async.
        """

        class CustomAwaitable:
            def __await__(self):
                yield from []

        assert is_async_callable(CustomAwaitable())
