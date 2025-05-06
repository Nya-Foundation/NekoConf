"""Tests for the LockManager utility.

This module contains test cases for testing the lock file management features.
"""

import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import TestCase, mock

import filelock
import pytest

from nekoconf.utils.lock import LockManager


def increment_file_number(path):
    import time

    from nekoconf.utils.lock import LockManager

    mgr = LockManager(path)
    with mgr:
        try:
            with open(path, "r") as f:
                content = f.read().strip()
                current = int(content) if content else 0
        except (FileNotFoundError, ValueError):
            current = 0
        time.sleep(0.01)
        with open(path, "w") as f:
            f.write(str(current + 1))
        return current + 1


class TestLockManager(TestCase):
    """Test cases for LockManager."""

    def setUp(self):
        """Set up a temporary file for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_file = Path(self.temp_dir.name) / "test_file.txt"
        self.test_content = "Hello, NekoConf!"

        # Create the test file with some content
        with open(self.test_file, "w") as f:
            f.write(self.test_content)

        # Create a lock manager for the test file
        self.lock_manager = LockManager(self.test_file)

    def tearDown(self):
        """Clean up temporary files."""
        self.lock_manager.cleanup()
        self.temp_dir.cleanup()

    def test_stale_lock_cleanup(self):
        """Test that stale lock files are cleaned up properly."""
        # Manually create a stale lock file
        lock_path = f"{self.test_file}.lock"
        with open(lock_path, "w") as f:
            f.write("")
        self.assertTrue(os.path.exists(lock_path))
        # Simulate process exit and cleanup
        LockManager.cleanup_stale_locks()
        self.assertFalse(os.path.exists(lock_path))

    def test_basic_lock_functionality(self):
        """Test the basic lock/unlock functionality."""
        # Acquire the lock
        with self.lock_manager:
            # Check the lock file exists
            lock_path = f"{self.test_file}.lock"
            self.assertTrue(os.path.exists(lock_path))
            self.assertTrue(self.lock_manager.is_locked)

            # Try to read the file while locked (should work)
            with open(self.test_file, "r") as f:
                content = f.read()
                self.assertEqual(content, self.test_content)

        # Lock should be released after the 'with' block
        self.assertFalse(self.lock_manager.is_locked)

    def test_explicit_acquire_release(self):
        """Test explicit lock acquisition and release."""
        # Explicitly acquire and release the lock
        self.lock_manager.acquire()
        self.assertTrue(self.lock_manager.is_locked)

        # Try to read the file while locked (should work)
        with open(self.test_file, "r") as f:
            content = f.read()
            self.assertEqual(content, self.test_content)

        # Explicitly release the lock
        self.lock_manager.release()
        self.assertFalse(self.lock_manager.is_locked)

    def test_lock_timeout(self):
        """Test that lock acquisition times out if another process holds it."""
        import multiprocessing
        import time

        def lock_file(path, wait):
            mgr = LockManager(path, timeout=5)
            mgr.acquire()
            time.sleep(wait)
            mgr.release()

        # Start a process that acquires the lock and holds it
        p = multiprocessing.Process(target=lock_file, args=(self.test_file, 1.5))
        p.start()
        time.sleep(0.2)  # Ensure the lock is acquired

        # Try to acquire with a short timeout, should raise Timeout
        short_timeout_manager = LockManager(self.test_file, timeout=0.3)
        with pytest.raises(filelock.Timeout):
            short_timeout_manager.acquire()
        p.join()
        short_timeout_manager.cleanup()

    def test_non_blocking_lock(self):
        """Test non-blocking lock acquisition (should fail if already locked by another process)."""
        import multiprocessing
        import time

        def lock_file(path, wait):
            mgr = LockManager(path, timeout=5)
            mgr.acquire()
            time.sleep(wait)
            mgr.release()

        p = multiprocessing.Process(target=lock_file, args=(self.test_file, 1.5))
        p.start()
        time.sleep(0.2)  # Ensure the lock is acquired

        another_manager = LockManager(self.test_file)
        with pytest.raises(filelock.Timeout):
            another_manager.acquire(blocking=False)
        p.join()
        another_manager.cleanup()

    def test_cleanup_removes_lock_file(self):
        """Test that cleanup removes the lock file."""
        # Acquire the lock
        self.lock_manager.acquire()

        # Check the lock file exists
        lock_path = f"{self.test_file}.lock"
        self.assertTrue(os.path.exists(lock_path))

        # Clean up
        self.lock_manager.cleanup()

        # Check the lock file is removed
        self.assertFalse(os.path.exists(lock_path))

        # Check the lock is released
        self.assertFalse(self.lock_manager.is_locked)

    def test_multiple_managers_same_file(self):
        """Test that multiple lock managers for the same file work correctly."""
        # Create another manager for the same file
        another_manager = LockManager(self.test_file)

        # Acquire with the first manager
        with self.lock_manager:
            # Try to acquire with the second manager, should block
            # We'll use a thread to test this
            result = {"acquired": False}

            def try_acquire():
                try:
                    with another_manager:
                        result["acquired"] = True
                except Exception:
                    pass

            thread = threading.Thread(target=try_acquire)
            thread.start()

            # Give the thread a moment to try to acquire
            time.sleep(0.1)

            # The thread should be waiting, not having acquired the lock
            self.assertFalse(result["acquired"])

        # Now that the first lock is released, wait for the thread to complete
        thread.join(timeout=1.0)

        # The thread should have acquired the lock
        self.assertTrue(result["acquired"])

        # Clean up
        another_manager.cleanup()

    def test_concurrent_access(self):
        """Test concurrent access patterns using multiple processes."""
        import multiprocessing

        file_path = Path(self.temp_dir.name) / "concurrent_test.txt"

        # Initialize file
        with open(file_path, "w") as f:
            f.write("0")

        num_operations = 20
        with multiprocessing.Pool(5) as pool:
            pool.map(increment_file_number, [file_path] * num_operations)

        with open(file_path, "r") as f:
            final_value = int(f.read().strip())

        self.assertEqual(final_value, num_operations)

    @mock.patch("os.unlink")
    def test_cleanup_error_handling(self, mock_unlink):
        """Test that cleanup handles errors gracefully."""
        # Make os.unlink raise an exception
        mock_unlink.side_effect = OSError("Permission denied")

        # Acquire the lock
        self.lock_manager.acquire()

        # Cleanup should not raise an exception
        try:
            self.lock_manager.cleanup()
        except Exception as e:
            self.fail(f"cleanup() raised an exception: {e}")

        # Mock should have been called
        mock_unlink.assert_called()

    def test_custom_lock_suffix(self):
        """Test using a custom lock suffix."""
        custom_suffix = ".customlock"
        custom_manager = LockManager(self.test_file, lock_suffix=custom_suffix)

        # Acquire the lock
        custom_manager.acquire()

        # Check the lock file exists with custom suffix
        lock_path = f"{self.test_file}{custom_suffix}"
        self.assertTrue(os.path.exists(lock_path))

        # Clean up
        custom_manager.cleanup()

        # Check the lock file is removed
        self.assertFalse(os.path.exists(lock_path))

    def test_is_locked_property(self):
        """Test the is_locked property."""
        # Initially not locked
        self.assertFalse(self.lock_manager.is_locked)

        # Acquire the lock
        self.lock_manager.acquire()
        self.assertTrue(self.lock_manager.is_locked)

        # Release the lock
        self.lock_manager.release()
        self.assertFalse(self.lock_manager.is_locked)


if __name__ == "__main__":
    pytest.main()
