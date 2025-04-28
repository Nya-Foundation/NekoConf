"""Tests for asynchronous operations in NekoConf."""

import asyncio

import pytest

from nekoconf.core.utils import notify_observers
from tests.test_helpers import (
    create_async_failing_observer,
    create_failing_observer,
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

        # Call notify_observers with both sync and async observers
        observers = [sync_observer, async_observer]
        await notify_observers(observers, config_data)

        # Both observers should have been called
        assert sync_called
        assert async_called

    @pytest.mark.asyncio
    async def test_notify_observers_with_none_value(self):
        """Test notify_observers with None as an observer."""
        config_data = {"test": "data"}
        results = []

        def valid_observer(data):
            results.append("called")

        # Mix with None value
        observers = [valid_observer, None, valid_observer]

        # Should skip None values without errors
        with pytest.raises(RuntimeError) as excinfo:
            await notify_observers(observers, config_data)

        assert "NoneType" in str(excinfo.value) or "not callable" in str(excinfo.value)
        assert len(results) == 1  # First observer was called before the error

    @pytest.mark.asyncio
    async def test_notify_observers_with_invalid_callable(self):
        """Test notify_observers with invalid callables."""
        config_data = {"test": "data"}

        # Test with non-callable object
        invalid_observer = "not_a_function"

        with pytest.raises(RuntimeError) as excinfo:
            await notify_observers([invalid_observer], config_data)

        assert "not callable" in str(excinfo.value).lower() or "str" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_notify_observers_with_wrong_signature(self):
        """Test notify_observers with observer that has wrong signature."""
        config_data = {"test": "data"}

        # Observer with no parameters
        def no_param_observer():
            pass

        # Observer with too many parameters
        def too_many_params_observer(data, extra_param):
            pass

        # Test with wrong signature observers
        with pytest.raises(RuntimeError) as excinfo:
            await notify_observers([no_param_observer], config_data)

        # Check if the error message contains appropriate text about argument/parameters
        assert "takes 0 positional arguments but 1 was given" in str(excinfo.value)

        with pytest.raises(RuntimeError) as excinfo:
            await notify_observers([too_many_params_observer], config_data)

        # Check if the error message contains appropriate text about argument/parameters
        assert "missing" in str(excinfo.value).lower() or "argument" in str(excinfo.value).lower()

    @pytest.mark.asyncio
    async def test_notify_observers_execution_order(self):
        """Test that notify_observers preserves execution order for sync observers."""
        config_data = {"test": "data"}
        execution_order = []

        def observer1(data):
            execution_order.append(1)

        def observer2(data):
            execution_order.append(2)

        def observer3(data):
            execution_order.append(3)

        # Notify in specific order
        await notify_observers([observer1, observer2, observer3], config_data)

        # Sync observers should execute in the order they were provided
        assert execution_order == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_notify_observers_continue_after_error(self):
        """Test that notify_observers stops on first error and doesn't call remaining observers."""
        config_data = {"test": "data"}
        called = []

        def good_observer1(data):
            called.append("good1")

        def failing_observer(data):
            called.append("failing")
            raise ValueError("Deliberate test failure")

        def good_observer2(data):
            called.append("good2")

        # This should raise on the failing observer
        with pytest.raises(RuntimeError):
            await notify_observers([good_observer1, failing_observer, good_observer2], config_data)

        # Should have called first observer and failing observer, but not the last
        assert called == ["good1", "failing"]
        assert "good2" not in called
