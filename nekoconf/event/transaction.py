import copy
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..utils.helper import deep_merge, get_nested_value, set_nested_value
from .changes import ChangeTracker, ConfigChange, emit_change_events

if TYPE_CHECKING:
    from ..core.config import NekoConf


class TransactionManager:
    """Manages a set of configuration changes as a single transaction."""

    def __init__(self, config: "NekoConf"):
        """Initialize a transaction manager.

        Args:
            config_manager: The NekoConf instance
        """
        self.config = config
        self.old_data = self.config.data
        self.transaction_data = copy.deepcopy(self.config.data)
        self.changes = []

    def get(self, key: Optional[str] = None, default: Any = None) -> Any:
        """Get configuration value from the transaction state.

        Args:
            key: Configuration key
            default: Default value if not found

        Returns:
            Configuration value
        """

        if key is None:
            return self.transaction_data
        return get_nested_value(self.transaction_data, key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value in the transaction.

        Args:
            key: Configuration key
            value: Value to set
        """

        set_nested_value(self.transaction_data, key, value)

    def delete(self, key: str) -> bool:
        """Delete configuration value in the transaction.

        Args:
            key: Configuration key to delete

        Returns:
            True if successful
        """
        parts = key.split(".")
        data_ptr = self.transaction_data

        # Navigate to the parent of the target key
        for part in parts[:-1]:
            if not isinstance(data_ptr, dict) or part not in data_ptr:
                return False
            data_ptr = data_ptr[part]

        # Delete the key
        if isinstance(data_ptr, dict) and parts[-1] in data_ptr:
            del data_ptr[parts[-1]]
            return True
        return False

    def update(self, data: Dict[str, Any]) -> None:
        """Update multiple configuration values in the transaction.

        Args:
            data: Dictionary of values to update
        """

        deep_merge(source=data, destination=self.transaction_data, in_place=True)

    def replace(self, data: Dict[str, Any]) -> None:
        """Replace entire configuration in the transaction.

        Args:
            data: New configuration data
        """
        self.transaction_data = copy.deepcopy(data)

    def commit(self) -> List[ConfigChange]:
        """Commit the transaction to the configuration manager.

        Returns:
            List of changes applied
        """

        # Detect changes between old and new config
        changes = ChangeTracker.detect_changes(self.old_data, self.transaction_data)

        # Apply the transaction data to the config manager
        self.config.data = self.transaction_data

        if not self.config.event_disabled:
            emit_change_events(self.config, changes)

        return changes
