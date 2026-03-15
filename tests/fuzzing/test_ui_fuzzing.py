import pytest
from hypothesis.stateful import run_state_machine_as_test

from tests.fuzzing.actions import ActionRegistry
from tests.fuzzing.catalogue_actions import registry as cat_registry
from tests.fuzzing.event_actions import registry as event_registry
from tests.fuzzing.undo_actions import registry as undo_registry

combined = ActionRegistry()
for r in (cat_registry, event_registry, undo_registry):
    combined.actions.extend(r.actions)

TscatGUIFuzzer = combined.build_state_machine(
    name="TscatGUIFuzzer",
    max_examples=10,
    stateful_step_count=10,
)


@pytest.mark.qt_no_exception_capture
def test_ui_fuzzing(qtbot):
    from tscat_gui import TSCatGUI
    from tscat_gui.tscat_driver.driver import tscat_driver

    widget = TSCatGUI()
    qtbot.addWidget(widget)

    TscatGUIFuzzer.gui = widget
    TscatGUIFuzzer.qtbot = qtbot

    try:
        run_state_machine_as_test(TscatGUIFuzzer)
    finally:
        tscat_driver.setParent(None)
