import threading
from typing import List, Callable
from graphql.pyutils import is_collection

from .sync_future import SyncFuture


class DataloaderBatchCallbacks:
    """
    Singleton that stores all the batched callbacks for all dataloaders. This is
    equivalent to the async `loop.call_soon` functionality and enables the
    batching functionality of dataloaders.

    Uses thread-local storage so that each thread (e.g., Django's threaded
    runserver) gets its own isolated callback list. Without this, concurrent
    threads share a single list, and one thread's dispatch loop can steal
    another's callbacks, leaving SyncFutures permanently PENDING.
    """

    def __init__(self) -> None:
        self._local = threading.local()

    @property
    def _callbacks(self) -> List[Callable]:
        try:
            return self._local.callbacks
        except AttributeError:
            self._local.callbacks = []
            return self._local.callbacks

    def add_callback(self, callback: Callable):
        self._callbacks.append(callback)

    def run_all_callbacks(self):
        callbacks = self._callbacks
        try:
            while callbacks:
                callbacks.pop(0)()
        except Exception:
            # A callback raised (e.g. a field completion error propagating out
            # of a dataloader dispatch). Drop any callbacks that were queued
            # behind it so they don't leak into the next operation on this
            # thread, then re-raise for the caller to handle.
            callbacks.clear()
            raise


dataloader_batch_callbacks = DataloaderBatchCallbacks()


class SyncDataLoader:
    def __init__(self, batch_load_fn):
        self._batch_load_fn = batch_load_fn
        self._cache = {}
        self._queue = []

    def load(self, key):
        try:
            return self._cache[key]
        except KeyError:
            future = SyncFuture()
            needs_dispatch = not self._queue
            self._queue.append((key, future))
            if needs_dispatch:
                dataloader_batch_callbacks.add_callback(self.dispatch_queue)
            self._cache[key] = future
            return future

    def clear(self, key):
        self._cache.pop(key, None)

    def dispatch_queue(self):
        queue = self._queue
        if not queue:
            return
        self._queue = []

        keys = [item[0] for item in queue]
        values = self._batch_load_fn(keys)
        if not is_collection(values) or len(keys) != len(values):
            raise ValueError("The batch loader does not return an expected result")

        for (_key, future), value in zip(queue, values):
            if future.done():
                # A previous future's completion cascade already resolved this
                # one (e.g. chained loads of the same key within this batch).
                continue
            if isinstance(value, Exception):
                future.set_exception(value)
            else:
                # set_result runs this future's completion callbacks
                # synchronously; if one raises (e.g. a non-null field error),
                # let it propagate rather than swallowing the real error.
                future.set_result(value)
