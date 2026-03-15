"""Test fixtures for tscat_gui.

The tscat backend must be initialized in testing mode BEFORE any tscat_gui
import, because tscat_gui creates module-level singletons (TscatDriver, _Model)
that immediately query the database on import.

We use a temp-file SQLite (not in-memory) because the driver's worker thread
needs cross-thread access to the same database.
"""
import os
import sys
import tempfile

from PySide6.QtWidgets import QApplication

# Ensure QApplication exists before any tscat_gui import
_app = QApplication.instance() or QApplication(sys.argv)

# Create a temp file for the test DB — in-memory SQLite is thread-local
# and doesn't work with the QThread-based driver.
_db_dir = tempfile.mkdtemp()
_db_path = os.path.join(_db_dir, 'test.sqlite')

# Patch _copy_to_tmp to just return our temp path (no source file to copy)
import tscat.orm_sqlalchemy as _orm  # noqa: E402
_orm.Backend._copy_to_tmp = lambda self, source: _db_path  # type: ignore[method-assign, assignment]

import tscat.base as _tscat_base  # noqa: E402
_tscat_base._backend = _orm.Backend(testing=_db_path)  # type: ignore[assignment]

import pytest  # noqa: E402
from tscat_gui.tscat_driver.driver import tscat_driver  # noqa: E402


@pytest.fixture
def driver():
    return tscat_driver


@pytest.fixture
def wait_for_action(qtbot):
    """Execute an action on the driver and wait for completion."""
    def _wait(action):
        with qtbot.waitSignal(tscat_driver.action_done, timeout=5000):
            tscat_driver.do(action)
        return action

    return _wait
