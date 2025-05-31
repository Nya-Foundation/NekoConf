"""Test cases for the event handling system."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from nekoconf.event.handler import EventContext, EventHandler
from nekoconf.event.pipeline import EventPipeline
from nekoconf.event.type import EventType


class TestEventContext:
    """Test cases for EventContext functionality."""

    def test_event_context_initialization(self):
        """Test EventContext initialization."""
        event_context = EventContext(
            event_type=EventType.UPDATE,
            path="database.host",
            old_value="localhost",
            new_value="db.example.com",
            config_data={"database": {"host": "db.example.com"}},
        )

        assert event_context.event_type == EventType.UPDATE
        assert event_context.path == "database.host"
        assert event_context.old_value == "localhost"
        assert event_context.new_value == "db.example.com"
        assert event_context.config_data == {"database": {"host": "db.example.com"}}


class TestEventHandler:
    """Test cases for EventHandler functionality."""

    def test_event_handler_initialization(self):
        """Test EventHandler initialization."""
        callback = MagicMock()
        callback.__name__ = "mock_callback"  # Add __name__ attribute to mock

        handler = EventHandler(
            callback=callback,
            event_types={EventType.UPDATE, EventType.CREATE},
            path_pattern="database.*",
            priority=50,
            custom_param="test",
        )

        assert handler.callback == callback
        assert handler.event_types == {EventType.UPDATE, EventType.CREATE}
        assert handler.path_pattern == "database.*"
        assert handler.priority == 50
        assert handler.kwargs == {"custom_param": "test"}
        assert handler.is_async is False

    def test_handler_matches_event_type(self):
        """Test handler matching by event type."""

        def mock_callback():
            pass

        handler = EventHandler(
            mock_callback,
            {EventType.UPDATE},
            "database.host",
        )

        # Matching event type and path
        context = EventContext(EventType.UPDATE, "database.host")
        assert handler.matches(context) is True

        # Matching path but non-matching event type
        context = EventContext(EventType.DELETE, "database.host")
        assert handler.matches(context) is False

    def test_handler_matches_path_pattern(self):
        """Test handler matching by path pattern."""

        def mock_callback():
            pass

        handler = EventHandler(mock_callback, {EventType.UPDATE}, "database.*")

        # Matching event type and path pattern
        context = EventContext(EventType.UPDATE, "database.host")
        assert handler.matches(context) is True
        context = EventContext(EventType.UPDATE, "database.port")
        assert handler.matches(context) is True

        # Non-matching path pattern
        context = EventContext(EventType.UPDATE, "logging.level")
        assert handler.matches(context) is False

    def test_handler_global_match(self):
        """Test global handlers that match everything."""

        def mock_callback():
            pass

        handler = EventHandler(mock_callback, {EventType.UPDATE}, "*")  # Global pattern

        # Should match any path for the specified event type
        context = EventContext(EventType.UPDATE, "database.host")
        assert handler.matches(context) is True
        context = EventContext(EventType.UPDATE, "logging.level")
        assert handler.matches(context) is True

        # But not other event types
        context = EventContext(EventType.DELETE, "database.host")
        assert handler.matches(context) is False

    def test_handler_handle_event_sync(self):
        """Test handling events with a synchronous callback."""
        mock_callback = MagicMock()
        mock_callback.__name__ = "mock_callback"  # Add __name__ attribute
        handler = EventHandler(mock_callback, {EventType.UPDATE}, custom_param="test")

        context = EventContext(
            event_type=EventType.UPDATE,
            path="database.host",
            old_value="localhost",
            new_value="db.example.com",
            config_data={"database": {"host": "db.example.com"}},
        )

        handler.handle_event(context)

        # Callback should be called with the right parameters
        mock_callback.assert_called_once()
        args = mock_callback.call_args[1]
        assert args["event_type"] == EventType.UPDATE
        assert args["path"] == "database.host"
        assert args["old_value"] == "localhost"
        assert args["new_value"] == "db.example.com"
        assert args["config_data"] == {"database": {"host": "db.example.com"}}
        assert args["custom_param"] == "test"

    @pytest.mark.asyncio
    def test_handler_is_async(self):
        """Test that is_async is correctly determined based on the callback type."""

        async def mock_async_callback():
            pass

        handler = EventHandler(mock_async_callback, {EventType.UPDATE})

        assert handler.is_async is True, "Handler should be async based on the callback type"

    @pytest.mark.asyncio
    async def test_handler_handle_event_async(self):
        """Test handling events with an async callback."""

        # Use a real async function instead of AsyncMock for better compatibility
        async def mock_async_callback(**kwargs):
            # Store the call arguments for verification
            mock_async_callback.call_args = kwargs
            mock_async_callback.call_count = getattr(mock_async_callback, "call_count", 0) + 1

        mock_async_callback.call_count = 0
        mock_async_callback.call_args = None
        mock_async_callback.__name__ = "mock_async_callback"

        handler = EventHandler(mock_async_callback, {EventType.UPDATE}, custom_param="test")

        # Should be detected as async
        assert handler.is_async is True

        context = EventContext(
            event_type=EventType.UPDATE,
            path="database.host",
            old_value="localhost",
            new_value="db.example.com",
            config_data={"database": {"host": "db.example.com"}},
        )

        # Test async handling
        await handler.handle_async(context)

        # Callback should be called with the right parameters
        assert mock_async_callback.call_count == 1
        args = mock_async_callback.call_args
        assert args["event_type"] == EventType.UPDATE
        assert args["path"] == "database.host"
        assert args["custom_param"] == "test"

    @pytest.mark.asyncio
    async def test_handler_asyncmock_compatibility(self):
        """Test AsyncMock compatibility across Python versions."""
        import sys

        # Only test AsyncMock on Python 3.10+ where it's more reliable
        if sys.version_info >= (3, 10):
            mock_callback = AsyncMock()
            mock_callback.__name__ = "mock_async_callback"
            handler = EventHandler(mock_callback, {EventType.UPDATE}, custom_param="test")

            # Should be detected as async in Python 3.10+
            assert handler.is_async is True

            context = EventContext(
                event_type=EventType.UPDATE,
                path="database.host",
                old_value="localhost",
                new_value="db.example.com",
                config_data={"database": {"host": "db.example.com"}},
            )

            # Test async handling
            await handler.handle_async(context)

            # Callback should be called with the right parameters
            mock_callback.assert_called_once()
            args = mock_callback.call_args[1]
            assert args["event_type"] == EventType.UPDATE
            assert args["path"] == "database.host"
            assert args["custom_param"] == "test"
        else:
            # For Python 3.9, skip this test or use alternative approach
            pytest.skip("AsyncMock detection unreliable in Python 3.9")


class TestEventPipeline:
    """Test cases for EventPipeline functionality."""

    def test_pipeline_initialization(self):
        """Test event pipeline initialization."""
        pipeline = EventPipeline()
        assert pipeline.handlers == []

    def test_register_handler(self):
        """Test registering handlers in the pipeline."""
        pipeline = EventPipeline()
        mock_callback = MagicMock()
        mock_callback.__name__ = "mock_callback"  # Add __name__ attribute

        # Register a single handler
        handler1 = pipeline.register_handler(
            mock_callback, EventType.UPDATE, "database.*", priority=100
        )

        assert len(pipeline.handlers) == 1
        assert pipeline.handlers[0] == handler1
        assert handler1.callback == mock_callback
        assert handler1.event_types == {EventType.UPDATE}
        assert handler1.path_pattern == "database.*"

        # Register another handler with higher priority
        handler2 = pipeline.register_handler(
            mock_callback, [EventType.CREATE, EventType.DELETE], priority=50
        )

        assert len(pipeline.handlers) == 2
        # Handlers should be sorted by priority (lower number = higher priority)
        assert pipeline.handlers == [handler2, handler1]

    def test_unregister_handler(self):
        """Test unregistering handlers from the pipeline."""
        pipeline = EventPipeline()
        mock_callback = MagicMock()
        mock_callback.__name__ = "mock_callback"  # Add __name__ attribute

        # Register handlers
        handler1 = pipeline.register_handler(mock_callback, EventType.UPDATE)
        handler2 = pipeline.register_handler(mock_callback, EventType.CREATE)

        assert len(pipeline.handlers) == 2

        # Unregister one handler
        result = pipeline.unregister_handler(handler1)
        assert result is True
        assert len(pipeline.handlers) == 1
        assert pipeline.handlers[0] == handler2

        # Try to unregister a non-existent handler
        result = pipeline.unregister_handler(handler1)
        assert result is False
        assert len(pipeline.handlers) == 1

    def test_emit_event(self):
        """Test emitting events through the pipeline."""
        pipeline = EventPipeline()

        # Create callbacks for different event types and paths
        callback1 = MagicMock()
        callback1.__name__ = "callback1"
        callback2 = MagicMock()
        callback2.__name__ = "callback2"
        callback3 = MagicMock()
        callback3.__name__ = "callback3"

        # Register handlers
        pipeline.register_handler(callback1, EventType.UPDATE, "database.*")
        pipeline.register_handler(callback2, EventType.UPDATE, "logging.*")
        pipeline.register_handler(callback3, EventType.CREATE)

        # Emit an event that should match callback1 only
        count = pipeline.emit(
            EventType.UPDATE,
            "database.host",
            old_value="localhost",
            new_value="db.example.com",
            config_data={"database": {"host": "db.example.com"}},
        )

        assert count == 1
        callback1.assert_called_once()
        callback2.assert_not_called()
        callback3.assert_not_called()

        # Reset mocks
        callback1.reset_mock()

        # Emit an event that matches multiple handlers
        count = pipeline.emit(
            EventType.CREATE,
            "database.port",
            old_value=None,
            new_value=5432,
            config_data={"database": {"port": 5432}},
        )

        # Both callback1 (matches path) and callback3 (matches event type) should be called
        assert count == 1  # Only callback3 matches
        callback1.assert_not_called()  # Only handles UPDATE events
        callback2.assert_not_called()
        callback3.assert_called_once()

    def test_emit_with_ignore(self):
        """Test ignoring events with the ignore flag."""
        pipeline = EventPipeline()
        callback = MagicMock()
        callback.__name__ = "mock_callback"  # Add __name__ attribute

        pipeline.register_handler(callback, EventType.UPDATE)

        # Emit an event with ignore=True
        count = pipeline.emit(
            EventType.UPDATE,
            "database.host",
            old_value="localhost",
            new_value="db.example.com",
            ignore=True,
        )

        assert count == 0
        callback.assert_not_called()

    def test_handler_exception_handling(self):
        """Test that exceptions in handlers are caught and don't affect other handlers."""
        pipeline = EventPipeline()

        # Create handlers: one that works and one that raises an exception
        def raising_handler(**kwargs):
            raise ValueError("Intentional error for testing")

        normal_handler = MagicMock()
        normal_handler.__name__ = "normal_handler"  # Add __name__ attribute

        # Register handlers with different priorities
        pipeline.register_handler(raising_handler, EventType.UPDATE, "database.*", priority=10)
        pipeline.register_handler(normal_handler, EventType.UPDATE, "database.*", priority=20)

        # Emit an event that triggers both handlers
        count = pipeline.emit(EventType.UPDATE, "database.host")

        # The normal handler should still be called, despite the exception in the first handler
        assert count == 2  # Only one handler succeeded
        normal_handler.assert_called_once()
