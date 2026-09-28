from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from git_version_tagger.ui.worker import run_in_background


def test_result_is_delivered_on_the_ui_thread(qtbot):
    results, threads = [], []

    def on_done(value):
        results.append(value)
        threads.append(QThread.currentThread())

    run_in_background(lambda: 42, on_done, lambda exc: None)
    qtbot.waitUntil(lambda: results == [42])
    assert threads == [QApplication.instance().thread()]


def test_exception_is_delivered_to_on_failed(qtbot):
    errors = []
    run_in_background(lambda: 1 / 0, lambda value: None, errors.append)
    qtbot.waitUntil(lambda: len(errors) == 1)
    assert isinstance(errors[0], ZeroDivisionError)
