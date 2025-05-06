from enum import Enum


class EventType(Enum):
    """Types of configuration events."""

    CHANGE = "change"  # Any configuration change
    CREATE = "create"  # New configuration key created
    UPDATE = "update"  # Existing configuration key updated
    DELETE = "delete"  # Configuration key deleted
    RELOAD = "reload"  # Configuration reloaded from disk
    VALIDATE = "validate"  # Configuration validation event
