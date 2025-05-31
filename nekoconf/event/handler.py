from typing import Any, Callable, Dict, Optional, Set

from ..utils.helper import getLogger, is_async_callable
from .match import PathMatcher
from .type import EventType


class EventContext:
    """Context information for a configuration event."""

    def __init__(
        self,
        event_type: EventType,
        path: str = None,
        old_value: Any = None,
        new_value: Any = None,
        config_data: Dict[str, Any] = None,
    ):
        """Initialize event context.

        Args:
            event_type: The type of event that occurred
            path: The configuration path that changed (enhanced dot notation)
            old_value: The previous value (if applicable)
            new_value: The new value (if applicable)
            config_data: The complete configuration data
        """
        self.event_type = event_type
        self.path = path
        self.old_value = old_value
        self.new_value = new_value
        self.config_data = config_data or {}


class EventHandler:
    """Handler for configuration events."""

    def __init__(
        self,
        callback: Callable,
        event_types: Set[EventType],
        path_pattern: Optional[str] = None,
        priority: int = 100,
        **kwargs,
    ):
        """Initialize an event handler.

        Args:
            callback: Function to call when event occurs
            event_types: Types of events this handler responds to
            path_pattern: Optional path pattern to filter events (enhanced dot notation)
            priority: Handler priority (lower number = higher priority)
            **kwargs: Additional keyword arguments to pass to callback
        """
        if not callable(callback):
            raise TypeError(f"Callback must be callable, received {type(callback).__name__}")

        self.callback = callback
        self.event_types = event_types
        self.path_pattern = path_pattern
        self.priority = priority
        self.kwargs = kwargs
        self.is_async = is_async_callable(callback)

        self.logger = getLogger(__name__)

    def matches(self, context: EventContext) -> bool:
        """Check if this handler should handle the given event.

        Args:
            context: Event context

        Returns:
            True if handler should handle this event
        """
        # Check event type
        if context.event_type not in self.event_types:
            return False

        # If no path filter, handle all paths
        if not self.path_pattern:
            return True

        # Special pattern for global-only events
        if self.path_pattern == "@global":
            # Only match events with global path marker
            return context.path == "*" or context.path is None

        # Standard wildcard "*" - matches everything
        if self.path_pattern == "*":
            return True

        # If event is global, but handler wants specific paths, don't match
        # This prevents specific path handlers from receiving global notifications
        if context.path == "*" or context.path is None:
            return False

        try:
            # Use PathMatcher for path matching with enhanced dot notation
            return PathMatcher.match(self.path_pattern, context.path)
        except Exception as e:
            # Log but don't fail, just consider it a non-match
            self.logger.debug(
                f"Error matching path pattern '{self.path_pattern}' to '{context.path}': {e}"
            )
            return False

    async def handle_async(self, context: EventContext) -> None:
        """Handle event asynchronously.

        Args:
            context: Event context
        """
        kwargs = self.kwargs.copy()

        # Add standard parameters
        kwargs.update(
            {
                "event_type": context.event_type,
                "path": context.path,
                "old_value": context.old_value,
                "new_value": context.new_value,
                "config_data": context.config_data,
            }
        )

        try:
            # Call async or sync callback
            if self.is_async:
                await self.callback(**kwargs)
            else:
                self.callback(**kwargs)
        except Exception as e:
            import traceback

            # Log the error but don't propagate it
            self.logger.error(f"Error in event handler {self.callback.__name__}: {e}")
            self.logger.debug(traceback.format_exc())

    def handle_event(self, context: EventContext) -> None:
        """Handle event synchronously.

        Args:
            context: Event context
        """
        kwargs = self.kwargs.copy()

        # Add standard parameters
        kwargs.update(
            {
                "event_type": context.event_type,
                "path": context.path,
                "old_value": context.old_value,
                "new_value": context.new_value,
                "config_data": context.config_data,
            }
        )

        # Call the callback - with error handling
        try:
            if self.is_async:
                # For async callbacks in sync context, we create a new event loop if needed
                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                    # If we're already in a running event loop, schedule the task
                    asyncio.create_task(self.callback(**kwargs))
                except RuntimeError:
                    # Handle case when there's no event loop
                    asyncio.run(self.callback(**kwargs))
            else:
                # For sync callbacks, just call directly
                self.callback(**kwargs)
        except Exception as e:
            # Log the error but don't propagate it
            import traceback

            self.logger.error(f"Error in event handler {self.callback.__name__}: {e}")
            self.logger.debug(traceback.format_exc())
