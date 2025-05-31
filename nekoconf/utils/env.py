"""Environment variable override utility for NekoConf.

This module provides functionality to override configuration values with
environment variables using various strategies and patterns.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .helper import get_nested_value, getLogger, parse_value, set_nested_value


class EnvOverrideHandler:
    """Handles environment variable overrides for configuration values.

    Simple, modular implementation following the Zen of Python principles.
    """

    def __init__(
        self,
        prefix: str = "NEKOCONF",
        nested_delimiter: str = "_",
        include_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
        logger: Optional[logging.Logger] = None,
        preserve_case: bool = False,
        strict_parsing: bool = False,
        create_missing_keys: bool = True,
    ):
        """Initialize the environment variable override handler.

        Args:
            prefix: Prefix for environment variables. Set to "" for no prefix.
            nested_delimiter: Delimiter used in env var names for nested keys
            include_paths: List of dot-separated paths to include in overrides.
                           If None or empty, all keys are potentially included.
            exclude_paths: List of dot-separated paths to exclude from overrides.
                           Takes precedence over include_paths.
            logger: Optional logger for messages
            preserve_case: If True, maintains the original case of keys from environment variables
            strict_parsing: If True, raises exceptions when parsing fails rather than logging a warning
            create_missing_keys: If True, allows creation of new config keys. If False, only updates existing keys.
        """
        self.prefix = prefix.rstrip("_") if prefix else ""
        self.nested_delimiter = nested_delimiter
        self.include_paths = include_paths or []
        self.exclude_paths = exclude_paths or []
        self.logger = logger or getLogger(__name__)
        self.preserve_case = preserve_case
        self.strict_parsing = strict_parsing
        self.create_missing_keys = create_missing_keys

        # Cache the prefix pattern for better performance
        self.prefix_pattern = f"{self.prefix}{self.nested_delimiter}" if self.prefix else ""

        # System environment variables to skip when no prefix is used
        self.system_vars = ("_", "PATH", "HOME", "USER", "SHELL", "TERM")

        # Warn if no prefix is used
        if not self.prefix:
            self.logger.warning(
                "Environment variable overrides without a prefix is not recommended. "
                "This may lead to conflicts with system variables."
            )

    def apply_overrides(
        self, config_data: Dict[str, Any], in_place: bool = False
    ) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration data.

        Args:
            config_data: The original configuration data to override
            in_place: Whether to modify config_data in place (more memory efficient)

        Returns:
            The configuration data with environment variable overrides applied
        """
        # Use the original or create a new dictionary
        effective_data = config_data if in_place else config_data.copy()

        # Find and apply matching environment variables
        applied, errors = self._apply_matching_env_vars(effective_data)

        # Log application statistics
        if applied:
            error_msg = f" with {errors} errors" if errors else ""
            self.logger.debug(f"Applied {applied} environment overrides{error_msg}")

        return effective_data

    def _apply_matching_env_vars(self, data: Dict[str, Any]) -> Tuple[int, int]:
        """Find matching environment variables and apply them to the config.

        Args:
            data: The configuration data to modify

        Returns:
            Tuple of (applied_count, error_count)
        """
        applied, errors = 0, 0

        for env_name, value in os.environ.items():
            # Skip variables that don't match our criteria
            if not self._is_matching_env_var(env_name):
                continue

            # Extract and convert the key part
            try:
                config_key = self._env_var_to_config_key(env_name)

                # Check if this key should be overridden based on include/exclude rules
                if not self._should_override(config_key):
                    continue

                # Check if we should create new keys or only update existing ones
                if not self.create_missing_keys and not self._key_exists(data, config_key):
                    self.logger.debug(
                        f"Skipping new key '{config_key}' (create_missing_keys=False)"
                    )
                    continue

                # Apply the override
                if self._set_config_value(data, config_key, env_name, value):
                    applied += 1
                else:
                    errors += 1

            except ValueError as e:
                self.logger.debug(f"Skipping env var '{env_name}': {e}")

        return applied, errors

    def _is_matching_env_var(self, env_name: str) -> bool:
        """Check if an environment variable name contains our prefix or is a valid system variable.

        Args:
            env_name: The environment variable name

        Returns:
            True if the variable should be processed
        """
        # Check prefix if one is specified
        if self.prefix:
            return env_name.startswith(self.prefix_pattern)

        # When no prefix is used, skip common system variables
        return not env_name.startswith(self.system_vars)

    def _env_var_to_config_key(self, env_name: str) -> str:
        """Convert an environment variable name to a configuration key path.

        Args:
            env_name: The environment variable name

        Returns:
            The corresponding configuration key path

        Raises:
            ValueError: If the key format is invalid
        """
        # Extract the key part (without prefix)
        if self.prefix:
            key_part = env_name[len(self.prefix_pattern) :]
        else:
            key_part = env_name

        # Validate key format
        if not key_part:
            raise ValueError("Empty key after prefix")

        # Check for invalid delimiter patterns
        if self.nested_delimiter and (
            key_part.startswith(self.nested_delimiter)
            or key_part.endswith(self.nested_delimiter)
            or self.nested_delimiter + self.nested_delimiter in key_part
        ):
            raise ValueError("Invalid delimiter format")

        # Convert to configuration key format (replace delimiters with dots)
        config_key = key_part.replace(self.nested_delimiter, ".")

        # Apply case transformation if needed
        if not self.preserve_case:
            config_key = config_key.lower()

        return config_key

    def _key_exists(self, data: Dict[str, Any], key: str) -> bool:
        """Check if a configuration key already exists in the data.

        Args:
            data: The configuration data to check
            key: The configuration key path to check

        Returns:
            True if the key exists, False otherwise
        """
        # Use a sentinel object to detect if key doesn't exist
        sentinel = object()
        return get_nested_value(data, key, default=sentinel) is not sentinel

    def _should_override(self, config_key: str) -> bool:
        """Check if a key should be overridden based on include/exclude rules.

        Args:
            config_key: The configuration key to check

        Returns:
            True if the key should be overridden
        """
        # Check exclusions first (higher precedence)
        if any(
            config_key == pattern or config_key.startswith(f"{pattern}.")
            for pattern in self.exclude_paths
        ):
            return False

        # If includes specified, check if key matches any include pattern
        if self.include_paths:
            return any(
                config_key == pattern or config_key.startswith(f"{pattern}.")
                for pattern in self.include_paths
            )

        # By default, include everything if no specific includes are defined
        return True

    def _set_config_value(self, data: Dict[str, Any], key: str, env_name: str, value: str) -> bool:
        """Set a configuration value from an environment variable.

        Args:
            data: The configuration data to modify
            key: The configuration key path
            env_name: The environment variable name (for logging)
            value: The environment variable value

        Returns:
            True if successful, False if error occurred
        """
        try:
            # Parse the value string to appropriate type
            parsed_value = parse_value(value)

            # Set the value in the configuration
            set_nested_value(data, key, parsed_value)

            # Log the override
            self.logger.debug(f"Applied override: {env_name}='{value}' -> {key}")
            return True

        except Exception as e:
            error_msg = f"Failed to set '{key}' from env var '{env_name}': {e}"

            if self.strict_parsing:
                raise ValueError(error_msg)
            else:
                self.logger.warning(error_msg)

            return False
