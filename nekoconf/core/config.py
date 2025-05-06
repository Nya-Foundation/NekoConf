"""Configuration manager module for NekoConf.

This module provides functionality to read, write, and manage configuration files
in YAML, JSON, and TOML formats.
"""

import copy
import logging
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import filelock

from ..event.changes import ChangeTracker, ChangeType, ConfigChange, emit_change_events
from ..event.pipeline import EventType, NekoEventPipeline, on_change, on_event

# Check for optional dependencies
from ..remote import HAS_REMOTE_DEPS, RemoteConfigClient
from ..schema import HAS_SCHEMA_DEPS, NekoSchemaValidator
from ..utils.env import EnvOverrideHandler
from ..utils.helper import (
    create_file_if_not_exists,
    deep_merge,
    get_nested_value,
    getLogger,
    load_file,
    save_file,
    set_nested_value,
)
from ..utils.lock import LockManager

if TYPE_CHECKING:
    from ..core.wrapper import NekoConfigManager


class NekoConfigManager:
    """Configuration manager for reading, writing, and event handling configuration files."""

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
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
        # Remote configuration parameters
        remote_url: Optional[str] = None,
        remote_api_key: Optional[str] = None,
        remote_read_only: bool = True,
        remote_reconnect_attempts: int = 5,
        remote_reconnect_delay: float = 1.0,
        # In-memory mode (no file)
        in_memory: bool = False,
        # Event handling parameters
        event_emission_enabled: bool = False,
    ) -> None:
        """Initialize the configuration manager.

        Args:
            config_path: Path to the configuration file (optional if using remote_url and in_memory mode)
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
            remote_url: URL of a remote NekoConf server to sync with (optional)
            remote_api_key: API key for authentication with the remote server (optional)
            remote_read_only: If True, only read from remote server, no writes allowed (default: True)
            remote_reconnect_attempts: Number of reconnection attempts on failure (default: 5)
            remote_reconnect_delay: Delay between reconnection attempts with exponential backoff (default: 1.0)
            in_memory: If True, configuration is kept only in memory, not saved to file (default: False)
            event_emission_enabled: If True, emits events for configuration changes (default: False)

        """
        self.logger = logger or getLogger(__name__)
        self.data: Dict[str, Any] = {}
        self.event_pipeline = NekoEventPipeline(logger=self.logger)
        self.in_memory = in_memory

        # Determine operating mode
        self.remote_sync: "RemoteConfigClient" = None
        self.config_path = None
        self.lock_manager = None
        self.event_disabled = not event_emission_enabled

        # Initialize configuration source based on provided parameters
        if remote_url:
            # Remote configuration mode
            if not HAS_REMOTE_DEPS:
                self.logger.error(
                    "Remote configuration requested but dependencies are not available. "
                    "Install with: pip install nekoconf[remote]"
                )
                if config_path:  # Fall back to local file if possible
                    self.logger.warning("Falling back to local configuration only")
                    self.config_path = Path(config_path)
                    self.lock_manager = LockManager(self.config_path, timeout=lock_timeout)
                else:
                    raise ImportError(
                        "Cannot initialize: remote dependencies missing and no config_path provided. "
                        "Install with: pip install nekoconf[remote]"
                    )
            else:
                try:
                    self.remote_sync = RemoteConfigClient(
                        remote_url=remote_url,
                        api_key=remote_api_key,
                        read_only=remote_read_only,
                        on_update=self._handle_remote_update,
                        logger=self.logger,
                        reconnect_attempts=remote_reconnect_attempts,
                        reconnect_delay=remote_reconnect_delay,
                    )
                    self.logger.info(f"Configured to use remote configuration from {remote_url}")

                    # Still set up local file if not in-memory mode
                    if not in_memory and config_path:
                        self.config_path = Path(config_path)
                        self.lock_manager = LockManager(self.config_path, timeout=lock_timeout)
                        self.logger.info(
                            f"Local configuration will be stored at {self.config_path}"
                        )
                    else:
                        self.logger.info("Using in-memory configuration with remote sync")
                except Exception as e:
                    self.logger.error(f"Failed to initialize remote sync: {e}")
                    if config_path:  # Fall back to local file if possible
                        self.logger.warning("Falling back to local configuration only")
                        self.config_path = Path(config_path)
                        self.lock_manager = LockManager(self.config_path, timeout=lock_timeout)
                    else:
                        raise ValueError(
                            f"Cannot initialize: remote sync failed and no config_path provided: {e}"
                        )
        elif config_path:
            # Local file mode
            self.config_path = Path(config_path)
            self.lock_manager = LockManager(self.config_path, timeout=lock_timeout)
            self.logger.info(f"Using local configuration from {self.config_path}")
        else:
            # In-memory only mode
            if not in_memory:
                raise ValueError("Must provide either config_path or set in_memory=True")
            self.logger.info("Using in-memory configuration only (no persistence)")

        self.schema_path = Path(schema_path) if schema_path else None

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
        # Stop remote sync if active
        if self.remote_sync:
            self.logger.debug("Stopping remote configuration sync")
            self.remote_sync.stop()

        # Clean up lock file if using local file
        if self.lock_manager:
            self.lock_manager.cleanup()

    def _init_config(self) -> None:
        """Initialize the configuration by loading it."""
        # Create local file if needed
        if self.config_path and not self.in_memory:
            create_file_if_not_exists(self.config_path)

        # If using remote config, start sync
        if self.remote_sync:
            if self.remote_sync.start():
                # Initial load from remote was successful
                self.data = self.remote_sync.get_config()
                self.event_pipeline.emit(
                    EventType.RELOAD,
                    config_data=self.data,
                    old_value={},
                    new_value=self.data,
                    ignore=self.event_disabled,
                )
            elif self.config_path:
                # Remote failed but we have a local file, fall back to it
                self.logger.warning("Remote sync failed, falling back to local configuration")
                self.load()
            else:
                # Remote failed and no local file
                self.logger.error("Remote sync failed and no local fallback available")
                self.data = {}
        else:
            # Standard local file load
            self.load()

    def _handle_remote_update(self, config_data: Dict[str, Any]) -> None:
        """Handle configuration updates from remote server.

        Args:
            config_data: Updated configuration from remote
        """
        old_data = self.data.copy()
        self.data = config_data

        self.logger.debug("Received remote configuration update")

        # Emit change event if data changed
        if old_data != self.data:
            self.event_pipeline.emit(
                EventType.CHANGE,
                old_value=old_data,
                new_value=self.data,
                config_data=self.data,
                ignore=self.event_disabled,
            )

        # Save to local file if configured
        if self.config_path and not self.in_memory:
            self.logger.debug("Saving remote configuration update to local file")
            try:
                with self.lock_manager:
                    save_file(self.config_path, self.data)
            except Exception as e:
                self.logger.error(f"Failed to save remote update to local file: {e}")

    def _load_validators(self) -> None:
        """Load schema validators if available."""
        self.validator = None

        if self.schema_path:
            if not HAS_SCHEMA_DEPS:
                self.logger.warning(
                    "Schema validation requested but dependencies are not available. "
                    "Install with: pip install nekoconf[schema]"
                )
                return

            try:
                self.validator = NekoSchemaValidator(self.schema_path)
                self.logger.debug(f"Loaded schema validator from {self.schema_path}")
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

        # If we're in remote mode, use that as source of truth
        if self.remote_sync:
            loaded_data = self.remote_sync.get_config()
            self.logger.debug("Reloaded configuration from remote server")
        # Otherwise if we have a local file and not in memory-only mode
        elif self.config_path and not self.in_memory:
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
        else:
            # In-memory only, just use current data
            self.logger.debug("Using current in-memory configuration")
            return self.data

        # Apply environment variable overrides to the loaded data
        old_data = copy.deepcopy(self.data)

        # Use the env_handler to apply overrides
        if apply_env_overrides:
            effective_data = self.env_handler.apply_overrides(loaded_data, in_place=in_place)
        else:
            effective_data = loaded_data if in_place else loaded_data.copy()

        self.data = effective_data

        # Emit reload event with old and new values
        self.event_pipeline.emit(
            EventType.RELOAD,
            old_value=old_data,
            new_value=self.data,
            config_data=self.data,
            ignore=self.event_disabled,
        )

        # If the loaded data is empty or unchanged, return it as is
        if not old_data or old_data == self.data:
            return self.data

        # Emit update event if there was a effective change on reload
        self.event_pipeline.emit(
            EventType.UPDATE,
            old_value=old_data,
            new_value=self.data,
            config_data=self.data,
            ignore=self.event_disabled,
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
        # If using remote and it's not read-only, push changes to remote
        if self.remote_sync and not self.remote_sync.read_only:
            success = self.remote_sync.update_config(self.data)
            if not success:
                self.logger.error("Failed to update remote configuration")
                return False

        # If we're in memory-only mode with no local file, we're done
        if self.in_memory and not self.config_path:
            return True

        # Otherwise save to local file if we have one
        if self.config_path:
            try:
                # Use lock manager to prevent race conditions
                with self.lock_manager:
                    save_file(self.config_path, self.data)
                    self.logger.debug(f"Saved configuration to {self.config_path}")
                return True

            except filelock.Timeout:
                self.logger.error(
                    "Could not acquire lock to write config file - another process may be using it"
                )
                return False
            except Exception as e:
                self.logger.error(f"Error saving configuration: {e}")
                return False

        return True

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
        # Make a copy of current state
        old_data = copy.deepcopy(self.data)

        # Apply the change
        is_updated = set_nested_value(self.data, key, value)

        # If the value was not updated (same value), we don't emit an event
        if not is_updated:
            return

        # if event emission is disabled, skip emitting events
        if self.event_disabled:
            return

        changes = []

        # Detect what kind of change occurred and emit events
        changes.append(ChangeTracker.detect_single_change(old_data, self.data, key))

        # Append a global change event
        changes.append(ConfigChange(ChangeType.CHANGE, "*", old_data, self.data))

        # Emit events for the change using our centralized function
        emit_change_events(self, changes)

    def delete(self, key: str) -> bool:
        """Delete a configuration value from the *effective* configuration.

        This change will be persisted on the next `save()`.

        Args:
            key: The configuration key (JMESPath expressions for nested values)

        Returns:
            True if the key was deleted, False if it didn't exist
        """

        # Check if key exists before attempting delete
        _sentinel = object()
        old_value = get_nested_value(self.data, key, default=_sentinel)
        if old_value is _sentinel:
            return False  # Key doesn't exist in effective config

        # Make a copy of current state
        old_data = copy.deepcopy(self.data)

        # Navigate to the parent of the target key
        parts = key.split(".")
        data_ptr = self.data  # Operate on effective data

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

        # if event emission is disabled, skip emitting events
        if self.event_disabled:
            return True

        changes = []
        # Create the change object manually since we know it's a deletion
        changes.append(ConfigChange(ChangeType.DELETE, key, old_value=old_value, new_value=None))

        # Append a global change event
        changes.append(
            ConfigChange(
                ChangeType.CHANGE,
                old_value=old_data,
                new_value=self.data,
            )
        )
        # Emit events for the deletion using our centralized function
        emit_change_events(self, changes)

        return True

    def replace(self, data: Dict[str, Any]) -> bool:
        """Replace the entire *effective* configuration with new data.

        This change will be persisted on the next `save()`.

        Args:
            data: New configuration data to replace the current effective configuration
        Returns:
            True if the configuration was replaced, False if no changes were made

        """
        if data == self.data:
            return False

        old_data = copy.deepcopy(self.data)

        # Apply the new data
        self.data = data

        # if event emission is disabled, skip emitting events
        if self.event_disabled:
            return

        # Detect changes between configurations
        changes = ChangeTracker.detect_changes(old_data, data)
        emit_change_events(self, changes)

        return True

    def update(self, data: Dict[str, Any]) -> None:
        """Update multiple configuration values in the *effective* configuration.

        This change will be persisted on the next `save()`.

        Args:
            data: Dictionary of configuration values to update
        """
        # Make deep copies to prevent mutations
        old_data = copy.deepcopy(self.data)

        # Create an updated version by deep merging
        deep_merge(source=data, destination=self.data, in_place=True)

        # if event emission is disabled, skip emitting events
        if self.event_disabled:
            return

        # Detect changes between configurations
        changes = ChangeTracker.detect_changes(old_data, self.data)
        emit_change_events(self, changes)

    def on_change(self, path_pattern: str, priority: int = 100):
        """Register a handler for changes to a specific configuration path.

        Args:
            path_pattern: Path pattern to filter events (e.g., "database.connection")
            priority: Handler priority (lower number = higher priority)

        Returns:
            Decorator function

        Example:
            @config.on_change("database.connection")
            def handle_db_connection_change(event_type, path, old_value, new_value, config_data, **kwargs):
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

    def reload(self) -> Dict[str, Any]:
        """Reload configuration from source (file or remote).

        For remote configuration, this will trigger a refresh from the server.
        For local files, this will reload from disk.

        Returns:
            The updated configuration
        """
        updated_data = {}

        # If using remote sync, trigger a reload
        if self.remote_sync:
            if self.remote_sync.read_only:
                # If we're in read-only mode, just re-fetch
                updated_data = self.load()
            else:
                # Otherwise trigger reload on the server
                if self.remote_sync.reload_remote_config():
                    updated_data = self.remote_sync.get_config()
                else:
                    self.logger.error("Failed to trigger reload from remote server")
                    updated_data = self.data
        else:
            # Standard local reload
            updated_data = self.load()

        self.event_pipeline.emit(
            EventType.RELOAD,
            old_value=self.data,
            new_value=updated_data,
            config_data=updated_data,
            ignore=self.event_disabled,
        )

        self.data = updated_data

        return updated_data

    def validate_schema(self, data: Optional[Dict[str, Any]] = None) -> bool:
        """Validate the configuration against the schema.
        Args:
            data: Optional data to validate (if None, uses the effective configuration)
        Returns:
            True if valid, False otherwise
        """

        if not self.validator:
            self.logger.warning("No schema validator available, skipping validation")
            return []

        return self.validator.validate(data)  # Validate effective data

    def validate(self) -> List[str]:
        """Validate the *effective* configuration against schema.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = self.validate_schema(self.data)

        self.event_pipeline.emit(
            EventType.VALIDATE,
            new_value=not bool(errors),
            old_value=errors,
            config_data=self.data,
            ignore=self.event_disabled,
        )

        return errors

    def transaction(self):
        """Start a new configuration transaction.

        This allows multiple configuration changes to be applied and
        emitted as a single logical operation.

        Returns:
            A transaction manager to use as a context manager

        Example:
            with config.transaction() as txn:
                txn.set("database.host", "localhost")
                txn.set("database.port", 5432)
                txn.set("database.username", "admin")
                # Changes are applied and events emitted only when the context exits
        """
        from ..event.transaction import TransactionManager

        class TransactionContext:
            def __init__(self, config: "NekoConfigManager"):
                self.config = config
                self.transaction = None

            def __enter__(self):
                self.transaction = TransactionManager(self.config)
                return self.transaction

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:  # No exception occurred
                    # Apply all changes at once
                    self.transaction.commit()
                    # Save if in non-memory mode with a file path
                    if not self.config.in_memory and self.config.config_path:
                        self.config.save()
                return False  # Don't suppress exceptions

        return TransactionContext(self)
