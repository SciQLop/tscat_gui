import os

import pytest

import tscat.base as _tscat_base
from tscat_gui import TSCatGUI
from tscat_gui.tscat_driver.driver import tscat_driver
from tests.fuzzing.actions import StoryRunner


@pytest.fixture(scope="session", autouse=True)
def _verify_temp_db():
    """Safety guard: abort if the tscat backend is not using a temp database."""
    backend = _tscat_base._backend
    db_url = str(backend.engine.url)
    assert "tmp" in db_url or "test" in db_url, \
        f"SAFETY: fuzzing tests must run against a temp database, not real catalogues! (url={db_url})"


@pytest.fixture(scope="session", autouse=True)
def fuzzing_reports_dir():
    """Ensure test-reports directory exists for story dumps."""
    reports_dir = os.environ.get("TSCAT_TEST_REPORTS", "test-reports")
    os.makedirs(reports_dir, exist_ok=True)


@pytest.fixture
def gui(qtbot):
    """A TSCatGUI widget with test isolation."""
    widget = TSCatGUI()
    qtbot.addWidget(widget)
    yield widget
    tscat_driver.setParent(None)


@pytest.fixture
def story_runner(gui):
    """A StoryRunner wired to the live gui, with automatic cleanup."""
    runner = StoryRunner(gui)
    yield runner
    runner.cleanup()
