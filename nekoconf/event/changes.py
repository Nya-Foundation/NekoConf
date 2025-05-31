"""Change detection and tracking for NekoConf.

This module provides utilities for detecting and tracking changes between configuration states,
generating appropriate events for path-based modifications.
"""

from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Tuple

from ..utils.helper import getLogger
from .pipeline import EventType

if TYPE_CHECKING:
    from ..core.config import NekoConf

logger = getLogger(__name__)


class ChangeType(Enum):
    """Types of changes that can be detected between configurations."""

    CREATE = "create"  # A new configuration key was created
    UPDATE = "update"  # An existing configuration key was updated
    DELETE = "delete"  # A configuration key was deleted
    CHANGE = "change"  # A change occurred, but not specifically create/update/delete


class ConfigChange:
    """Represents a single change to a configuration value."""

    def __init__(
        self,
        change_type: ChangeType,
        path: str = "*",
        old_value: Any = None,
        new_value: Any = None,
    ):
        """Initialize a configuration change.

        Args:
            change_type: The type of change (create, update, delete)
            path: The path to the changed configuration item
            old_value: The previous value (None for creates)
            new_value: The new value (None for deletes)
        """
        self.change_type = change_type
        self.path = path or "*"
        self.old_value = old_value
        self.new_value = new_value

    def to_event_type(self) -> EventType:
        """Convert change type to event type.

        Returns:
            The corresponding EventType for this change
        """
        if self.change_type == ChangeType.CREATE:
            return EventType.CREATE
        elif self.change_type == ChangeType.UPDATE:
            return EventType.UPDATE
        elif self.change_type == ChangeType.DELETE:
            return EventType.DELETE
        elif self.change_type == ChangeType.CHANGE:
            return EventType.CHANGE
        else:
            return EventType.CHANGE


class ChangeTracker:
    """Utility for tracking changes between configuration states."""

    @staticmethod
    def detect_changes(
        old_config: Dict[str, Any], new_config: Dict[str, Any]
    ) -> List[ConfigChange]:
        """Detect changes between two configuration states.

        Args:
            old_config: Previous configuration state
            new_config: New configuration state

        Returns:
            List of ConfigChange objects describing the changes
        """
        changes = []

        if not old_config and not new_config:
            return changes

        if old_config == new_config:
            return changes

        # record the global change
        changes.append(ConfigChange(ChangeType.CHANGE, "*", old_config, new_config))

        # Process all paths in both configs
        for path, change in ChangeTracker._walk_changes(old_config, new_config):
            changes.append(change)

        return changes

    @staticmethod
    def _walk_changes(
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        parent_path: str = "",
    ) -> Generator[Tuple[str, ConfigChange], None, None]:
        """Walk through old and new configs, yielding changes.

        Args:
            old_data: Previous configuration state
            new_data: New configuration state
            parent_path: Path prefix for nested values

        Yields:
            Tuples of (path, change) for each detected change
        """
        # Find keys in both configs
        old_keys = set(old_data.keys() if isinstance(old_data, dict) else [])
        new_keys = set(new_data.keys() if isinstance(new_data, dict) else [])

        # Process deleted keys (in old but not new)
        for key in old_keys - new_keys:
            path = f"{parent_path}.{key}" if parent_path else key
            yield path, ConfigChange(
                ChangeType.DELETE, path, old_value=old_data[key], new_value=None
            )

        # Process created keys (in new but not old)
        for key in new_keys - old_keys:
            path = f"{parent_path}.{key}" if parent_path else key
            yield path, ConfigChange(
                ChangeType.CREATE, path, old_value=None, new_value=new_data[key]
            )

        # Process common keys
        for key in new_keys & old_keys:
            path = f"{parent_path}.{key}" if parent_path else key
            old_value = old_data[key]
            new_value = new_data[key]

            # Handle different types
            if type(old_value) != type(new_value):
                yield path, ConfigChange(
                    ChangeType.UPDATE, path, old_value=old_value, new_value=new_value
                )

            # Both are dictionaries - recurse
            elif isinstance(new_value, dict) and isinstance(old_value, dict):
                yield from ChangeTracker._walk_changes(old_value, new_value, path)

            # Both are lists - check if they're different
            elif isinstance(new_value, list) and isinstance(old_value, list):
                if new_value != old_value:
                    yield path, ConfigChange(
                        ChangeType.UPDATE,
                        path,
                        old_value=old_value,
                        new_value=new_value,
                    )

            # Atomic values - check equality
            elif new_value != old_value:
                yield path, ConfigChange(
                    ChangeType.UPDATE, path, old_value=old_value, new_value=new_value
                )


def emit_change_events(config: "NekoConf", changes: List[ConfigChange]) -> None:
    """Emit events for a list of changes.

    This centralizes event emission logic in one place.

    Args:
        config_manager: The NekoConf instance
        changes: List of changes to emit events for
        ignore: If True, ignore the changes and don't emit events
    """

    if not changes:
        return

    # Emit specific events for each path change
    for change in changes:
        event_type = change.to_event_type()
        config.event_pipeline.emit(
            event_type,
            path=change.path or "*",
            old_value=change.old_value,
            new_value=change.new_value,
            config_data=config.data,
        )

        # Also emit CHANGE event for each specific path
        if event_type != EventType.CHANGE:
            config.event_pipeline.emit(
                EventType.CHANGE,
                path=change.path,
                old_value=change.old_value,
                new_value=change.new_value,
                config_data=config.data,
            )

        if change.path != "*":
            logger.debug(
                f"Emitted {event_type.value} event for path '{change.path}' "
                f"from '{change.old_value}' to '{change.new_value}'"
            )
