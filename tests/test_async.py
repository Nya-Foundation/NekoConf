"""Tests for asynchronous operations in NekoConf."""

import asyncio
import pytest

from nekoconf.utils import notify_observers
from tests.test_helpers import (
    create_failing_observer,
    create_async_failing_observer,
    wait_for_observers,
)


class TestAsyncOperations:
    """Tests for asynchronous operations."""

    @pytest.mark.asyncio
    async def test_observer_patterns(self, config_manager):
        """Test different observer notification patterns."""
        # Track observations
        sync_observed = []
        async_observed = []

        # Create observers
        async def async_observer(config_data):
            await asyncio.sleep(0.1)  # Simulate async work
            async_observed.append(config_data)

        def sync_observer(config_data):
            sync_observed.append(config_data)

        # Register both observers
        config_manager.register_observer(async_observer)
        config_manager.register_observer(sync_observer)

        # Make changes and check notifications
        config_manager.set("server.port", 9000)

        # Wait for async observer to complete
        await wait_for_observers()

        # Check both observers received the notification
        assert len(sync_observed) == 1
        assert sync_observed[0]["server"]["port"] == 9000

        assert len(async_observed) == 1
        assert async_observed[0]["server"]["port"] == 9000

    @pytest.mark.asyncio
    async def test_error_handling(self, config_manager):
        """Test that exceptions in observers are properly handled."""
        # Create failing observers
        failing_sync = create_failing_observer("Test sync error")
        failing_async = await create_async_failing_observer("Test async error")

        # Register failing observers
        config_manager.register_observer(failing_sync)
        config_manager.register_observer(failing_async)

        # This should not raise exceptions even though observers will fail
        config_manager.set("test.key", "value")

        # Wait for async operations
        await wait_for_observers()

        # No exception should have propagated to this point
        assert True

    @pytest.mark.asyncio
    async def test_notify_observers_utility(self):
        """Test the notify_observers utility function."""
        # Create test data
        config_data = {"test": "data"}

        # Create observers
        sync_called = False
        async_called = False

        def sync_observer(data):
            nonlocal sync_called
            sync_called = True
            assert data == config_data

        async def async_observer(data):
            nonlocal async_called
            async_called = True
            assert data == config_data

        # Test notification
        await notify_observers([sync_observer, async_observer], config_data)

        # Both observers should have been called
        assert sync_called
        assert async_called

        # Test with failing observer
        failing_observer = create_failing_observer()

        # This should not raise even though one observer fails
        await notify_observers([failing_observer, sync_observer], config_data)
