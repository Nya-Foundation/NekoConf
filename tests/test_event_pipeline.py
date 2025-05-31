"""Unit tests for the event pipeline functionality.

This module provides comprehensive test coverage for the NekoConf event pipeline system,
including synchronous and asynchronous event handling, event filtering, error handling,
and integration with the configuration management system.
"""

import asyncio
import os
import tempfile
from unittest.mock import Mock

import pytest

from nekoconf.core.config import NekoConf
from nekoconf.event.pipeline import (
    EventContext,
    EventHandler,
    EventPipeline,
    EventType,
)
from nekoconf.utils.helper import is_async_callable


class TestEventPipeline:
    """Test case for the event pipeline functionality.

    This test suite verifies that the event pipeline correctly handles:
    - Event registration and unregistration
    - Event filtering by type and path
    - Synchronous and asynchronous event handlers
    - Error handling in event handlers
    - Priority-based execution order
    - Event context propagation
    - Integration with configuration management
    """

    def setup_method(self):
        """Set up test environment before each test method.

        Creates a temporary configuration file and initializes the event pipeline
        and configuration manager for testing.
        """
        # Create a temporary file for configuration
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix=".yaml")
        with open(self.temp_path, "w") as f:
            f.write(
                """
                server:
                  host: localhost
                  port: 8000
                  debug: false
                logging:
                  level: INFO
                  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                database:
                  url: "sqlite:///test.db"
                  pool_size: 5
                """
            )
        self.config = NekoConf(self.temp_path)
        self.pipeline = EventPipeline()

    def teardown_method(self):
        """Clean up after each test method.

        Removes the temporary configuration file.
        """
        os.close(self.temp_fd)
        os.unlink(self.temp_path)

    def test_event_handler_registration_and_unregistration(self):
        """Test registering and unregistering event handlers.

        Verifies:
        1. Handler is correctly registered and receives matching events
        2. Handler doesn't receive non-matching events (wrong path or type)
        3. Unregistered handlers no longer receive events
        """
        # Setup a handler
        events_received = []

        def test_handler(path, new_value, **kwargs):
            events_received.append((path, new_value))

        # Register handler for change events
        handler = self.pipeline.register_handler(
            test_handler, [EventType.CHANGE], path_pattern="server.host"
        )

        # Emit event that should be caught (matching path and event type)
        self.pipeline.emit(EventType.CHANGE, path="server.host", new_value="0.0.0.0")

        # Emit event that should not be caught (different path)
        self.pipeline.emit(EventType.CHANGE, path="server.port", new_value=9000)

        # Emit event that should not be caught (different event type)
        self.pipeline.emit(EventType.DELETE, path="server.host")

        assert len(events_received) == 1
        assert events_received[0] == ("server.host", "0.0.0.0")

        # Unregister handler and ensure no more events are caught
        events_received.clear()
        self.pipeline.unregister_handler(handler)

        self.pipeline.emit(EventType.CHANGE, path="server.host", new_value="0.0.0.0")

        assert len(events_received) == 0

    def test_multiple_event_types(self):
        """Test handler registration for multiple event types.

        Verifies that a handler registered for multiple event types
        receives events of all those types, but not of unregistered types.
        """
        events_received = []

        def test_handler(event_type, path, **kwargs):
            events_received.append((event_type, path))

        # Register handler for multiple event types
        self.pipeline.register_handler(
            test_handler,
            [EventType.CHANGE, EventType.DELETE],
            path_pattern="server.host",
        )

        # Emit events of different types
        self.pipeline.emit(EventType.CHANGE, path="server.host", new_value="0.0.0.0")
        self.pipeline.emit(EventType.DELETE, path="server.host")
        self.pipeline.emit(EventType.CREATE, path="server.host", new_value="1.1.1.1")

        # Should only receive events for registered types
        assert len(events_received) == 2
        assert (EventType.CHANGE, "server.host") in events_received
        assert (EventType.DELETE, "server.host") in events_received
        # CREATE event should not be received
        assert not any(event[0] == EventType.CREATE for event in events_received)

    def test_path_pattern_matching(self):
        """Test different path pattern matching strategies.

        Verifies:
        1. Exact path matching
        2. Wildcard matching for all paths with a prefix
        3. Root-level wildcard matching all paths
        4. Parent path matching with trailing wildcard
        """
        events_received = []

        def test_handler(path, **kwargs):
            events_received.append(path)

        # Test exact path matching
        self.pipeline.register_handler(test_handler, EventType.CHANGE, path_pattern="server.host")

        # Test prefix wildcard matching
        self.pipeline.register_handler(test_handler, EventType.CHANGE, path_pattern="logging.*")

        # Test root-level wildcard matching
        self.pipeline.register_handler(test_handler, EventType.CREATE, path_pattern="*")

        # Emit events for different paths
        self.pipeline.emit(EventType.CHANGE, path="server.host", new_value="0.0.0.0")
        self.pipeline.emit(EventType.CHANGE, path="server.port", new_value=9000)
        self.pipeline.emit(EventType.CHANGE, path="logging.level", new_value="DEBUG")
        self.pipeline.emit(EventType.CHANGE, path="logging.format", new_value="simple")
        self.pipeline.emit(EventType.CREATE, path="new.path", new_value="value")

        # Check path matching results
        assert events_received.count("server.host") == 1  # Exact match
        assert events_received.count("server.port") == 0  # No match
        assert events_received.count("logging.level") == 1  # Wildcard match
        assert events_received.count("logging.format") == 1  # Wildcard match
        assert events_received.count("new.path") == 1  # Root wildcard match

    def test_parent_path_matching(self):
        """Test parent path matching behavior.

        Verifies that a handler registered for 'parent.*' receives events
        for both the parent path itself and its children.
        """
        events_received = []

        def test_handler(path, **kwargs):
            events_received.append(path)

        # Register handler for database.* patterns
        self.pipeline.register_handler(test_handler, EventType.CHANGE, path_pattern="database.*")

        # Emit events for parent and child paths
        self.pipeline.emit(EventType.CHANGE, path="database", new_value={"url": "new_url"})
        self.pipeline.emit(EventType.CHANGE, path="database.url", new_value="mysql://")
        self.pipeline.emit(EventType.CHANGE, path="database.pool_size", new_value=10)
        self.pipeline.emit(EventType.CHANGE, path="other.path", new_value="value")

        # Check parent path matching results
        assert events_received.count("database") == 1  # Parent path match
        assert events_received.count("database.url") == 1  # Child path match
        assert events_received.count("database.pool_size") == 1  # Child path match
        assert events_received.count("other.path") == 0  # No match

    def test_sync_calling_async_handler(self):
        """Test synchronous emit calling async handlers.

        Verifies that async handlers work correctly when called via the
        synchronous emit method, which should create or use an event loop.
        """
        events_received = []

        async def async_handler(path, new_value, **kwargs):
            await asyncio.sleep(0.01)  # Simulate async work
            events_received.append((path, new_value))

        # Register async handler
        self.pipeline.register_handler(async_handler, EventType.CHANGE, path_pattern="server.*")

        # Call async handler with sync emit
        self.pipeline.emit(EventType.CHANGE, path="server.host", new_value="0.0.0.0")

        # Check that async handler was called correctly
        assert len(events_received) == 1
        assert events_received[0] == ("server.host", "0.0.0.0")

    def test_priority_ordering(self):
        """Test that handlers are executed in priority order.

        Verifies that handlers with lower priority numbers are executed
        before handlers with higher priority numbers.
        """
        execution_order = []

        def handler_high_priority(**kwargs):
            execution_order.append("high")

        def handler_medium_priority(**kwargs):
            execution_order.append("medium")

        def handler_low_priority(**kwargs):
            execution_order.append("low")

        # Register handlers with different priorities
        self.pipeline.register_handler(handler_medium_priority, EventType.CHANGE, priority=50)
        self.pipeline.register_handler(handler_low_priority, EventType.CHANGE, priority=100)
        self.pipeline.register_handler(handler_high_priority, EventType.CHANGE, priority=1)

        # Emit event
        self.pipeline.emit(EventType.CHANGE)

        # Check execution order
        assert execution_order == ["high", "medium", "low"]

    def test_error_handling_in_sync_handlers(self):
        """Test error handling in synchronous handlers.

        Verifies:
        1. Errors in handlers are caught and logged
        2. Errors don't prevent other handlers from executing
        3. Error details are properly logged
        """
        executed_handlers = []

        def good_handler(**kwargs):
            executed_handlers.append("good")

        def bad_handler(**kwargs):
            executed_handlers.append("bad")
            raise ValueError("Simulated error in handler")

        def another_good_handler(**kwargs):
            executed_handlers.append("another_good")

        # Register handlers including one that raises an exception
        self.pipeline.register_handler(good_handler, EventType.CHANGE, priority=1)
        handler = self.pipeline.register_handler(bad_handler, EventType.CHANGE, priority=2)
        self.pipeline.register_handler(another_good_handler, EventType.CHANGE, priority=3)

        # Mock the logger
        mock_logger = Mock()
        handler.logger = mock_logger

        # Emit event which should trigger the error
        self.pipeline.emit(EventType.CHANGE)

        # Verify error was logged
        mock_logger.error.assert_called_once()
        error_message = mock_logger.error.call_args[0][0]
        assert "Error in event handler bad_handler" in error_message

        # All handlers should have executed despite the error
        assert executed_handlers == ["good", "bad", "another_good"]

    def test_event_context_propagation(self):
        """Test that event context is properly propagated to handlers.

        Verifies that all relevant fields of the event context (event_type,
        path, old_value, new_value, and config_data) are correctly passed
        to the handlers.
        """
        received_contexts = []

        def context_capture_handler(event_type, path, old_value, new_value, config_data, **kwargs):
            received_contexts.append(
                {
                    "event_type": event_type,
                    "path": path,
                    "old_value": old_value,
                    "new_value": new_value,
                    "config_data": config_data,
                }
            )

        # Register handler
        self.pipeline.register_handler(context_capture_handler, EventType.CHANGE)

        # Emit event with full context
        test_config_data = {"test": "data"}
        self.pipeline.emit(
            EventType.CHANGE,
            path="test.path",
            old_value="old",
            new_value="new",
            config_data=test_config_data,
        )

        # Check that context was received correctly
        assert len(received_contexts) == 1
        context = received_contexts[0]
        assert context["event_type"] == EventType.CHANGE
        assert context["path"] == "test.path"
        assert context["old_value"] == "old"
        assert context["new_value"] == "new"
        assert context["config_data"] == test_config_data

    def test_decorator_syntax(self):
        """Test the decorator syntax for event handlers.

        Verifies that handlers registered with the decorator syntax
        receive events correctly and with the proper context.
        """
        events_received = []

        # Create a config manager with event pipeline
        config = NekoConf(self.temp_path, event_emission_enabled=True)

        # Register handlers using decorator syntax
        @config.on_change("server.host")
        def handle_host_change(old_value, new_value, **kwargs):
            events_received.append(("host", old_value, new_value))

        @config.on_change("server.port")
        def handle_port_change(old_value, new_value, **kwargs):
            events_received.append(("port", old_value, new_value))

        # Change values to trigger the handlers
        config.set("server.host", "0.0.0.0")
        config.set("server.port", 9000)

        # Another change that shouldn't trigger handlers
        config.set("server.debug", True)

        # Check that handlers were called with correct parameters
        assert len(events_received) == 2
        assert ("host", "localhost", "0.0.0.0") in events_received
        assert ("port", 8000, 9000) in events_received

    @pytest.mark.asyncio
    async def test_async_decorator_syntax(self):
        """Test the decorator syntax for async event handlers.

        Verifies that async handlers registered with the decorator syntax
        receive events correctly and are properly awaited.
        """
        events_received = []

        # Create a config manager with event pipeline
        config = NekoConf(self.temp_path, event_emission_enabled=True)

        # Register async handler using decorator syntax
        @config.on_change("server.host")
        async def handle_host_change_async(old_value, new_value, **kwargs):
            await asyncio.sleep(0.01)
            events_received.append(("host", old_value, new_value))

        # Change a value and wait for the event to propagate asynchronously
        config.set("server.host", "0.0.0.0")

        # We need to give the async handler time to execute
        # This is a bit hacky but works for testing
        await asyncio.sleep(0.02)

        # Check that async handler was called with correct parameters
        assert len(events_received) == 1
        assert events_received[0] == ("host", "localhost", "0.0.0.0")

    def test_client_event_handlers(self):
        """Test event handlers with NekoConf.

        Verifies that the higher-level NekoConf correctly
        propagates events to registered handlers.
        """
        events_received = []

        # Create a client
        client = NekoConf(self.temp_path, event_emission_enabled=True)

        # Register handler using client's on_change
        @client.on_change("server.port")
        def handle_port_change(old_value, new_value, **kwargs):
            events_received.append((old_value, new_value))

        # Register handler for a specific event type
        @client.on_event(EventType.DELETE)
        def handle_delete(path, old_value, **kwargs):
            events_received.append(("DELETE", path, old_value))

        # Perform operations to trigger events
        client.set("server.port", 9000)
        client.delete("logging.level")

        # Check that handlers were called with correct parameters
        assert len(events_received) == 2
        assert (8000, 9000) in events_received  # From port change
        assert ("DELETE", "logging.level", "INFO") in events_received  # From delete

    def test_event_types_with_config_manager(self):
        """Test different event types with NekoConf.

        Verifies that all event types (CREATE, UPDATE, DELETE, RELOAD)
        are correctly emitted by the configuration manager.
        """
        events = []

        # Create a config manager
        config = NekoConf(self.temp_path, event_emission_enabled=True)

        # Register handlers for different event types
        @config.on_event(EventType.CREATE)
        def handle_create(path, new_value, **kwargs):
            events.append(("CREATE", path, new_value))

        @config.on_event(EventType.UPDATE)
        def handle_update(path, old_value, new_value, **kwargs):
            events.append(("UPDATE", path, old_value, new_value))

        @config.on_event(EventType.DELETE)
        def handle_delete(path, old_value, **kwargs):
            events.append(("DELETE", path, old_value))

        @config.on_event(EventType.RELOAD)
        def handle_reload(old_value, new_value, **kwargs):
            # For RELOAD, old_value and new_value contain the entire config
            events.append(("RELOAD", len(old_value), len(new_value)))

        # Perform operations to trigger events
        config.set("new.key", "value")  # CREATE
        config.set("server.host", "0.0.0.0")  # UPDATE
        config.delete("logging.level")  # DELETE
        config.load()  # RELOAD

        # Check events
        assert len(events) >= 4  # At least 4 events should be emitted

        print(events)  # For debugging purposes

        # Check for specific events
        assert any(e[0] == "CREATE" and e[1] == "new" and e[2] == {"key": "value"} for e in events)
        assert any(
            e[0] == "UPDATE" and e[1] == "server.host" and e[2] == "localhost" and e[3] == "0.0.0.0"
            for e in events
        )
        assert any(e[0] == "DELETE" and e[1] == "logging.level" for e in events)
        assert any(e[0] == "RELOAD" for e in events)

    def test_is_async_callable_detection(self):
        """Test that async callables are correctly detected.

        Verifies that the is_async_callable function correctly identifies
        different types of async and sync callables.
        """

        # Regular function
        def regular_func():
            pass

        # Async function
        async def async_func():
            pass

        # Class with __call__
        class CallableClass:
            def __call__(self):
                pass

        # Class with async __call__
        class AsyncCallableClass:
            async def __call__(self):
                pass

        # Lambda
        lambda_func = lambda: None

        # Verify detection
        assert not is_async_callable(regular_func)
        assert is_async_callable(async_func)
        assert not is_async_callable(CallableClass())
        assert is_async_callable(AsyncCallableClass())
        assert not is_async_callable(lambda_func)

    def test_event_handler_class(self):
        """Test the EventHandler class directly.

        Verifies:
        1. EventHandler correctly identifies async vs sync callables
        2. EventHandler matches events based on event type and path
        3. EventHandler gracefully handles errors in callbacks
        """
        # Create mock callback
        callback = Mock()

        # Create handler
        handler = EventHandler(
            callback=callback,
            event_types={EventType.CHANGE, EventType.UPDATE},
            path_pattern="test.path",
            priority=100,
        )

        # Test event matching
        matching_context = EventContext(EventType.CHANGE, "test.path")
        non_matching_type_context = EventContext(EventType.DELETE, "test.path")
        non_matching_path_context = EventContext(EventType.CHANGE, "other.path")

        assert handler.matches(matching_context)
        assert not handler.matches(non_matching_type_context)
        assert not handler.matches(non_matching_path_context)

        # Test handler execution
        handler.handle_event(matching_context)
        callback.assert_called_once()

        # Check callback arguments
        call_kwargs = callback.call_args[1]
        assert call_kwargs.get("event_type") == EventType.CHANGE
        assert call_kwargs.get("path") == "test.path"

    @pytest.mark.asyncio
    async def test_update_event_type(self):
        """Test the specific UPDATE event type behavior.

        Verifies that:
        1. UPDATE events are only emitted for existing keys
        2. UPDATE events include both old and new values
        """
        events = []

        # Create a config manager
        config = NekoConf(self.temp_path, event_emission_enabled=True)

        @config.on_event(EventType.UPDATE)
        def handle_update(event_type, path, old_value, new_value, config_data, **kwargs):
            events.append((path, old_value, new_value))

        # Set an existing value (should trigger UPDATE and CHANGE)
        config.set("server.port", 9000)

        # Set a new value (should trigger CREATE and CHANGE, not UPDATE)
        config.set("new.setting", "value")

        # Update the new value (now should trigger UPDATE)
        config.set("new.setting", "updated")

        # Check that UPDATE events have correct old and new values
        assert len(events) == 2
        assert ("server.port", 8000, 9000) in events
        assert ("new.setting", "value", "updated") in events

    @pytest.mark.asyncio
    async def test_reload_event_type(self):
        """Test the RELOAD event type with no configuration change.

        Verifies that:
        1. RELOAD events are emitted when loading from disk
        2. RELOAD events contain the old and new configuration
        """
        reload_events = []

        # Create a config manager
        config = NekoConf(self.temp_path, event_emission_enabled=True)

        @config.on_event(EventType.RELOAD)
        def handle_reload(old_value, new_value, **kwargs):
            reload_events.append((type(old_value), type(new_value)))

        # Load the configuration
        config.load()

        # Since the configuration hasn't changed, it should not emit a RELOAD event
        assert len(reload_events) == 1
        assert reload_events[0][0] == dict  # Old value is a dict
        assert reload_events[0][1] == dict  # New value is a dict
