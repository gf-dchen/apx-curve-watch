import logging

import pytest

from apx_curve_watch import _configure_logging


@pytest.fixture(autouse=True)
def _restore_root_logger():
    original_handlers = logging.getLogger().handlers[:]
    original_level = logging.getLogger().level
    yield
    for handler in logging.getLogger().handlers[:]:
        handler.close()
    logging.getLogger().handlers = original_handlers
    logging.getLogger().setLevel(original_level)


def test_configure_logging_creates_missing_parent_dirs_and_writes_to_file(tmp_path):
    log_path = tmp_path / "nested" / "app.log"
    _configure_logging(str(log_path))

    logging.getLogger("apx_curve_watch").info("hello from test")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_path.exists()
    assert "hello from test" in log_path.read_text()


def test_configure_logging_with_empty_path_is_console_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _configure_logging("")
    assert list(tmp_path.iterdir()) == []
