"""Environment variable override utility for NekoConf.

This module provides functionality to override configuration values with
environment variables using various strategies and patterns.
"""

import copy
import logging
import os
from typing import Any, Dict, List, MutableMapping, Optional, Set, Tuple

from .helper import get_nested_value, getLogger, parse_value


class EnvOverrideHandler:
    """Handles environment variable overrides for configuration values."""

    def __init__(
        self,
        enabled: bool = True,
        prefix: str = "NEKOCONF",
        nested_delimiter: str = "_",
        include_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
        logger: Optional[logging.Logger] = None,
        preserve_case: bool = False,
        strict_parsing: bool = False,
    ):
        """Initialize the environment variable override handler.

        Args:
            enabled: Enable/disable environment variable overrides
            prefix: Prefix for environment variables. Set to "" for no prefix.
            nested_delimiter: Delimiter used in env var names for nested keys
            include_paths: List of dot-separated paths to include in overrides.
                           If None or empty, all keys are potentially included.
            exclude_paths: List of dot-separated paths to exclude from overrides.
                           Takes precedence over include_paths.
            logger: Optional logger for messages
            preserve_case: If True, maintains the original case of keys from environment variables
            strict_parsing: If True, raises exceptions when parsing fails rather than logging a warning
        """
        self.enabled = enabled
        self.prefix = prefix.rstrip("_") if prefix else ""
        self.nested_delimiter = nested_delimiter
        self.include_paths = include_paths or []  # Default to empty list
        self.exclude_paths = exclude_paths or []  # Default to empty list
        self.logger = logger or getLogger(__name__)
        self.preserve_case = preserve_case
        self.strict_parsing = strict_parsing

        if self.prefix == "":
            self.logger.warning(
                "Environment variable overrides are enabled without a prefix is not recommended. "
                "This may lead to conflicts with internal variables."
            )

        # Problematic characters in variable names
        self.problematic_chars = ["[", "]", "*", "?"]

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
        if not self.enabled:
            return config_data

        # Either create a copy or use the original (in-place)
        effective_data = config_data if in_place else copy.deepcopy(config_data)
        stats = {"applied_count": 0, "error_count": 0}

        # Get relevant environment variables once
        matching_env_vars = self._get_matching_env_vars()

        # Process existing keys in config and add new keys
        self._process_environment_overrides(effective_data, matching_env_vars, stats)

        if stats["applied_count"] > 0:
            self.logger.debug(
                f"Environment variable overrides applied: {stats['applied_count']}"
                + (f" (with {stats['error_count']} errors)" if stats["error_count"] > 0 else "")
            )

        return effective_data

    def _process_environment_overrides(
        self,
        effective_data: Dict[str, Any],
        env_vars: List[Tuple[str, str, str]],
        stats: MutableMapping[str, int],
    ) -> None:
        """Process all environment variable overrides.

        Args:
            effective_data: The configuration data to modify
            env_vars: List of (env_var_name, config_key, env_var_value) tuples
            stats: Mutable mapping to track statistics
        """
        processed_keys = set()

        # First process existing keys to prevent duplicated processing
        existing_keys = self._collect_all_keys(effective_data)

        for env_var_name, config_key, env_var_value in env_vars:
            # Check if this key exists in the configuration
            if config_key in existing_keys:
                # Override existing key
                if self._should_override(config_key):
                    self._try_parse_and_set_value(
                        effective_data, config_key, env_var_name, env_var_value, stats
                    )
                    processed_keys.add(config_key)
            elif config_key not in processed_keys:
                # Add new key if it should be overridden
                if self._should_override(config_key):
                    # Check if the key already exists in the data
                    sentinel = object()
                    if get_nested_value(effective_data, config_key, default=sentinel) is sentinel:
                        # Key doesn't exist yet, so add it
                        self._try_parse_and_set_value(
                            effective_data,
                            config_key,
                            env_var_name,
                            env_var_value,
                            stats,
                        )
                        processed_keys.add(config_key)

    def _collect_all_keys(self, data: Dict[str, Any], prefix: str = "") -> Set[str]:
        """Recursively collect all keys in the configuration.

        Args:
            data: The configuration data
            prefix: Current path prefix

        Returns:
            Set of all configuration keys
        """
        keys = set()

        if not isinstance(data, dict):
            return keys

        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            keys.add(full_key)

            if isinstance(value, dict):
                # Recursively collect keys from nested dictionaries
                nested_keys = self._collect_all_keys(value, full_key)
                keys.update(nested_keys)

        return keys

    def _get_matching_env_vars(self) -> List[Tuple[str, str, str]]:
        """Get environment variables that match our prefix and convert to config keys.

        Returns:
            List of (env_var_name, config_key, env_var_value) tuples
        """
        matching_vars = []
        prefix_len = len(f"{self.prefix}_") if self.prefix else 0

        for env_var_name, env_var_value in os.environ.items():
            # Basic checks
            if not env_var_name:
                continue

            # Check if variable matches our prefix
            if self.prefix:
                if not env_var_name.startswith(f"{self.prefix}_"):
                    continue
            else:
                # With no prefix, avoid internal vars and problematic ones
                if env_var_name.startswith("_"):
                    continue

                # Skip vars with problematic patterns that would cause errors
                if self._is_problematic_env_var(env_var_name):
                    self.logger.debug(f"Skipping problematic env var: {env_var_name}")
                    continue

            # Extract the key part
            key_part = env_var_name[prefix_len:] if self.prefix else env_var_name

            # Validate the key format
            if not self._validate_key_format(key_part, env_var_name):
                continue

            # Convert to config key
            config_key = self._env_key_to_config_key(key_part)

            matching_vars.append((env_var_name, config_key, env_var_value))

        return matching_vars

    def _is_problematic_env_var(self, env_var_name: str) -> bool:
        """Check if an environment variable name would cause parsing issues.

        Args:
            env_var_name: The environment variable name to check

        Returns:
            True if the environment variable would cause parsing issues
        """
        # If prefix is set, we handle problematic chars during conversion
        if self.prefix:
            return False

        # Check for numeric segments in dot-separated path
        parts = env_var_name.split(".")
        for part in parts:
            if part.isdigit() or (part and part[0].isdigit()):
                return True

        # Check for other problematic characters
        return any(c in env_var_name for c in self.problematic_chars)

    def _validate_key_format(self, key_part: str, env_var_name: str) -> bool:
        """Validate the format of the key part extracted from an environment variable.

        Args:
            key_part: The key part extracted from the environment variable
            env_var_name: Original environment variable name for logging

        Returns:
            True if the key format is valid
        """
        # Check for empty keys
        if not key_part:
            self.logger.warning(f"Skipping env var '{env_var_name}' due to empty key after prefix.")
            return False

        # Check for delimiter issues
        if self.nested_delimiter and (
            key_part.startswith(self.nested_delimiter)
            or key_part.endswith(self.nested_delimiter)
            or self.nested_delimiter + self.nested_delimiter in key_part
        ):
            self.logger.warning(
                f"Skipping env var '{env_var_name}' due to invalid delimiter format."
            )
            return False

        return True

    def _env_key_to_config_key(self, key_part: str) -> str:
        """Convert an environment variable key part to a configuration key.

        Args:
            key_part: The key part extracted from the environment variable

        Returns:
            The corresponding configuration key
        """
        # Replace delimiters with dots
        if self.preserve_case:
            config_key = key_part.replace(self.nested_delimiter, ".")
        else:
            config_key = key_part.replace(self.nested_delimiter, ".").lower()

        return config_key

    def _try_parse_and_set_value(
        self,
        data: Dict[str, Any],
        key_path: str,
        env_var_name: str,
        env_var_value_str: str,
        stats: MutableMapping[str, int],
    ) -> bool:
        """Try to parse an environment variable value and set it in the configuration.

        Args:
            data: The configuration data to modify
            key_path: The configuration key path
            env_var_name: The environment variable name (for logging)
            env_var_value_str: The environment variable string value
            stats: Statistics counters to update

        Returns:
            True if successful
        """
        try:
            # Parse the value string to appropriate type
            parsed_value = parse_value(env_var_value_str)

            # Use direct dictionary navigation to set value
            self._set_nested_value(data, key_path, parsed_value)
            stats["applied_count"] += 1

            self.logger.debug(
                f"Applied override: {env_var_name}='{env_var_value_str}' -> {key_path}"
            )
            return True

        except Exception as e:
            stats["error_count"] = stats.get("error_count", 0) + 1
            error_msg = f"Failed to set '{key_path}' from env var '{env_var_name}': {e}"

            if self.strict_parsing:
                raise ValueError(error_msg)
            else:
                self.logger.warning(error_msg)

            return False

    def _set_nested_value(self, data: Dict[str, Any], key_path: str, value: Any) -> None:
        """Safely set a value in a nested dictionary by navigating the dot-separated path.

        Args:
            data: The dictionary to modify
            key_path: Dot-separated path to the value location
            value: The value to set

        Raises:
            ValueError: If the path cannot be navigated
        """
        if not key_path:
            raise ValueError("Empty key path")

        parts = key_path.split(".")
        current = data

        # Navigate to the parent of the target key
        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                raise ValueError(
                    f"Cannot set value at '{key_path}' because '{'.'.join(parts[:i+1])}' is not a dictionary"
                )
            current = current[part]

        # Set the value at the final path segment
        current[parts[-1]] = value

    def _should_override(self, config_key: str) -> bool:
        """Check if a key should be considered for environment override based on include/exclude rules.

        Args:
            config_key: The configuration key to check

        Returns:
            True if the key should be overridden
        """
        # Check exclusions first (higher precedence)
        if self.exclude_paths:
            for exclude_pattern in self.exclude_paths:
                if config_key == exclude_pattern or config_key.startswith(f"{exclude_pattern}."):
                    return False

        # Check inclusions if specified
        if self.include_paths:
            for include_pattern in self.include_paths:
                if config_key == include_pattern or config_key.startswith(f"{include_pattern}."):
                    return True
            return False  # Not included in any pattern

        # Default to include if no specific rules apply
        return True
