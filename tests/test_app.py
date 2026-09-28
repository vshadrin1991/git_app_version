import logging
import stat

from git_version_tagger import app as app_module


def test_log_folder_is_private(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(app_module, "user_log_dir", lambda name: str(log_dir))
    logger = logging.getLogger("git_version_tagger")
    before = list(logger.handlers)
    try:
        app_module.setup_logging()
        assert stat.S_IMODE(log_dir.stat().st_mode) == 0o700  # the log names repos, hosts and GitHub accounts
    finally:
        for handler in logger.handlers[len(before):]:
            logger.removeHandler(handler)
            handler.close()
