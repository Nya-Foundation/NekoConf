"""Configuration manager module for NekoConf.

This module provides functionality to read, write, and manage configuration files
in YAML, JSON, and TOML formats.
"""

import logging
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import filelock

from .env import EnvOverrideHandler
from .event import EventType, NekoEventPipeline, on_change, on_event
from .lock import LockManager
from .utils import (
    create_file_if_not_exists,
    deep_merge,
    get_nested_value,
    getLogger,
    load_file,
    save_file,
    set_nested_value,
)


class NekoConfigManager:
    """Configuration manager for reading, writing, and event handling configuration files."""

    def __init__(
        self,
        config_path: Union[str, Path],
        schema_path: Optional[Union[str, Path]] = None,
        logger: Optional[logging.Logger] = None,
        # Lock settings
        lock_timeout: float = 1.0,
        # Environment variable override parameters
        env_override_enabled: bool = True,
        env_prefix: str = "NEKOCONF",
        env_nested_delimiter: str = "_",
        env_include_paths: Optional[List[str]] = None,
        env_exclude_paths: Optional[List[str]] = None,
        env_preserve_case: bool = False,
        env_strict_parsing: bool = False,
    ) -> None:
        """Initialize the configuration manager.

        Args:
            config_path: Path to the configuration file
            schema_path: Path to the schema file for validation (optional)
            logger: Optional logger instance for logging messages
            lock_timeout: Timeout in seconds for acquiring file locks
            env_override_enabled: Enable/disable environment variable overrides (default: True)
            env_prefix: Prefix for environment variables (default: "NEKOCONF"). Set to "" for no prefix.
            env_nested_delimiter: Delimiter used in env var names for nested keys (default: "_")
            env_include_paths: List of dot-separated paths to include in overrides.
                               If None or empty, all keys are potentially included (default: None).
            env_exclude_paths: List of dot-separated paths to exclude from overrides.
                               Takes precedence over include_paths (default: None).
            env_preserve_case: If True, preserves the original case of keys from environment variables.
            env_strict_parsing: If True, raises exceptions when parsing fails rather than logging warnings.
        """
        self.config_path = Path(config_path)
        self.schema_path = Path(schema_path) if schema_path else None
        self.logger = logger or getLogger(__name__)

        # Initialize lock manager
        self.lock_manager = LockManager(self.config_path, timeout=lock_timeout)

        # Initialize environment variable override handler
        self.env_handler = EnvOverrideHandler(
            enabled=env_override_enabled,
            prefix=env_prefix,
            nested_delimiter=env_nested_delimiter,
            include_paths=env_include_paths,
            exclude_paths=env_exclude_paths,
            logger=self.logger,
            preserve_case=env_preserve_case,
            strict_parsing=env_strict_parsing,
        )

        self.data: Dict[str, Any] = {}
        self.event_pipeline = NekoEventPipeline(logger=self.logger)

        self._load_validators()
        self._init_config()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()
        return False  # Don't suppress exceptions

    def cleanup(self):
        """Clean up resources used by the configuration manager."""
        # Clean up lock file
        self.lock_manager.cleanup()

    def _init_config(self) -> None:
        """Initialize the configuration by loading it from the file."""
        create_file_if_not_exists(self.config_path)
        self.load()

    def _load_validators(self) -> None:
        """Load schema validators if available."""
        self.validator = None
        if self.schema_path:
            try:
                from .eval import NekoSchemaValidator

                self.validator = NekoSchemaValidator(self.schema_path)
                self.logger.debug(f"Loaded schema validator from {self.schema_path}")
            except ImportError:
                self.logger.warning(
                    "Schema validation requested but schema_validator module not available. "
                    "Install with pip install nekoconf[schema]"
                )
            except Exception as e:
                self.logger.error(f"Failed to load schema validator: {e}")

    def load(self, apply_env_overrides: bool = True, in_place: bool = False) -> Dict[str, Any]:
        """Load configuration from file and apply environment variable overrides.

        Args:
            apply_env_overrides: Whether to apply environment variable overrides after loading
            in_place: Whether to modify data in-place (more memory efficient for large configs)

        Returns:
            The effective configuration data after overrides.
        """
        loaded_data: Dict[str, Any] = {}

        try:
            # Use lock manager to prevent race conditions during file read
            with self.lock_manager:
                if self.config_path.exists():
                    loaded_data = load_file(self.config_path) or {}
                    self.logger.debug(f"Loaded configuration from file: {self.config_path}")
                else:
                    self.logger.warning(f"Configuration file not found: {self.config_path}")
                    loaded_data = {}

        except filelock.Timeout:
            self.logger.error(
                f"Could not acquire lock to read config file {self.config_path} - another process may be using it"
            )
            # Return current data if lock fails
            return self.data
        except Exception as e:
            self.logger.error(
                f"Error loading configuration file {self.config_path}: {e}, {traceback.format_exc()}"
            )
            loaded_data = {}

        # Apply environment variable overrides to the loaded data
        old_data = self.data.copy()

        # Use the env_handler to apply overrides
        if apply_env_overrides:
            effective_data = self.env_handler.apply_overrides(loaded_data, in_place=in_place)
        else:
            effective_data = loaded_data if in_place else loaded_data.copy()

        self.data = effective_data

        # Emit reload event with old and new values
        self.event_pipeline.emit(
            EventType.RELOAD,
            config_data=self.data,
            old_value=old_data,
            new_value=self.data,
        )

        # If the loaded data is empty or unchanged, return it as is
        if not old_data or old_data == self.data:
            return self.data

        # Emit update event if there was a effective change on reload
        self.event_pipeline.emit(
            EventType.UPDATE,
            config_data=self.data,
            old_value=old_data,
            new_value=self.data,
        )

        return self.data

    def save(self) -> bool:
        """Save configuration to file.

        Note: This saves the *current effective configuration* which might include
        values that were originally overridden by environment variables but later
        modified via set/update.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Use lock manager to prevent race conditions
            with self.lock_manager:
                save_file(self.config_path, self.data)
                self.logger.debug(f"Saved configuration to {self.config_path}")

            # Emit generic change event
            self.event_pipeline.emit(
                EventType.CHANGE,
                config_data=self.data,
            )

            return True
        except filelock.Timeout:
            self.logger.error(
                "Could not acquire lock to write config file - another process may be using it"
            )
            return False
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
            return False

    def get_all(self) -> Dict[str, Any]:
        """Get all *effective* configuration data (including overrides).

        Returns:
            The entire effective configuration data as a dictionary
        """
        return self.data

    def get(self, key: Optional[str] = None, default: Any = None) -> Any:
        """Get an *effective* configuration value (including overrides).

        Args:
            key: The configuration key (JMESPath expressions for nested values)
            default: Default value to return if key is not found

        Returns:
            The configuration value or default if not found
        """
        if key is None:
            return self.data

        # Use the utility which handles nested keys
        return get_nested_value(self.data, key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value in the *effective* configuration.

        This change will be persisted on the next `save()`.

        Args:
            key: The configuration key (JMESPath expressions for nested values)
            value: The value to set
        """
        old_value = self.get(key)  # Get current effective value
        is_updated = set_nested_value(self.data, key, value)  # Update effective data

        # Determine if the key existed before
        event_type = EventType.UPDATE if old_value is not None else EventType.CREATE

        # If the value was not updated (e.g., same value), we don't emit an event
        if not is_updated:
            return

        self.event_pipeline.emit(
            event_type, path=key, old_value=old_value, new_value=value, config_data=self.data
        )
        # Also emit generic change event for this path
        self.event_pipeline.emit(
            EventType.CHANGE, path=key, old_value=old_value, new_value=value, config_data=self.data
        )

    def delete(self, key: str) -> bool:
        """Delete a configuration value from the *effective* configuration.

        This change will be persisted on the next `save()`.

        Args:
            key: The configuration key (JMESPath expressions for nested values)

        Returns:
            True if the key was deleted, False if it didn't exist
        """
        parts = key.split(".")
        data_ptr = self.data  # Operate on effective data
        old_value = self.get(key)  # Get current effective value

        # Check if key exists before attempting delete
        _sentinel = object()
        if get_nested_value(self.data, key, default=_sentinel) is _sentinel:
            return False  # Key doesn't exist in effective config

        # Navigate to the parent of the target key
        for i, part in enumerate(parts[:-1]):
            # This check should ideally not fail if the key exists, but added for safety
            if not isinstance(data_ptr, dict) or part not in data_ptr:
                self.logger.error(
                    f"Inconsistency found while navigating to delete key '{key}' at part '{part}'. Aborting delete."
                )
                return False
            data_ptr = data_ptr[part]

        # Check if parent is a dict and the final key exists
        if not isinstance(data_ptr, dict) or parts[-1] not in data_ptr:
            # This should also not happen if the initial check passed
            self.logger.error(
                f"Inconsistency found: key '{key}' existed but parent path is not a dict or final key missing."
            )
            return False

        # Delete the key
        del data_ptr[parts[-1]]

        # Emit delete event
        self.event_pipeline.emit(
            EventType.DELETE, path=key, old_value=old_value, config_data=self.data
        )

        # Also emit generic change event for this path
        self.event_pipeline.emit(
            EventType.CHANGE,
            path=key,
            old_value=old_value,
            new_value=None,
            config_data=self.data,
        )

        return True

    def update(
        self, data: Dict[str, Any], deep_merge_enabled: bool = True, in_place: bool = False
    ) -> None:
        """Update multiple configuration values in the *effective* configuration.

        This change will be persisted on the next `save()`.

        Args:
            data: Dictionary of configuration values to update
            deep_merge_enabled: Whether to perform deep merge for nested dictionaries
            in_place: Whether to modify the data in-place (more memory efficient)
        """
        old_data = None
        if not in_place:
            old_data = self.data.copy()  # Copy current effective data if needed for events

        if deep_merge_enabled:
            # Deep merge the incoming data into the current effective data
            self.data = deep_merge(source=data, destination=self.data)
        else:
            # Simple update (overwrites top-level keys)
            self.data.update(data)

        # Emit generic change event if data actually changed
        if not in_place and old_data != self.data:
            self.event_pipeline.emit(
                EventType.CHANGE,
                old_value=old_data,
                new_value=self.data,
                config_data=self.data,
            )

    def on_change(self, path_pattern: str, priority: int = 100):
        """Register a handler for changes to a specific configuration path.

        Args:
            path_pattern: Path pattern to filter events (e.g., "database.connection")
            priority: Handler priority (lower number = higher priority)

        Returns:
            Decorator function

        Example:
            @config.on_change("database.connection")
            def handle_db_connection_change(old_value, new_value, **kwargs):
                # Reconnect to database with new settings
                pass
        """
        return on_change(self.event_pipeline, path_pattern, priority)

    def on_event(self, event_type, path_pattern=None, priority=100):
        """Register a handler for specific event types.

        Args:
            event_type: Type of event to handle (or list of types)
            path_pattern: Optional path pattern to filter events
            priority: Handler priority (lower number = higher priority)

        Returns:
            Decorator function

        Example:
            @config.on_event(EventType.DELETE, "cache.*")
            def handle_cache_delete(path, old_value, **kwargs):
                # Clear cache entries when deleted
                pass
        """
        return on_event(self.event_pipeline, event_type, path_pattern, priority)

    def validate(self) -> List[str]:
        """Validate the *effective* configuration against schema.

        Returns:
            List of validation error messages (empty if valid)
        """
        if not self.validator:
            self.logger.warning("No schema validator available, skipping validation")
            return []

        errors = self.validator.validate(self.data)  # Validate effective data

        # Emit validation event
        self.event_pipeline.emit(
            EventType.VALIDATE,
            config_data=self.data,
            new_value=not bool(errors),  # True if validation passed
            old_value=errors,  # Pass errors as old_value
        )

        return errors
