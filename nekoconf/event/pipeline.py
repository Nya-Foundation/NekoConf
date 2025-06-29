"""Event pipeline system for NekoConf.

This module provides functionality to define and execute event pipelines
for configuration changes, with support for filtering and transformation.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Union

from ..utils.helper import getLogger
from .handler import EventContext, EventHandler
from .type import EventType


class EventPipeline:
    """Central event pipeline for NekoConf configuration events."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the event pipeline.

        Args:
            logger: Optional logger for event logging
        """
        self.logger = logger or getLogger(__name__)
        self.handlers: List[EventHandler] = []

    def register_handler(
        self,
        callback: Callable,
        event_types: Union[EventType, List[EventType]],
        path_pattern: Optional[str] = None,
        priority: int = 100,
        **kwargs,
    ) -> EventHandler:
        """Register a new event handler.

        Args:
            callback: Function to call when event occurs
            event_types: Type(s) of events this handler responds to
            path_pattern: Optional path pattern to filter events
            priority: Handler priority (lower number = higher priority)
            **kwargs: Additional keyword arguments to pass to callback

        Returns:
            The registered handler
        """

        # Convert single event type to a set
        if isinstance(event_types, EventType):
            event_types = {event_types}
        else:
            event_types = set(event_types)

        handler = EventHandler(callback, event_types, path_pattern, priority, **kwargs)
        self.handlers.append(handler)

        # Sort handlers by priority
        self.handlers.sort(key=lambda h: h.priority)

        self.logger.debug(
            f"Registered handler {callback.__name__} for "
            f"{[e.value for e in event_types]}"
            + (f" with path pattern '{path_pattern}'" if path_pattern else "")
        )

        return handler

    def unregister_handler(self, handler: EventHandler) -> bool:
        """Unregister an event handler.

        Args:
            handler: Handler to remove

        Returns:
            True if handler was found and removed
        """
        if handler in self.handlers:
            self.handlers.remove(handler)
            self.logger.debug(f"Unregistered handler {handler.callback.__name__}")
            return True
        return False

    def emit(
        self,
        event_type: EventType,
        path: Optional[str] = None,
        old_value: Any = None,
        new_value: Any = None,
        config_data: Optional[Dict[str, Any]] = None,
        ignore: Optional[bool] = False,
    ) -> int:
        """Emit an event to be processed by handlers.

        Args:
            event_type: Type of event, e.g., CHANGE, CREATE, DELETE
            path: Configuration path that changed
            old_value: Previous value
            new_value: New value
            config_data: Complete updated configuration data
            ignore: If True, ignore this event

        Returns:
            Number of handlers that processed the event
        """
        if ignore:
            return 0

        context = EventContext(event_type, path, old_value, new_value, config_data)
        count = 0

        for handler in self.handlers:
            if handler.matches(context):
                try:
                    handler.handle_event(context)
                    count += 1
                except Exception as e:
                    self.logger.error(
                        f"Error in handler {handler.callback.__name__} for {event_type.value}: {e}"
                    )

        return count


def on_event(
    event_pipeline: EventPipeline,
    event_type: Union[EventType, List[EventType]],
    path_pattern: Optional[str] = None,
    priority: int = 100,
):
    """Decorator to register a function as an event handler.

    Example:
        @on_event(pipeline, EventType.CHANGE, "database.connection")
        def handle_db_connection_change(event_type, path, old_value, new_value, config_data, **kwargs):
            # Reconnect to database with new settings
            pass

    Args:
        event_pipeline: The event pipeline to register with
        event_type: Type(s) of events to handle
        path_pattern: Optional path pattern to filter events
        priority: Handler priority (lower number = higher priority)

    Returns:
        Decorator function
    """

    def decorator(func):
        event_pipeline.register_handler(func, event_type, path_pattern, priority)
        return func

    return decorator


def on_change(event_pipeline: EventPipeline, path_pattern: str, priority: int = 100):
    """Decorator to register a function as a change event handler.

    Example:
        @on_change(pipeline, "database.connection")
        def handle_db_connection_change(event_type, path, old_value, new_value, config_data, **kwargs):
            # Reconnect to database with new settings
            pass

    Args:
        event_pipeline: The event pipeline to register with
        path_pattern: Path pattern to filter events
        priority: Handler priority (lower number = higher priority)

    Returns:
        Decorator function
    """
    return on_event(event_pipeline, EventType.CHANGE, path_pattern, priority)
