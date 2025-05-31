#!/usr/bin/env python3
"""Test script to demonstrate the improved EnvOverrideHandler functionality."""

import logging
import os

from nekoconf.utils.env import EnvOverrideHandler

# Set up logging
logging.basicConfig(level=logging.DEBUG)


def test_basic_functionality():
    """Test basic environment variable override functionality."""
    print("=== Testing Basic Functionality ===")

    # Set up test environment variables
    os.environ["NEKOCONF_DATABASE_HOST"] = "localhost"
    os.environ["NEKOCONF_DATABASE_PORT"] = "5432"
    os.environ["NEKOCONF_API_TIMEOUT"] = "30.5"
    os.environ["NEKOCONF_DEBUG"] = "true"
    os.environ["NEKOCONF_FEATURES_NEW_UI"] = "false"

    # Test config data
    config_data = {
        "database": {"host": "production.example.com", "port": 3306, "username": "admin"},
        "api": {"timeout": 10},
        "debug": False,
    }

    # Create handler and apply overrides
    handler = EnvOverrideHandler()
    result = handler.apply_overrides(config_data)

    print("Original config:", config_data)
    print("Result with overrides:", result)

    # Verify results
    assert result["database"]["host"] == "localhost"
    assert result["database"]["port"] == 5432
    assert result["api"]["timeout"] == 30.5
    assert result["debug"] is True
    assert result["features"]["new"]["ui"] is False

    print("✓ Basic functionality test passed\n")


def test_path_filtering():
    """Test include/exclude path filtering."""
    print("=== Testing Path Filtering ===")

    # Set up test environment variables
    os.environ["NEKOCONF_DATABASE_HOST"] = "filtered-host"
    os.environ["NEKOCONF_API_TIMEOUT"] = "99"
    os.environ["NEKOCONF_CACHE_SIZE"] = "1000"

    config_data = {"database": {"host": "original"}, "api": {"timeout": 10}, "cache": {"size": 100}}

    # Test with include paths
    handler = EnvOverrideHandler(include_paths=["database"])
    result = handler.apply_overrides(config_data)

    assert result["database"]["host"] == "filtered-host"
    assert result["api"]["timeout"] == 10  # Should not be overridden
    assert result["cache"]["size"] == 100  # Should not be overridden

    # Test with exclude paths
    handler = EnvOverrideHandler(exclude_paths=["api"])
    result = handler.apply_overrides(config_data)

    assert result["database"]["host"] == "filtered-host"
    assert result["api"]["timeout"] == 10  # Should not be overridden
    assert result["cache"]["size"] == 1000  # Should be overridden

    print("✓ Path filtering test passed\n")


def test_case_preservation():
    """Test case preservation functionality."""
    print("=== Testing Case Preservation ===")

    # Set up test environment variables with mixed case
    os.environ["NEKOCONF_API_EndPoint"] = "https://api.example.com"

    config_data = {"api": {"endpoint": "http://localhost"}}

    # Test without case preservation
    handler = EnvOverrideHandler(preserve_case=False)
    result = handler.apply_overrides(config_data)

    # With preserve_case=False, should use lowercase
    assert result["api"]["endpoint"] == "https://api.example.com"

    # Test with case preservation
    handler = EnvOverrideHandler(preserve_case=True)
    result = handler.apply_overrides(config_data)

    print("Result with case preservation:", result)
    print("✓ Case preservation test passed\n")


def test_no_prefix():
    """Test functionality without prefix."""
    print("=== Testing No Prefix Mode ===")

    # Set up test environment variables without prefix
    os.environ["TEST_VAR"] = "test_value"

    config_data = {}

    # Create handler without prefix
    handler = EnvOverrideHandler(prefix="")
    result = handler.apply_overrides(config_data)

    print("Result without prefix:", result)
    print("✓ No prefix test completed\n")


def test_error_handling():
    """Test error handling and strict parsing."""
    print("=== Testing Error Handling ===")

    # Set up test environment variable with potentially problematic value
    os.environ["NEKOCONF_INVALID_JSON"] = '{"invalid": json}'

    config_data = {}

    # Test with non-strict parsing (should log warning but continue)
    handler = EnvOverrideHandler(strict_parsing=False)
    result = handler.apply_overrides(config_data)

    print("Result with non-strict parsing:", result)

    # Test with strict parsing (should raise exception)
    handler = EnvOverrideHandler(strict_parsing=True)
    try:
        result = handler.apply_overrides(config_data)
        print("Unexpected: strict parsing should have failed")
    except ValueError as e:
        print(f"Expected error with strict parsing: {e}")

    print("✓ Error handling test passed\n")


def test_numeric_variables():
    """Test handling of numeric variable names (previously problematic)."""
    print("=== Testing Numeric Variables ===")

    cleanup_env_vars()  # Ensure no previous test variables interfere

    # Set up test environment variables with numbers
    os.environ["NEKOCONF_SERVER1_HOST"] = "server1.example.com"
    os.environ["NEKOCONF_PORT8080"] = "8080"
    os.environ["NEKOCONF_VERSION2_ENABLED"] = "true"
    os.environ["NEKOCONF_DB_CONNECTION_123"] = "connection_string"

    config_data = {}

    handler = EnvOverrideHandler()
    result = handler.apply_overrides(config_data)

    print("Result with numeric variables:", result)

    # Verify numeric handling works correctly
    assert result["server1"]["host"] == "server1.example.com"
    assert result["port8080"] == 8080
    assert result["version2"]["enabled"] is True
    assert result["db"]["connection"]["123"] == "connection_string"

    print("✓ Numeric variables test passed\n")


def test_custom_delimiter():
    """Test custom nested delimiter functionality."""
    print("=== Testing Custom Delimiter ===")

    # Set up test environment variables with custom delimiter
    os.environ["CUSTOM__API__URL"] = "https://custom.api.com"
    os.environ["CUSTOM__DB__MAX__CONNECTIONS"] = "100"

    config_data = {}

    # Test with double underscore delimiter
    handler = EnvOverrideHandler(prefix="CUSTOM", nested_delimiter="__")
    result = handler.apply_overrides(config_data)

    print("Result with custom delimiter:", result)

    assert result["api"]["url"] == "https://custom.api.com"
    assert result["db"]["max"]["connections"] == 100

    print("✓ Custom delimiter test passed\n")


def test_value_type_parsing():
    """Test parsing of different value types."""
    print("=== Testing Value Type Parsing ===")

    # Set up various data types
    os.environ["NEKOCONF_STRING_VAL"] = "simple_string"
    os.environ["NEKOCONF_INT_VAL"] = "42"
    os.environ["NEKOCONF_FLOAT_VAL"] = "3.14159"
    os.environ["NEKOCONF_BOOL_TRUE"] = "true"
    os.environ["NEKOCONF_BOOL_FALSE"] = "false"
    os.environ["NEKOCONF_NULL_VAL"] = "null"
    os.environ["NEKOCONF_EMPTY_VAL"] = ""
    os.environ["NEKOCONF_JSON_ARRAY"] = '["item1", "item2", "item3"]'
    os.environ["NEKOCONF_JSON_OBJECT"] = '{"key": "value", "number": 123}'

    config_data = {}

    handler = EnvOverrideHandler()
    result = handler.apply_overrides(config_data)

    print("Result with various types:", result)

    # Verify type parsing
    assert isinstance(result["string"]["val"], str)
    assert isinstance(result["int"]["val"], int) and result["int"]["val"] == 42
    assert (
        isinstance(result["float"]["val"], float) and abs(result["float"]["val"] - 3.14159) < 0.0001
    )
    assert isinstance(result["bool"]["true"], bool) and result["bool"]["true"] is True
    assert isinstance(result["bool"]["false"], bool) and result["bool"]["false"] is False
    assert result["null"]["val"] is None
    assert result["empty"]["val"] == ""
    assert isinstance(result["json"]["array"], list) and len(result["json"]["array"]) == 3
    assert isinstance(result["json"]["object"], dict) and result["json"]["object"]["key"] == "value"

    print("✓ Value type parsing test passed\n")


def test_invalid_delimiter_patterns():
    """Test handling of invalid delimiter patterns."""
    print("=== Testing Invalid Delimiter Patterns ===")

    # Set up environment variables with invalid patterns
    os.environ["NEKOCONF__LEADING_DELIMITER"] = "value1"
    os.environ["NEKOCONF_TRAILING_DELIMITER_"] = "value2"
    os.environ["NEKOCONF_DOUBLE__DELIMITER"] = "value3"
    os.environ["NEKOCONF_"] = "empty_key"

    config_data = {}

    handler = EnvOverrideHandler()
    result = handler.apply_overrides(config_data)

    print("Result with invalid patterns (should be filtered):", result)

    # These should be filtered out due to invalid patterns
    assert "leading" not in str(result)
    assert "trailing" not in str(result)
    assert "double" not in str(result)

    print("✓ Invalid delimiter patterns test passed\n")


def test_in_place_modification():
    """Test in-place modification functionality."""
    print("=== Testing In-Place Modification ===")

    os.environ["NEKOCONF_NEW_KEY"] = "new_value"

    config_data = {"existing": "data"}
    original_id = id(config_data)

    # Test in-place modification
    handler = EnvOverrideHandler()
    result = handler.apply_overrides(config_data, in_place=True)

    print("Original after in-place:", config_data)
    print("Result:", result)

    # Should be the same object
    assert id(result) == original_id
    assert result is config_data
    assert result["new"]["key"] == "new_value"

    # Test copy mode
    config_data2 = {"existing": "data"}
    original_id2 = id(config_data2)
    result2 = handler.apply_overrides(config_data2, in_place=False)

    # Should be different objects
    assert id(result2) != original_id2
    assert result2 is not config_data2

    print("✓ In-place modification test passed\n")


def test_system_variables_filtering():
    """Test that system variables are properly filtered when no prefix is used."""
    print("=== Testing System Variables Filtering ===")

    # These should be ignored when no prefix is used
    original_path = os.environ.get("PATH", "")
    original_home = os.environ.get("HOME", "")

    config_data = {}

    handler = EnvOverrideHandler(prefix="")
    result = handler.apply_overrides(config_data)

    print("Result without system vars:", result)

    # System variables should not appear in config
    assert "path" not in result
    assert "home" not in result
    assert "_" not in result

    print("✓ System variables filtering test passed\n")


def test_include_exclude_precedence():
    """Test that exclude paths take precedence over include paths."""
    print("=== Testing Include/Exclude Precedence ===")

    os.environ["NEKOCONF_API_KEY"] = "secret_key"
    os.environ["NEKOCONF_API_TIMEOUT"] = "30"
    os.environ["NEKOCONF_DB_HOST"] = "localhost"

    config_data = {}

    # Include 'api' but exclude 'api.key' - exclude should win
    handler = EnvOverrideHandler(include_paths=["api"], exclude_paths=["api.key"])
    result = handler.apply_overrides(config_data)

    print("Result with precedence test:", result)

    # api.timeout should be included, api.key should be excluded
    assert result["api"]["timeout"] == 30
    assert "key" not in result.get("api", {})
    assert "db" not in result  # Not in include list

    print("✓ Include/exclude precedence test passed\n")


def test_deep_nested_overrides():
    """Test deeply nested configuration overrides."""
    print("=== Testing Deep Nested Overrides ===")

    os.environ["NEKOCONF_APP_FEATURES_AUTH_OAUTH_GOOGLE_CLIENT"] = "google_client_123"
    os.environ["NEKOCONF_APP_FEATURES_AUTH_OAUTH_GITHUB_CLIENT"] = "github_client_456"

    config_data = {
        "app": {
            "features": {
                "auth": {
                    "oauth": {
                        "google": {"client": "old_google"},
                        "github": {"client": "old_github"},
                    }
                }
            }
        }
    }

    handler = EnvOverrideHandler()
    result = handler.apply_overrides(config_data)

    print("Result with deep nesting:", result)

    # Check if overrides were applied
    assert result["app"]["features"]["auth"]["oauth"]["google"]["client"] == "google_client_123"
    assert result["app"]["features"]["auth"]["oauth"]["github"]["client"] == "github_client_456"

    print("✓ Deep nested overrides test passed\n")


def test_empty_config_data():
    """Test handling of empty configuration data."""
    print("=== Testing Empty Config Data ===")

    os.environ["NEKOCONF_NEW_CONFIG"] = "from_env"

    config_data = {}

    handler = EnvOverrideHandler()
    result = handler.apply_overrides(config_data)

    print("Result with empty config:", result)

    assert result["new"]["config"] == "from_env"

    print("✓ Empty config data test passed\n")


def test_edge_cases():
    """Test various edge cases and boundary conditions."""
    print("=== Testing Edge Cases ===")

    # Test single character delimiters
    os.environ["EDGE-API-URL"] = "https://edge.api.com"
    handler = EnvOverrideHandler(prefix="EDGE", nested_delimiter="-")
    result = handler.apply_overrides({})
    assert result["api"]["url"] == "https://edge.api.com"

    # Test with None environment value edge case (shouldn't happen in real world)
    # This tests robustness of our code
    os.environ["NEKOCONF_EDGE_TEST"] = "test_value"
    handler = EnvOverrideHandler()
    result = handler.apply_overrides({})
    assert result["edge"]["test"] == "test_value"

    print("✓ Edge cases test passed\n")


def test_prefix_with_underscore():
    """Test prefix handling with underscores."""
    print("=== Testing Prefix with Underscore ===")

    # Test prefix that already ends with underscore
    os.environ["TEST__CONFIG__VALUE"] = "test_val"
    handler = EnvOverrideHandler(prefix="TEST_", nested_delimiter="__")
    result = handler.apply_overrides({})

    print("Result with underscore prefix:", result)
    assert result["config"]["value"] == "test_val"

    print("✓ Prefix with underscore test passed\n")


def test_case_sensitive_matching():
    """Test case-sensitive environment variable matching."""
    print("=== Testing Case Sensitive Matching ===")

    # Different case variations
    os.environ["NEKOCONF_CamelCase_Key"] = "camel_value"
    os.environ["NEKOCONF_SNAKE_CASE_KEY"] = "snake_value"
    os.environ["NEKOCONF_MixedCase_UPPER_lower"] = "mixed_value"

    config_data = {}

    # Test without case preservation
    handler = EnvOverrideHandler(preserve_case=False)
    result = handler.apply_overrides(config_data)

    print("Result without case preservation:", result)
    assert result["camelcase"]["key"] == "camel_value"
    assert result["snake"]["case"]["key"] == "snake_value"
    assert result["mixedcase"]["upper"]["lower"] == "mixed_value"

    # Test with case preservation
    handler = EnvOverrideHandler(preserve_case=True)
    result = handler.apply_overrides(config_data)

    print("Result with case preservation:", result)
    assert result["CamelCase"]["Key"] == "camel_value"
    assert result["SNAKE"]["CASE"]["KEY"] == "snake_value"
    assert result["MixedCase"]["UPPER"]["lower"] == "mixed_value"

    print("✓ Case sensitive matching test passed\n")


def test_existing_data_preservation():
    """Test that existing configuration data is preserved when not overridden."""
    print("=== Testing Existing Data Preservation ===")

    os.environ["NEKOCONF_OVERRIDE_KEY"] = "new_value"

    config_data = {
        "existing": {"untouched": "original", "nested": {"deep": "value"}},
        "override": {"key": "old_value", "other": "preserved"},
        "another": "section",
    }

    handler = EnvOverrideHandler()
    result = handler.apply_overrides(config_data)

    print("Result with preservation:", result)

    # Original data should be preserved
    assert result["existing"]["untouched"] == "original"
    assert result["existing"]["nested"]["deep"] == "value"
    assert result["override"]["other"] == "preserved"
    assert result["another"] == "section"

    # Only the specific override should change
    assert result["override"]["key"] == "new_value"

    print("✓ Existing data preservation test passed\n")


def test_no_environment_variables():
    """Test behavior when no matching environment variables exist."""
    print("=== Testing No Environment Variables ===")

    # Clean up all test variables first
    cleanup_env_vars()

    config_data = {"existing": "data"}

    handler = EnvOverrideHandler()
    result = handler.apply_overrides(config_data)

    print("Result with no env vars:", result)

    # Should return unchanged data
    assert result == config_data

    print("✓ No environment variables test passed\n")


def test_special_characters_in_values():
    """Test handling of special characters in environment variable values."""
    print("=== Testing Special Characters in Values ===")

    # Test various special characters
    os.environ["NEKOCONF_SPECIAL_CHARS"] = "special!@#$%^&*()chars"
    os.environ["NEKOCONF_UNICODE_VALUE"] = "unicode_测试_éñ_value"
    os.environ["NEKOCONF_MULTILINE"] = "line1\nline2\nline3"
    os.environ["NEKOCONF_SPACES"] = "  value with spaces  "

    config_data = {}

    handler = EnvOverrideHandler()
    result = handler.apply_overrides(config_data)

    print("Result with special chars:", result)

    assert result["special"]["chars"] == "special!@#$%^&*()chars"
    assert result["unicode"]["value"] == "unicode_测试_éñ_value"
    assert result["multiline"] == "line1\nline2\nline3"
    assert result["spaces"] == "  value with spaces  "

    print("✓ Special characters test passed\n")


def test_logger_integration():
    """Test custom logger integration."""
    print("=== Testing Logger Integration ===")

    # Create a custom logger to test integration
    import logging

    test_logger = logging.getLogger("test_env_handler")
    test_logger.setLevel(logging.DEBUG)

    # Create handler to capture log messages
    log_handler = logging.StreamHandler()
    test_logger.addHandler(log_handler)

    os.environ["NEKOCONF_LOGGER_TEST"] = "test_value"

    config_data = {}

    # Test with custom logger
    handler = EnvOverrideHandler(logger=test_logger)
    result = handler.apply_overrides(config_data)

    print("Result with custom logger:", result)
    assert result["logger"]["test"] == "test_value"

    print("✓ Logger integration test passed\n")


def test_empty_prefix_warning():
    """Test that warning is logged when using empty prefix."""
    print("=== Testing Empty Prefix Warning ===")

    # This should trigger a warning
    handler = EnvOverrideHandler(prefix="")

    # The warning should be logged during initialization
    print("✓ Empty prefix warning test passed\n")


def test_complex_json_parsing():
    """Test parsing of complex JSON structures."""
    print("=== Testing Complex JSON Parsing ===")

    # Complex nested JSON
    complex_json = '{"users": [{"name": "Alice", "roles": ["admin", "user"]}, {"name": "Bob", "roles": ["user"]}], "settings": {"timeout": 30, "retries": 3}}'
    os.environ["NEKOCONF_COMPLEX_DATA"] = complex_json

    config_data = {}

    handler = EnvOverrideHandler()
    result = handler.apply_overrides(config_data)

    print("Result with complex JSON:", result)

    assert isinstance(result["complex"]["data"], dict)
    assert len(result["complex"]["data"]["users"]) == 2
    assert result["complex"]["data"]["users"][0]["name"] == "Alice"
    assert "admin" in result["complex"]["data"]["users"][0]["roles"]
    assert result["complex"]["data"]["settings"]["timeout"] == 30

    print("✓ Complex JSON parsing test passed\n")


def test_include_exact_match():
    """Test exact path matching in include/exclude rules."""
    print("=== Testing Include Exact Match ===")

    os.environ["NEKOCONF_API_VERSION"] = "v1"
    os.environ["NEKOCONF_API_VERSION_DETAIL"] = "v1.2.3"

    config_data = {}

    # Include only exact match "api.version"
    handler = EnvOverrideHandler(include_paths=["api.version.detail"])
    result = handler.apply_overrides(config_data)

    print("Result with exact include:", result)

    # Should include api.version but not api.version.detail
    assert result["api"]["version"]["detail"] == "v1.2.3"

    print("✓ Include exact match test passed\n")


def run_all_tests():
    """Run all test functions."""
    print("Starting comprehensive EnvOverrideHandler tests...\n")

    try:
        test_basic_functionality()
        test_path_filtering()
        test_case_preservation()
        test_no_prefix()
        test_error_handling()
        test_numeric_variables()
        test_custom_delimiter()
        test_value_type_parsing()
        test_invalid_delimiter_patterns()
        test_in_place_modification()
        test_system_variables_filtering()
        test_include_exclude_precedence()
        test_deep_nested_overrides()
        test_empty_config_data()
        test_edge_cases()
        test_prefix_with_underscore()
        test_case_sensitive_matching()
        test_existing_data_preservation()
        test_no_environment_variables()
        test_special_characters_in_values()
        test_logger_integration()
        test_empty_prefix_warning()
        test_complex_json_parsing()
        test_include_exact_match()

        print("🎉 All tests passed successfully!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise
    finally:
        cleanup_env_vars()


def cleanup_env_vars():
    """Clean up test environment variables."""
    test_vars = [
        "NEKOCONF_DATABASE_HOST",
        "NEKOCONF_DATABASE_PORT",
        "NEKOCONF_API_TIMEOUT",
        "NEKOCONF_DEBUG",
        "NEKOCONF_FEATURES_NEW_UI",
        "NEKOCONF_CACHE_SIZE",
        "NEKOCONF_API_EndPoint",
        "NEKOCONF_INVALID_JSON",
        "TEST_VAR",
        # Numeric variables
        "NEKOCONF_SERVER1_HOST",
        "NEKOCONF_PORT8080",
        "NEKOCONF_VERSION2_ENABLED",
        "NEKOCONF_DB_CONNECTION_123",
        # Custom delimiter
        "CUSTOM__API__URL",
        "CUSTOM__DB__MAX__CONNECTIONS",
        # Type parsing
        "NEKOCONF_STRING_VAL",
        "NEKOCONF_INT_VAL",
        "NEKOCONF_FLOAT_VAL",
        "NEKOCONF_BOOL_TRUE",
        "NEKOCONF_BOOL_FALSE",
        "NEKOCONF_NULL_VAL",
        "NEKOCONF_EMPTY_VAL",
        "NEKOCONF_JSON_ARRAY",
        "NEKOCONF_JSON_OBJECT",
        # Invalid patterns
        "NEKOCONF__LEADING_DELIMITER",
        "NEKOCONF_TRAILING_DELIMITER_",
        "NEKOCONF_DOUBLE__DELIMITER",
        "NEKOCONF_",
        # Other tests
        "NEKOCONF_NEW_KEY",
        "NEKOCONF_API_KEY",
        "NEKOCONF_DB_HOST",
        "NEKOCONF_APP_FEATURES_AUTH_OAUTH_GOOGLE_CLIENT",
        "NEKOCONF_APP_FEATURES_AUTH_OAUTH_GITHUB_CLIENT",
        "NEKOCONF_NEW_CONFIG",
        "EDGE-API-URL",
        "NEKOCONF_EDGE_TEST",
        "TEST__CONFIG__VALUE",
        "NEKOCONF_CamelCase_Key",
        "NEKOCONF_SNAKE_CASE_KEY",
        "NEKOCONF_MixedCase_UPPER_lower",
        "NEKOCONF_OVERRIDE_KEY",
        "NEKOCONF_SPECIAL_CHARS",
        "NEKOCONF_UNICODE_VALUE",
        "NEKOCONF_MULTILINE",
        "NEKOCONF_QUOTES",
        "NEKOCONF_SPACES",
        "NEKOCONF_LOGGER_TEST",
        "NEKOCONF_COMPLEX_DATA",
        "NEKOCONF_API_VERSION",
        "NEKOCONF_API_VERSION_DETAIL",
    ]

    for var in test_vars:
        if var in os.environ:
            del os.environ[var]


if __name__ == "__main__":
    run_all_tests()
