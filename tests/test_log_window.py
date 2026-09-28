import logging
import threading

from git_version_tagger.ui.log_window import LogWindow, QtLogHandler


def test_log_records_from_worker_threads_reach_the_window(qtbot):
    handler = QtLogHandler()
    window = LogWindow()
    qtbot.addWidget(window)
    handler.emitter.message.connect(window.append_line)
    logger = logging.getLogger("git_version_tagger.test")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        thread = threading.Thread(target=lambda: logger.info("$ git fetch origin"))
        thread.start()
        thread.join()
        qtbot.waitUntil(lambda: "$ git fetch origin" in window.text.toPlainText())
    finally:
        logger.removeHandler(handler)
