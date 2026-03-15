from __future__ import annotations

from tests.fuzzing.actions import ActionRegistry, settle, ui_action
from tests.fuzzing.introspect import catalogue_uuids
from tests.fuzzing.model import AppModel
from tscat_gui import TSCatGUI

registry = ActionRegistry()


def _verify_catalogues(gui: TSCatGUI, model: AppModel) -> None:
    live = set(catalogue_uuids(gui))
    expected = {u for u in model.catalogues if u not in model.trashed}
    assert live == expected, f"catalogues mismatch: live={live}, expected={expected}"


@registry.register
@ui_action(
    narrate="Undo",
    model_update=lambda model: model.pop_snapshot(),
    verify=_verify_catalogues,
    precondition=lambda model: model.has_undo,
    manages_own_snapshots=True,
    settle_timeout_ms=500,
)
def undo(gui: TSCatGUI, model: AppModel):
    gui.state.undo_stack().undo()
    settle(500)


@registry.register
@ui_action(
    narrate="Redo",
    model_update=lambda model: model.pop_redo(),
    verify=_verify_catalogues,
    precondition=lambda model: model.has_redo,
    manages_own_snapshots=True,
    settle_timeout_ms=500,
)
def redo(gui: TSCatGUI, model: AppModel):
    gui.state.undo_stack().redo()
    settle(500)
