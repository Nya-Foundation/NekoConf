"""Lock file management for file access synchronization.

This module provides a simple, reliable way to manage lock files
for synchronizing access to shared resources across processes.
"""

import atexit
import os
import signal
import threading
from pathlib import Path
from typing import Set

import filelock

# Default timeout for acquiring locks (in seconds)
DEFAULT_TIMEOUT = 1.0

# Thread/process-safe set for active locks
_active_locks: Set[str] = set()
_active_locks_lock = threading.Lock()

# Thread local storage to track lock acquisition counts per thread
_thread_local = threading.local()


def _add_active_lock(lock_path: str):
    with _active_locks_lock:
        _active_locks.add(lock_path)


def _remove_active_lock(lock_path: str):
    with _active_locks_lock:
        _active_locks.discard(lock_path)


def _list_active_locks():
    with _active_locks_lock:
        return list(_active_locks)


class LockManager:
    """Manages lock files for synchronizing access to files across processes and threads."""

    def __init__(
        self,
        resource_path: Path,
        timeout: float = DEFAULT_TIMEOUT,
        lock_suffix: str = ".lock",
    ):
        self.resource_path = Path(resource_path)
        self.lock_path = f"{self.resource_path}{lock_suffix}"
        self.timeout = timeout
        self._file_lock = filelock.FileLock(self.lock_path, timeout=self.timeout)
        self._local_lock = threading.RLock()
        _add_active_lock(self.lock_path)
        _ensure_signal_handlers()

    @property
    def _lock_count(self) -> int:
        if not hasattr(_thread_local, "lock_counts"):
            _thread_local.lock_counts = {}
        return _thread_local.lock_counts.get(self.lock_path, 0)

    @_lock_count.setter
    def _lock_count(self, value: int) -> None:
        if not hasattr(_thread_local, "lock_counts"):
            _thread_local.lock_counts = {}
        _thread_local.lock_counts[self.lock_path] = value

    def __enter__(self):
        with self._local_lock:
            if self._lock_count == 0:
                self._file_lock.acquire()
            self._lock_count += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        with self._local_lock:
            self._lock_count -= 1
            if self._lock_count == 0:
                self._file_lock.release()
        return False

    def acquire(self, blocking: bool = True):
        with self._local_lock:
            if self._lock_count > 0:
                self._lock_count += 1
                return self._file_lock
            if not blocking:
                orig_timeout = self._file_lock.timeout
                self._file_lock.timeout = 0.01
                try:
                    self._file_lock.acquire()
                    self._lock_count += 1
                finally:
                    self._file_lock.timeout = orig_timeout
            else:
                self._file_lock.acquire()
                self._lock_count += 1
            return self._file_lock

    def release(self):
        with self._local_lock:
            if self._lock_count > 0:
                self._lock_count -= 1
                if self._lock_count == 0 and self._file_lock.is_locked:
                    self._file_lock.release()

    def cleanup(self):
        with self._local_lock:
            if self._file_lock.is_locked:
                self._file_lock.release()
            self._lock_count = 0
            _remove_active_lock(self.lock_path)
            try:
                if os.path.exists(self.lock_path):
                    os.unlink(self.lock_path)
            except Exception:
                pass

    @property
    def is_locked(self) -> bool:
        return self._file_lock.is_locked

    @property
    def is_held(self) -> bool:
        return self._lock_count > 0

    @staticmethod
    def cleanup_stale_locks():
        """Check and remove stale lock files left by dead processes."""
        for lock_path in _list_active_locks():
            try:
                lock = filelock.FileLock(lock_path)
                if not lock.is_locked and os.path.exists(lock_path):
                    os.unlink(lock_path)
                    _remove_active_lock(lock_path)
            except Exception:
                pass


# --- Module level functions for global lock management ---
def _cleanup_locks():
    for lock_path in _list_active_locks():
        try:
            if os.path.exists(lock_path):
                os.unlink(lock_path)
            _remove_active_lock(lock_path)
        except Exception:
            pass


atexit.register(_cleanup_locks)


def _signal_handler(sig, frame):
    _cleanup_locks()
    signal.signal(sig, signal.SIG_DFL)
    os.kill(os.getpid(), sig)


def _ensure_signal_handlers():
    if not hasattr(_ensure_signal_handlers, "initialized"):
        try:
            signal.signal(signal.SIGINT, _signal_handler)
            signal.signal(signal.SIGTERM, _signal_handler)
        except Exception:
            pass
        _ensure_signal_handlers.initialized = True
