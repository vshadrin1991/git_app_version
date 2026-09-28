"""Run git work off the UI thread and get the result back on it."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(object)


class _Job(QRunnable):
    def __init__(self, fn: Callable[[], Any], signals: _Signals) -> None:
        super().__init__()
        self._fn = fn
        self._signals = signals

    def run(self) -> None:  # runs on a pool thread
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001 - every failure is reported to the UI
            self._signals.failed.emit(exc)
        else:
            self._signals.done.emit(result)


class _Dispatcher(QObject):
    """Lives on the UI thread, so Qt queues the job's signals to it and the callbacks run there."""

    def __init__(self, on_done: Callable[[Any], None], on_failed: Callable[[Exception], None]) -> None:
        super().__init__()
        self.signals = _Signals()
        self.signals.done.connect(self._done)
        self.signals.failed.connect(self._failed)
        self._on_done = on_done
        self._on_failed = on_failed

    def _done(self, result: Any) -> None:
        _pending.discard(self)
        self._on_done(result)

    def _failed(self, exc: Exception) -> None:
        _pending.discard(self)
        self._on_failed(exc)


_pending: set[_Dispatcher] = set()  # keeps each dispatcher alive until its job reports back


def run_in_background(
    fn: Callable[[], Any],
    on_done: Callable[[Any], None],
    on_failed: Callable[[Exception], None],
) -> None:
    """Call fn() on the thread pool, then on_done(result) or on_failed(exception) on the UI thread."""
    dispatcher = _Dispatcher(on_done, on_failed)
    _pending.add(dispatcher)
    QThreadPool.globalInstance().start(_Job(fn, dispatcher.signals))
