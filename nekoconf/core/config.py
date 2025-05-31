"""Configuration manager module for NekoConf.

This module provides functionality to read, write, and manage configuration files
in YAML, JSON, and TOML formats using pluggable storage backends.
"""

import copy
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, TypeVar, Union, overload

# Type variable for type hints
T = TypeVar("T")

from ..event.changes import ChangeTracker, ChangeType, ConfigChange, emit_change_events
from ..event.pipeline import EventPipeline, EventType, on_change, on_event

# Check for optional dependencies
from ..schema import HAS_SCHEMA_DEPS, NekoSchemaValidator
from ..storage import (
    FileStorageBackend,
    StorageBackend,
    StorageError,
)
from ..utils.env import EnvOverrideHandler
from ..utils.helper import (
    deep_merge,
    delete_nested_value,
    get_nested_value,
    getLogger,
    set_nested_value,
)

if TYPE_CHECKING:
    pass


class NekoConf:
    """Configuration manager for reading, writing, and event handling configuration files.

    This class provides both low-level configuration management and high-level
    type-safe convenience methods for accessing configuration values.
    """

    def __init__(
        self,
        storage: Optional[Union[StorageBackend, str, Path, dict]] = None,
        schema_path: Optional[Union[str, Path]] = None,
        logger: Optional[logging.Logger] = None,
        read_only: Optional[bool] = False,
        # Environment variable override parameters
        env_override_enabled: bool = False,
        env_prefix: str = "NEKOCONF",
        env_nested_delimiter: str = "_",
        env_include_paths: Optional[List[str]] = None,
        env_exclude_paths: Optional[List[str]] = None,
        env_preserve_case: bool = False,
        env_strict_parsing: bool = False,
        # Event handling parameters
        event_emission_enabled: bool = False,
    ) -> None:
        """Initialize the configuration manager.

        Args:
            storage: Optional storage backend instance. If None (default), uses memory-only storage.
                    storage can be a string (file path) or a dictionary for in-memory data.
                    Create backends using: FileStorageBackend(), RemoteStorageBackend(), etc.
            schema_path: Path to the schema file for validation (optional)
            read_only: If True, prevents writing to the storage backend (default: False)
            logger: Optional logger instance for logging messages
            env_override_enabled: Enable/disable environment variable overrides (default: False)
            env_prefix: Prefix for environment variables (default: "NEKOCONF"). Set to "" for no prefix.
            env_nested_delimiter: Delimiter used in env var names for nested keys (default: "_")
            env_include_paths: List of dot-separated paths to include in overrides.
                               If None or empty, all keys are potentially included (default: None).
            env_exclude_paths: List of dot-separated paths to exclude from overrides.
                               Takes precedence over include_paths (default: None).
            env_preserve_case: If True, preserves the original case of keys from environment variables.
            env_strict_parsing: If True, raises exceptions when parsing fails rather than logging warnings.
            event_emission_enabled: If True, emits events for configuration changes (default: False)

        Examples:
            # Memory-only storage (default)
            config = NekoConf()
            config = NekoConf({"debug": True})

            # File storage for persistent configurations
            config = NekoConf("config.yaml")
            config = NekoConf(Path("config.yaml"))
            config = NekoConf(storage=FileStorageBackend("config.yaml"))

            # Remote storage for distributed configurations
            config = NekoConf(storage=RemoteStorageBackend("https://nekoconf-server.com", api_key="key"))
        """
        self.logger = logger or getLogger(__name__)
        self.schema_path = Path(schema_path) if schema_path else None

        # Initialize configuration data
        self.data: Dict[str, Any] = {}

        self.read_only = read_only

        if self.read_only:
            self.logger.debug("Configuration is read-only, no changes will be saved")

        # Initialize storage backend
        self._memory_only = False
        self.storage_backend: StorageBackend = self._init_storage_backend(storage)
        if self.storage_backend:
            self.logger.debug(f"Using storage backend: {self.storage_backend}")
            self.storage_backend.set_change_callback(self._handle_storage_update)
        else:
            self.logger.debug("Using memory-only storage")
            self._memory_only = True

        # Initialize environment variable override handler
        self.env_handler: Optional[EnvOverrideHandler] = None
        if env_override_enabled:
            self.env_handler = EnvOverrideHandler(
                prefix=env_prefix,
                nested_delimiter=env_nested_delimiter,
                include_paths=env_include_paths,
                exclude_paths=env_exclude_paths,
                logger=self.logger,
                preserve_case=env_preserve_case,
                strict_parsing=env_strict_parsing,
            )

        # Event pipeline initialization
        self.event_disabled = not event_emission_enabled
        self.event_pipeline: EventPipeline = EventPipeline(logger=self.logger)

        self._load_validators()
        self._init_config()

    def _init_storage_backend(
        self, storage: Optional[Union[StorageBackend, str, Path, dict]]
    ) -> None:
        """Handle the storage backend initialization with fallbacks.

        Args:
            storage: Storage backend instance or path to a file
        """
        if storage is None:
            return None
        elif isinstance(storage, StorageBackend):
            return storage
        elif isinstance(storage, Path):
            return FileStorageBackend(storage)
        elif isinstance(storage, dict):
            self.data = storage
            return None
        elif isinstance(storage, str):
            return FileStorageBackend(storage)
        else:
            raise TypeError(
                f"storage must be a StorageBackend instance. "
                f"Got {type(storage)}. Use FileStorageBackend(), RemoteStorageBackend(), etc."
            )

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()
        return False  # Don't suppress exceptions

    def cleanup(self):
        """Clean up resources used by the configuration manager."""
        # Clean up storage backend
        if self.storage_backend:
            self.storage_backend.cleanup()

    def _init_config(self) -> None:
        """Initialize the configuration by loading it from the storage backend."""
        if self._memory_only:
            # For memory-only mode, data is already initialized in __init__
            self.logger.debug("Using memory-only storage with initial data")
            return

        try:
            # Load initial configuration from storage backend
            self.data = self.storage_backend.load()
            self.logger.debug(
                f"Initialized configuration from storage backend, {self.storage_backend}"
            )
        except StorageError as e:
            self.logger.error(f"Failed to initialize configuration: {e}")
            self.data = {}

    def _handle_storage_update(self, config_data: Dict[str, Any]) -> None:
        """Handle updates from the storage backend."""
        self.replace(config_data)

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

    def load(self) -> Dict[str, Any]:
        """Load configuration from storage backend and apply environment variable overrides.

        Returns:
            The effective configuration data after overrides.
        """
        if self._memory_only:
            self.logger.debug("Memory-only mode: no storage backend to load from")
            return self.data

        try:
            loaded_data = self.storage_backend.load()
            self.logger.debug("Loaded configuration from storage backend")
        except StorageError as e:
            self.logger.error(f"Error loading configuration: {e}")
            loaded_data = {}

        # Apply environment variable overrides to the loaded data
        old_data = copy.deepcopy(self.data)

        # Use the env_handler to apply overrides
        if self.env_handler:
            self.data = self.env_handler.apply_overrides(loaded_data, in_place=True)
        else:
            self.data = loaded_data

        # Emit reload event with old and new values
        self.event_pipeline.emit(
            EventType.RELOAD,
            old_value=old_data,
            new_value=self.data,
            config_data=self.data,
            ignore=self.event_disabled,
        )

        # If the loaded data is empty or unchanged, do not emit further events
        if not old_data or old_data == self.data or self.event_disabled:
            return self.data

        changes = ChangeTracker.detect_changes(old_data, self.data)

        if changes:
            emit_change_events(self, changes)

        return self.data

    def reload(self) -> Dict[str, Any]:
        return self.load()

    def save(self) -> bool:
        """Save configuration to storage backend.

        Note: This saves the *current effective configuration* which might include
        values that were originally overridden by environment variables but later
        modified via set/update.

        Returns:
            True if successful, False otherwise
        """
        if self._memory_only:
            self.logger.debug("Memory-only mode: no storage backend to save to")
            return True

        if self.read_only:
            self.logger.warning("Configuration is read-only, not saving")
            return False

        try:
            success = self.storage_backend.save(self.data)
            if success:
                self.logger.debug("Saved configuration to storage backend")
            else:
                self.logger.error("Failed to save configuration to storage backend")
            return success
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
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The configuration value or default if not found
        """
        if key is None:
            return self.data

        # Use the utility which handles nested keys
        return get_nested_value(self.data, key, default)

    # Type-safe convenience methods for accessing configuration values
    @overload
    def get_typed(self, key: str, default: None = None) -> Any: ...

    @overload
    def get_typed(self, key: str, default: T) -> T: ...

    def get_typed(self, key: str, default: Optional[T] = None) -> Union[Any, T]:
        """Get a configuration value with type preservation.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The configuration value (preserving the type of default if provided)
        """
        value = self.get(key, default)
        if default is not None and value is not None:
            try:
                # Try to convert the value to the same type as default
                value_type = type(default)
                return value_type(value)
            except (ValueError, TypeError):
                self.logger.warning(
                    f"Failed to convert '{key}' to type {type(default).__name__}, using as-is"
                )
        return value

    def get_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        """Get an integer configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The integer value or default if not found/not an integer
        """
        value = self.get(key, default)
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            self.logger.warning(f"Value for '{key}' is not a valid integer, using default")
            return default

    def get_float(self, key: str, default: Optional[float] = None) -> Optional[float]:
        """Get a float configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The float value or default if not found/not a float
        """
        value = self.get(key, default)
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            self.logger.warning(f"Value for '{key}' is not a valid float, using default")
            return default

    def get_bool(self, key: str, default: Optional[bool] = None) -> Optional[bool]:
        """Get a boolean configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The boolean value or default if not found/not a boolean
        """
        value = self.get(key, default)
        if value is None:
            return default

        if isinstance(value, bool):
            return value

        # Handle string values
        if isinstance(value, str):
            if value.lower() in ("true", "yes", "1", "on"):
                return True
            if value.lower() in ("false", "no", "0", "off"):
                return False

        # Handle numeric values
        try:
            return bool(int(value))
        except (ValueError, TypeError):
            self.logger.warning(f"Value for '{key}' is not a valid boolean, using default")
            return default

    def get_str(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a string configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The string value or default if not found
        """
        value = self.get(key, default)
        if value is None:
            return default
        return str(value)

    def get_list(self, key: str, default: Optional[List] = None) -> Optional[List]:
        """Get a list configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The list value or default if not found/not a list
        """
        value = self.get(key, default)
        if value is None:
            return default

        if isinstance(value, list):
            return value

        self.logger.warning(f"Value for '{key}' is not a list, using default")
        return default

    def get_dict(self, key: str, default: Optional[Dict] = None) -> Optional[Dict]:
        """Get a dictionary configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The dictionary value or default if not found/not a dictionary
        """
        value = self.get(key, default)
        if value is None:
            return default

        if isinstance(value, dict):
            return value

        self.logger.warning(f"Value for '{key}' is not a dictionary, using default")
        return default

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value in the *effective* configuration.

        This change will be persisted on the next `save()`.

        Args:
            key: The configuration key (dot notation for nested values)
            value: The value to set
        """

        if self.read_only:
            self.logger.warning("Configuration is read-only, not setting value")
            return

        # Make a copy of current state
        old_data = copy.deepcopy(self.data)

        # Apply the change
        is_updated = set_nested_value(self.data, key, value)

        # If the value was not updated (same value), we don't emit an event
        if not is_updated:
            return

        # if event emission is disabled, skip emitting events
        if self.event_disabled:
            return True

        # Detect changes between configurations
        changes = ChangeTracker.detect_changes(old_data, self.data)
        emit_change_events(self, changes)

    def delete(self, key: str) -> bool:
        """Delete a configuration value from the *effective* configuration.

        This change will be persisted on the next `save()`.

        Args:
            key: The configuration key (dot notation for nested values)

        Returns:
            True if the key was deleted, False if it didn't exist
        """
        if self.read_only:
            self.logger.warning("Configuration is read-only, not deleting value")
            return False

        # Make a copy of current state for change detection
        old_data = copy.deepcopy(self.data)

        # Use the utility function to delete the nested value
        success, old_value = delete_nested_value(self.data, key)

        if not success:
            return False  # Key didn't exist

        # Emit events if enabled
        if not self.event_disabled:
            changes = [
                ConfigChange(ChangeType.DELETE, key, old_value=old_value, new_value=None),
                ConfigChange(ChangeType.CHANGE, old_value=old_data, new_value=self.data),
            ]
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
        if not data or data == self.data:
            return False

        old_data = copy.deepcopy(self.data)

        # Apply the new data
        self.data = data

        # if event emission is disabled, skip emitting events
        if self.event_disabled:
            return True

        # Detect changes between configurations
        changes = ChangeTracker.detect_changes(old_data, data)
        emit_change_events(self, changes)

        return True

    def update(self, data: Dict[str, Any]) -> bool:
        """Update multiple configuration values in the *effective* configuration (no deletion).

        This change will be persisted on the next `save()`.

        Args:
            data: Dictionary of configuration values to update

        Returns:
            True if the configuration was updated, False if no changes were made
        """

        if not data or data == self.data:
            return False

        # Make deep copies to prevent mutations
        old_data = copy.deepcopy(self.data)

        # Create an updated version by deep merging
        deep_merge(source=data, destination=self.data, in_place=True)

        # if event emission is disabled, skip emitting events
        if self.event_disabled:
            return True

        # Detect changes between configurations
        changes = ChangeTracker.detect_changes(old_data, self.data)
        emit_change_events(self, changes)

        return True

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

    def validate_schema(self, data: Optional[Dict[str, Any]] = None) -> List[str]:
        """Validate the configuration against the schema.
        Args:
            data: Optional data to validate (if None, uses the effective configuration)
        Returns:
            List of validation error messages (empty if valid)
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

        read_only = self.read_only

        class TransactionContext:
            def __init__(self, config: "NekoConf"):
                self.config = config
                self.transaction = None

            def __enter__(self):
                self.transaction = TransactionManager(self.config)
                return self.transaction

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:  # No exception occurred
                    # Apply all changes at once
                    self.transaction.commit()
                    # Save if storage backend supports writes
                    if self.config.storage_backend and not read_only:
                        self.config.save()
                return False  # Don't suppress exceptions

        return TransactionContext(self)
