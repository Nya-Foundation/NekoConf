"""Configuration manager module for NekoConf.

This module provides functionality to read, write, and manage configuration files
in YAML and JSON formats.
"""

import asyncio
import logging
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

from .utils import (  # Relative import
    create_file_if_not_exists,
    deep_merge,
    get_nested_value,
    getLogger,
    is_async_callable,
    load_file,
    save_file,
    set_nested_value,
)


class NekoConfigManager:
    """Configuration manager for reading, writing, and observing configuration files."""

    def __init__(
        self,
        config_path: Union[str, Path],
        schema_path: Optional[Union[str, Path]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """Initialize the configuration manager.

        Args:
            config_path: Path to the configuration file
            schema_path: Path to the schema file for validation (optional)
            logger: Optional logger instance for logging messages
        """
        self.config_path = Path(config_path)
        self.schema_path = Path(schema_path) if schema_path else None

        self.logger = logger or getLogger(__name__)

        self.data: Dict[str, Any] = {}

        # Store observers as a dict: callback -> custom_kwargs
        self.observers_sync: Dict[Callable, Dict[str, Any]] = {}
        self.observers_async: Dict[Callable, Dict[str, Any]] = {}

        self._load_validators()
        self._init_config()  # Load the initial configuration

    def _init_config(self) -> None:
        """Initialize the configuration by loading it from the file."""
        create_file_if_not_exists(self.config_path)
        self.load()

    def _load_validators(self) -> None:
        """Load schema validators if available."""
        self.validator = None
        if self.schema_path:
            try:
                from .validator import NekoSchemaValidator  # Relative import

                self.validator = NekoSchemaValidator(self.schema_path)
                self.logger.debug(f"Loaded schema validator from {self.schema_path}")
            except ImportError:
                self.logger.warning(
                    "Schema validation requested but schema_validator module not available. "
                    "Install with pip install nekoconf[schema]"
                )
            except Exception as e:
                self.logger.error(f"Failed to load schema validator: {e}")

    def load(self) -> Dict[str, Any]:
        """Load configuration from file.

        Returns:
            The loaded configuration data
        """
        try:
            if self.config_path.exists():
                self.data = load_file(self.config_path)
                # self.logger.debug(f"Loaded configuration from {self.config_path}")
            else:
                self.logger.warning(f"Configuration file not found: {self.config_path}")
                self.data = {}
            return self.data
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            self.data = {}
            return self.data

    def save(self) -> bool:
        """Save configuration to file.

        Returns:
            True if successful, False otherwise
        """
        try:
            save_file(self.config_path, self.data)
            self.logger.debug(f"Saved configuration to {self.config_path}")

            # Notify observers after saving
            self._notify_observers()
            return True
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
            return False

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration data.

        Returns:
            The entire configuration data as a dictionary
        """
        return self.data

    def get(self, key: Optional[str] = None, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The configuration value or default if not found
        """
        if key is None:
            return self.data

        return get_nested_value(self.data, key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            value: The value to set
        """
        set_nested_value(self.data, key, value)

    def delete(self, key: str) -> bool:
        """Delete a configuration value.

        Args:
            key: The configuration key (dot notation for nested values)

        Returns:
            True if the key was deleted, False if it didn't exist
        """
        parts = key.split(".")
        data = self.data

        # Navigate to the parent of the target key
        for i, part in enumerate(parts[:-1]):
            if part not in data or not isinstance(data[part], dict):
                return False
            data = data[part]

        # Delete the key if it exists
        if parts[-1] in data:
            del data[parts[-1]]
            return True

        return False

    def update(self, data: Dict[str, Any], deep_merge_enabled: bool = True) -> None:
        """Update multiple configuration values.

        Args:
            data: Dictionary of configuration values to update
            deep_merge_enabled: Whether to perform deep merge for nested dictionaries
        """
        if deep_merge_enabled:
            self.data = deep_merge(source=data, destination=self.data)
        else:
            self.data.update(data)

        self.save()  # Save the configuration after setting the value

    def register_observer(self, observer: Callable, **kwargs) -> None:
        """Register an observer function to be called when new configuration was saved.

        Args:
            observer: Function to call with the updated configuration data
            **kwargs: Additional keyword arguments to pass to the observer when called

        Raises:
            TypeError: If the provided observer is not callable.
        """
        if not callable(observer):
            raise TypeError(
                f"Observer must be callable, but received type {type(observer).__name__}"
            )

        if is_async_callable(observer):
            self.observers_async[observer] = kwargs
        else:
            self.observers_sync[observer] = kwargs

    def unregister_observer(self, observer: Callable) -> None:
        """Unregister an observer function.

        Args:
            observer: Function to remove from observers
        """
        # Remove from async observers if it exists
        if observer in self.observers_async:
            del self.observers_async[observer]

        if observer in self.observers_sync:
            del self.observers_sync[observer]

        self.logger.debug(f"Unregistered configuration observer: {observer.__name__}")

    def _notify_observers(self) -> List[asyncio.Future]:
        """Notify all observers of configuration changes.

        Returns:
            A list of asyncio.Future objects for any async observers
            scheduled within an existing event loop. Returns an empty
            list otherwise.
        """
        if not self.observers_sync and not self.observers_async:
            return []

        futures = []  # List to store futures

        # Notify synchronous observers
        for observer, kwargs in self.observers_sync.items():

            # Create a copy of kwargs to avoid modifying the stored ones
            call_kwargs = kwargs.copy()
            # Ensure config_data is present for the call
            call_kwargs["config_data"] = self.data

            try:
                observer(**call_kwargs)  # Use call_kwargs
            except Exception as e:
                self.logger.error(f"Error triggering in observer {observer.__name__}: {e}")

        # Notify asynchronous observers
        for observer, kwargs in self.observers_async.items():

            # Create a copy of kwargs to avoid modifying the stored ones
            call_kwargs = kwargs.copy()
            # Ensure config_data is present for the call
            call_kwargs["config_data"] = self.data

            try:
                loop = asyncio.get_event_loop()
                # Check if we're in an event loop
                if loop.is_running():
                    # If in an event loop, schedule the coroutine and store the future
                    future = asyncio.ensure_future(observer(**call_kwargs))  # Use call_kwargs
                    futures.append(future)
                else:
                    # If not in an event loop, run the coroutine in a new event loop
                    asyncio.run(observer(**call_kwargs))  # Use call_kwargs

            except Exception as e:
                self.logger.error(
                    f"Error triggering async observers: {e}, {traceback.format_exc()}"
                )

        return futures  # Return the list of futures

    def validate(self) -> List[str]:
        """Validate configuration against schema.

        Returns:
            List of validation error messages (empty if valid)
        """
        if not self.validator:
            self.logger.warning("No schema validator available, skipping validation")
            return []

        return self.validator.validate(self.data)
