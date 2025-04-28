"""Tests for asynchronous operations in NekoConf."""

import asyncio

import pytest

from nekoconf.core.config import NekoConfigManager
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

        # Create observers (accepting config_data explicitly)
        async def async_observer(config_data, **kwargs):
            await asyncio.sleep(0.1)  # Simulate async work
            async_observed.append(config_data)

        def sync_observer(config_data, **kwargs):
            sync_observed.append(config_data)

        # Register both observers
        config_manager.register_observer(async_observer)
        config_manager.register_observer(sync_observer)

        # Make changes and check notifications
        config_manager.set("server.port", 9000)
        config_manager.save()

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
        config_manager.save()

        # Wait for async operations
        await wait_for_observers()

        # No exception should have propagated to this point
        assert True

    @pytest.mark.asyncio
    async def test_observer_notification_directly(self, tmp_path):
        """Test the observer notification in NekoConfigManager directly."""
        # Create a config manager instance for testing
        config_path = tmp_path / "test_config.yaml"
        config_manager = NekoConfigManager(config_path=config_path)

        # Test data
        config_data = {"test": "data"}
        config_manager.data = config_data

        # Create observers
        sync_called = False
        async_called = False

        # Update sync_observer to accept config_data as keyword arg
        def sync_observer(config_data, **kwargs):
            nonlocal sync_called
            sync_called = True
            assert config_data == config_manager.data  # Check against manager's data

        async def async_observer(config_data, **kwargs):
            nonlocal async_called
            async_called = True
            assert config_data == config_manager.data  # Check against manager's data

        # Register observers
        config_manager.register_observer(sync_observer)
        config_manager.register_observer(async_observer)

        # Manually trigger notification and capture futures
        futures = config_manager._notify_observers()

        # Wait for any scheduled async observers to complete
        if futures:
            await asyncio.gather(*futures)

        # Both observers should have been called
        assert sync_called
        assert async_called

    @pytest.mark.asyncio
    async def test_observers_with_none_value(self, tmp_path):
        """Test observers with None as an observer."""
        # Create a config manager
        config_path = tmp_path / "test_config.yaml"
        config_manager = NekoConfigManager(config_path=config_path)

        # This test is tricky as the NekoConfigManager won't let you register None
        # Instead, we can test the error handling for observers that return None
        results = []

        # Observer accepting config_data
        def valid_observer(config_data, **kwargs):
            results.append("called")

        # Register valid observer
        config_manager.register_observer(valid_observer)

        # Try to register None (this should be handled or fail gracefully)
        with pytest.raises(Exception) as excinfo:
            config_manager.register_observer(None)

        # The error message should mention callable or NoneType
        assert "callable" in str(excinfo.value).lower() or "none" in str(excinfo.value).lower()

        # The valid observer should still work
        config_manager.set("test.key", "value")
        config_manager.save()  # <-- Added save() call
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_observers_with_invalid_callable(self, tmp_path):
        """Test observers with invalid callables."""
        # Create a config manager
        config_path = tmp_path / "test_config.yaml"
        config_manager = NekoConfigManager(config_path=config_path)

        # Test with non-callable object
        invalid_observer = "not_a_function"

        with pytest.raises(Exception) as excinfo:
            config_manager.register_observer(invalid_observer)

        # Error should mention callable
        assert "callable" in str(excinfo.value).lower() or "str" in str(excinfo.value).lower()

    @pytest.mark.asyncio
    async def test_observers_with_wrong_signature(self, tmp_path):
        """Test observers with observer that has wrong signature."""
        # Create a config manager
        config_path = tmp_path / "test_config.yaml"
        config_manager = NekoConfigManager(config_path=config_path)

        # Observer with no parameters
        def no_param_observer():
            pass

        # Observer with too many required parameters
        def too_many_params_observer(data, extra_param):
            pass

        # Register and test observers with wrong signatures
        config_manager.register_observer(no_param_observer)
        config_manager.register_observer(too_many_params_observer)

        # The errors should be caught in _notify_observers without crashing the app
        config_manager.set("test.key", "value")

        # No exception should have propagated to this point
        assert True

    @pytest.mark.asyncio
    async def test_observers_execution_order(self, tmp_path):
        """Test that observers are executed in registration order for sync observers."""
        # Create a config manager
        config_path = tmp_path / "test_config.yaml"
        config_manager = NekoConfigManager(config_path=config_path)

        execution_order = []

        # Observers accepting config_data
        def observer1(config_data, **kwargs):
            execution_order.append(1)

        def observer2(config_data, **kwargs):
            execution_order.append(2)

        def observer3(config_data, **kwargs):
            execution_order.append(3)

        # Register in specific order
        config_manager.register_observer(observer1)
        config_manager.register_observer(observer2)
        config_manager.register_observer(observer3)

        # Trigger notification by setting and saving
        config_manager.set("test.key", "value")
        config_manager.save()  # <-- Added save() call

        # Sync observers should execute in the order they were registered
        assert execution_order == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_observers_continue_after_error(self, tmp_path):
        """Test that observer errors don't prevent other observers from being called."""
        # Create a config manager
        config_path = tmp_path / "test_config.yaml"
        config_manager = NekoConfigManager(config_path=config_path)

        called = []

        # Observers accepting config_data
        def good_observer1(config_data, **kwargs):
            called.append("good1")

        def failing_observer(config_data, **kwargs):
            called.append("failing")
            raise ValueError("Deliberate test failure")

        def good_observer2(config_data, **kwargs):
            called.append("good2")

        # Register observers
        config_manager.register_observer(good_observer1)
        config_manager.register_observer(failing_observer)
        config_manager.register_observer(good_observer2)

        # This should not raise as NekoConfigManager catches observer exceptions
        config_manager.set("test.key", "value")
        config_manager.save()  # <-- Added save() call

        # All observers should be called, even after failure
        assert called == ["good1", "failing", "good2"]
