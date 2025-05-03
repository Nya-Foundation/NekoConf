"""Environment variable override utility for NekoConf.

This module provides functionality to override configuration values with
environment variables using various strategies and patterns.
"""

import copy
import logging
import os
from typing import Any, Dict, List, MutableMapping, Optional, Tuple

from .utils import get_nested_value, getLogger, parse_value, set_nested_value


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
        stats = {"applied_count": 0, "error_count": 0}  # Use a dict as a mutable counter reference

        # Process existing keys in config
        self._override_existing_keys(effective_data, stats)

        # Process new keys from environment
        self._add_new_keys_from_env(effective_data, stats)

        if stats["applied_count"] > 0:
            self.logger.debug(
                f"Environment variable overrides applied: {stats['applied_count']}"
                + (f" (with {stats['error_count']} errors)" if stats["error_count"] > 0 else "")
            )

        return effective_data

    def _override_existing_keys(
        self, effective_data: Dict[str, Any], stats: MutableMapping[str, int]
    ) -> None:
        """Apply overrides to keys that exist in the original configuration.

        Args:
            effective_data: The configuration data to modify
            stats: Mutable mapping to track statistics (like applied overrides count)
        """
        # Stack to process nested dictionaries [(dict_level, path_prefix)]
        keys_to_process_stack = [(effective_data, "")]

        while keys_to_process_stack:
            current_dict, path_prefix = keys_to_process_stack.pop()

            if not isinstance(current_dict, dict):  # Skip non-dict items
                continue

            for key, value in current_dict.items():
                full_key_path = f"{path_prefix}.{key}" if path_prefix else key

                # Check if this key should be considered for override
                if not self._should_override(full_key_path):
                    # Still traverse children if it's a dict
                    if isinstance(value, dict):
                        keys_to_process_stack.append((value, full_key_path))
                    continue  # Skip env check for this key

                # Generate the corresponding environment variable name
                env_var_name = self._generate_env_var_name(full_key_path)
                env_var_value_str = os.environ.get(env_var_name)

                if env_var_value_str is not None:
                    success = self._try_parse_and_set_value(
                        effective_data, full_key_path, env_var_name, env_var_value_str, stats
                    )

                    if success:
                        self.logger.debug(
                            f"Applied override: {env_var_name}='{env_var_value_str}' -> {full_key_path}"
                        )

                # If it's a dictionary, add it to the stack to process its children
                if isinstance(value, dict):
                    keys_to_process_stack.append((value, full_key_path))

    def _add_new_keys_from_env(
        self, effective_data: Dict[str, Any], stats: MutableMapping[str, int]
    ) -> None:
        """Add new keys from environment variables that don't exist in the original configuration.

        Args:
            effective_data: The configuration data to modify
            stats: Mutable mapping to track statistics (like applied overrides count)
        """
        prefix_to_match = f"{self.prefix}_" if self.prefix else ""
        min_prefix_len = len(prefix_to_match)

        # Get only environment variables that match our prefix
        env_vars = self._get_matching_env_vars(prefix_to_match)

        for env_var_name, env_var_value_str in env_vars:
            # Derive potential config key from env var name
            # The prefix check is already done by _get_matching_env_vars
            key_part = env_var_name[min_prefix_len:] if self.prefix else env_var_name

            # Basic validation on key format
            if not self._validate_key_format(key_part, env_var_name):
                continue

            # Convert the environment variable name to a config key path
            config_key = self._env_key_to_config_key(key_part)

            # Check if this key already exists in the effective data
            _sentinel = object()
            if get_nested_value(effective_data, config_key, default=_sentinel) is not _sentinel:
                continue  # Already processed this key in the first pass

            # Check include/exclude rules for this new key
            if not self._should_override(config_key):
                continue

            # Try to parse and set the new value
            success = self._try_parse_and_set_value(
                effective_data, config_key, env_var_name, env_var_value_str, stats
            )

            if success:
                self.logger.debug(
                    f"Added NEW key from env: {env_var_name}='{env_var_value_str}' -> {config_key}"
                )

    def _get_matching_env_vars(self, prefix_to_match: str) -> List[Tuple[str, str]]:
        """Get environment variables that match our prefix.

        Args:
            prefix_to_match: The prefix to match against environment variable names.
                             If self.prefix is empty, this will be empty, and we match all non-internal vars.

        Returns:
            List of (env_var_name, env_var_value) tuples that match the prefix
        """
        matching_vars = []

        for env_var_name, env_var_value in os.environ.items():
            # Basic checks
            if not env_var_name:
                continue

            if self.prefix:
                # If prefix is set, only match variables starting with it
                if not env_var_name.startswith(prefix_to_match):
                    continue
            else:
                # If no prefix, avoid internal vars (e.g., starting with '_')
                # and potentially other system-specific vars if needed.
                # For now, just skip empty or underscore-prefixed ones.
                if env_var_name.startswith("_"):
                    continue

            matching_vars.append((env_var_name, env_var_value))

        return matching_vars

    def _validate_key_format(self, key_part: str, env_var_name: str) -> bool:
        """Validate the format of the key part extracted from an environment variable.

        Args:
            key_part: The key part extracted from the environment variable
            env_var_name: Original environment variable name for logging

        Returns:
            True if the key format is valid, False otherwise
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
            True if successful, False otherwise
        """
        try:
            parsed_value = parse_value(env_var_value_str)
            set_nested_value(data, key_path, parsed_value)
            stats["applied_count"] += 1  # Increment the counter by reference
            return True
        except Exception as e:
            stats["error_count"] = stats.get("error_count", 0) + 1
            error_msg = f"Failed to parse or apply environment variable '{env_var_name}' for key '{key_path}': {e}"

            if self.strict_parsing:
                raise ValueError(error_msg)
            else:
                self.logger.warning(error_msg)

            return False

    def _generate_env_var_name(self, config_key: str) -> str:
        """Generates the environment variable name for a given config key.

        Args:
            config_key: The configuration key in dot notation

        Returns:
            The corresponding environment variable name
        """
        # Replace dots with the specified delimiter
        env_key_part = config_key.replace(".", self.nested_delimiter)

        if not self.prefix:
            # No prefix, just format the key
            env_key = env_key_part
        else:
            # Add prefix and format the key
            env_key = f"{self.prefix}_{env_key_part}"
        return env_key.upper()

    def _should_override(self, config_key: str) -> bool:
        """Checks if a key should be considered for environment override based on include/exclude rules.

        Args:
            config_key: The configuration key to check

        Returns:
            True if the key should be overridden, False otherwise
        """
        # 1. Check Exclusions first (higher precedence)
        if self.exclude_paths:
            for exclude_pattern in self.exclude_paths:
                # Simple exact match or prefix match (dot-separated)
                if config_key == exclude_pattern or config_key.startswith(exclude_pattern + "."):
                    return False

        # 2. Check Inclusions if specified
        if self.include_paths:
            included = False
            for include_pattern in self.include_paths:
                # Simple exact match or prefix match (dot-separated)
                if config_key == include_pattern or config_key.startswith(include_pattern + "."):
                    included = True
                    break  # Found an include match, no need to check further
            if not included:
                return False  # Not included by any pattern, so exclude it

        # 3. If no specific rules apply (or includes are empty), default to include
        return True
