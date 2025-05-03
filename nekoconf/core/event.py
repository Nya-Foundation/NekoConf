"""Event pipeline system for NekoConf.

This module provides functionality to define and execute event pipelines
for configuration changes, with support for filtering and transformation.
"""

import asyncio
import inspect
import logging
import re
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Union

import jmespath
from jmespath.exceptions import ParseError

from .utils import getLogger, is_async_callable


class EventType(Enum):
    """Types of configuration events."""

    CHANGE = "change"  # Any configuration change
    CREATE = "create"  # New configuration key created
    UPDATE = "update"  # Existing configuration key updated
    DELETE = "delete"  # Configuration key deleted
    RELOAD = "reload"  # Configuration reloaded from disk
    VALIDATE = "validate"  # Configuration validation event


class PathMatcher:
    """Utility class for matching configuration paths against patterns using JMESPath."""

    @staticmethod
    def match(pattern: str, path: str) -> bool:
        """Match a path against a pattern using JMESPath expressions.

        Args:
            pattern: The pattern to match against (JMESPath or wildcard expressions)
            path: The actual path to check

        Returns:
            True if the path matches the pattern
        """
        if not pattern or not path:
            return pattern == path

        # Global wildcard matches everything
        if pattern == "*":
            return True

        # Exact match
        if pattern == path:
            return True

        # Handle wildcard at the end (e.g., "database.*")
        if pattern.endswith(".*"):
            base_pattern = pattern[:-2]
            # Parent path exact match (e.g., "database.*" matches "database")
            if path == base_pattern:
                return True

            # Child path match (e.g., "database.*" matches "database.host")
            if path.startswith(f"{base_pattern}."):
                return True

        # Convert path to a nested structure for JMESPath evaluation
        try:
            # Build a simple tree structure for JMESPath to query
            nested_structure = PathMatcher._path_to_nested_structure(path)

            # Try to evaluate the pattern against the structure
            # First, normalize pattern for JMESPath if needed
            jmespath_pattern = PathMatcher._normalize_pattern_for_jmespath(pattern)

            # Use JMESPath to evaluate if the path matches the pattern
            expression = jmespath.compile(jmespath_pattern)
            result = expression.search(nested_structure)

            return result is not None
        except (ParseError, ValueError):
            # Fall back to simpler matching for non-JMESPath expressions
            return PathMatcher._fallback_match(pattern, path)

    @staticmethod
    def _normalize_pattern_for_jmespath(pattern: str) -> str:
        """Normalize a path pattern to work with JMESPath.

        Args:
            pattern: The original pattern

        Returns:
            A normalized pattern suitable for JMESPath
        """
        # Handle wildcards
        if "*" in pattern and "[" not in pattern:
            # Simple wildcard like "servers.*.name" needs special handling
            parts = pattern.split(".")
            for i, part in enumerate(parts):
                if part == "*":
                    parts[i] = "[*]"

            # Reconstruct the pattern
            pattern = ".".join(parts)

        return pattern

    @staticmethod
    def _path_to_nested_structure(path: str) -> Dict:
        """Convert a path string to a nested dictionary structure.

        Args:
            path: Path string like "database.servers[0].host"

        Returns:
            Nested dictionary representing the path
        """
        parts = re.split(r"\.|\[|\]", path)
        parts = [p for p in parts if p]  # Remove empty parts

        result = {}
        current = result

        for i, part in enumerate(parts):
            if part.isdigit():
                # Handle array indices
                idx = int(part)
                parent_key = parts[i - 1]

                # Make sure parent exists and is a list
                if parent_key not in current:
                    current[parent_key] = []

                # Extend the list if needed
                while len(current[parent_key]) <= idx:
                    current[parent_key].append({})

                # Move pointer to the array element
                current = current[parent_key][idx]
            else:
                # Handle regular keys
                if i < len(parts) - 1 and parts[i + 1].isdigit():
                    # Next part is an array index
                    current[part] = []
                elif i == len(parts) - 1:
                    # Last part, set a non-empty value
                    current[part] = True
                else:
                    # Regular nested object
                    current[part] = {}
                    current = current[part]

        return result

    @staticmethod
    def _fallback_match(pattern: str, path: str) -> bool:
        """Fallback path matching for patterns that can't be parsed as JMESPath.

        Args:
            pattern: The pattern to match
            path: The path to check

        Returns:
            True if the path matches the pattern
        """
        # Handle wildcards in path segments
        if "*" in pattern:
            # Convert pattern to regex
            regex_pattern = pattern.replace(".", r"\.").replace("*", r"[^.]*")
            if re.match(f"^{regex_pattern}$", path):
                return True

        # Handle JMESPath array notation
        if "[" in pattern or "[" in path:
            # Pattern with array wildcards like servers[*].config
            pattern_with_wildcard_arrays = re.sub(r"\[\d+\]", "[*]", path)
            if pattern == pattern_with_wildcard_arrays:
                return True

            # Convert array access pattern to regex
            array_pattern = re.sub(r"\[[*\d]\]", r"(?:\[\d+\]|\[\*\])", pattern.replace(".", r"\."))
            if re.match(f"^{array_pattern}$", path):
                return True

        return False


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
            path: The configuration path that changed (JMESPath expressions)
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
            path_pattern: Optional path pattern to filter events (JMESPath expressions)
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

        # If event has no path, only match if handler accepts global wildcard
        if not context.path:
            return self.path_pattern == "*"

        try:
            # Use PathMatcher for path matching with JMESPath
            return PathMatcher.match(self.path_pattern, context.path)
        except Exception as e:
            # Log but don't fail, just consider it a non-match
            logging.debug(
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
            logging.error(f"Error in event handler {self.callback.__name__}: {e}")
            logging.debug(traceback.format_exc())

    def handle_sync(self, context: EventContext) -> None:
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
                try:
                    import asyncio

                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If we're already in a running event loop, schedule the task
                        asyncio.create_task(self.callback(**kwargs))
                    else:
                        # If no loop is running, run in a new event loop
                        asyncio.run(self.callback(**kwargs))
                except RuntimeError:
                    # Handle case when there's no event loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.callback(**kwargs))
                    loop.close()
            else:
                # For sync callbacks, just call directly
                self.callback(**kwargs)
        except Exception as e:
            # Log the error but don't propagate it
            import traceback

            logging.error(f"Error in event handler {self.callback.__name__}: {e}")
            logging.debug(traceback.format_exc())


class NekoEventPipeline:
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
    ) -> int:
        """Emit an event to be processed by handlers.

        Args:
            event_type: Type of event
            path: Configuration path that changed
            old_value: Previous value
            new_value: New value
            config_data: Complete configuration data

        Returns:
            Number of handlers that processed the event
        """
        context = EventContext(event_type, path, old_value, new_value, config_data)

        count = 0

        for handler in self.handlers:

            if handler.matches(context):
                try:
                    handler.handle_sync(context)
                    count += 1
                except Exception as e:
                    self.logger.error(
                        f"Error in handler {handler.callback.__name__} for {event_type.value}: {e}"
                    )

        return count

    async def emit_async(
        self,
        event_type: EventType,
        path: Optional[str] = None,
        old_value: Any = None,
        new_value: Any = None,
        config_data: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Emit an event to be processed asynchronously by handlers.

        Args:
            event_type: Type of event
            path: Configuration path that changed
            old_value: Previous value
            new_value: New value
            config_data: Complete configuration data

        Returns:
            Number of handlers that processed the event
        """
        context = EventContext(event_type, path, old_value, new_value, config_data)

        count = 0
        tasks = []

        for handler in self.handlers:
            if handler.matches(context):
                try:
                    tasks.append(handler.handle_async(context))
                    count += 1
                except Exception as e:
                    self.logger.error(
                        f"Error in handler {handler.callback.__name__} for {event_type.value}: {e}"
                    )

        # Wait for all async handlers to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return count


def on_event(
    event_pipeline: NekoEventPipeline,
    event_type: Union[EventType, List[EventType]],
    path_pattern: Optional[str] = None,
    priority: int = 100,
):
    """Decorator to register a function as an event handler.

    Example:
        @on_event(pipeline, EventType.CHANGE, "database.connection")
        def handle_db_connection_change(old_value, new_value, **kwargs):
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


def on_change(event_pipeline: NekoEventPipeline, path_pattern: str, priority: int = 100):
    """Decorator to register a function as a change event handler.

    Example:
        @on_change(pipeline, "database.connection")
        def handle_db_connection_change(old_value, new_value, **kwargs):
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
