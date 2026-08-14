import logging
from typing import Any, Callable, Dict, List
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import time

from .base_provider import ProviderEventBus, ProviderEvent, ProviderEventChannel

_logger = logging.getLogger(__name__)

class OdooProviderEventBus(ProviderEventBus):
    """
    Asynchronous event bus for the Unified Provider Platform.
    Uses ThreadPoolExecutor for non-blocking publishing (≤1ms return).
    """

    def __init__(self, max_workers: int = 5):
        self._subscribers: Dict[ProviderEventChannel, List[Callable[[ProviderEvent], None]]] = {
            channel: [] for channel in ProviderEventChannel
        }
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ProviderEventBus")
        self._active_tasks = []

    def publish(self, event: ProviderEvent) -> None:
        """
        Publish an event to a channel asynchronously.
        Returns immediately without blocking the caller.
        """
        with self._lock:
            subscribers = self._subscribers.get(event.channel, []).copy()

        if not subscribers:
            return

        def _dispatch():
            for callback in subscribers:
                try:
                    callback(event)
                except Exception as e:
                    _logger.error(f"Event subscriber on channel {event.channel.value} raised an error: {e}", exc_info=True)

        task = self._executor.submit(_dispatch)
        
        # Cleanup completed tasks to avoid memory leaks
        self._active_tasks = [t for t in self._active_tasks if not t.done()]
        self._active_tasks.append(task)

    def subscribe(self, channel: ProviderEventChannel, callback: Callable[[ProviderEvent], None]) -> None:
        """
        Subscribe a callback function to a specific event channel.
        """
        with self._lock:
            if channel not in self._subscribers:
                self._subscribers[channel] = []
            if callback not in self._subscribers[channel]:
                self._subscribers[channel].append(callback)

    def drain(self, timeout_ms: int = 5000) -> None:
        """
        Wait for all pending events in the thread pool to finish dispatching.
        Primarily used for testing synchronization.
        """
        start_time = time.time()
        timeout_seconds = timeout_ms / 1000.0

        while self._active_tasks:
            # Re-evaluate which tasks are done
            self._active_tasks = [t for t in self._active_tasks if not t.done()]
            if not self._active_tasks:
                break
            
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                _logger.warning(f"ProviderEventBus.drain() timed out after {timeout_ms}ms with {len(self._active_tasks)} pending tasks.")
                break
                
            time.sleep(0.01)

    def shutdown(self):
        """Shut down the thread pool."""
        self._executor.shutdown(wait=True)
