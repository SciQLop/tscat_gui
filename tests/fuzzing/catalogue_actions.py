from __future__ import annotations

from hypothesis import strategies as st
from PySide6.QtCore import QItemSelectionModel

import tscat

from tests.fuzzing.actions import SKIP, ActionRegistry, settle, ui_action
from tests.fuzzing.introspect import catalogue_uuids, selected_catalogue_uuids, trashed_uuids
from tests.fuzzing.model import AppModel
from tscat_gui import TSCatGUI
from tscat_gui.undo import (
    DeletePermanently,
    MoveEntityToTrash,
    NewCatalogue,
    RestoreEntityFromTrash,
)

registry = ActionRegistry()


def _verify_catalogues(gui: TSCatGUI, model: AppModel) -> None:
    live = set(catalogue_uuids(gui))
    expected = {u for u in model.catalogues if u not in model.trashed}
    assert live == expected, f"catalogues mismatch: live={live}, expected={expected}"


def _verify_trashed(gui: TSCatGUI, model: AppModel) -> None:
    live = trashed_uuids(gui)
    expected = model.trashed & set(model.catalogues)
    assert live == expected, f"trashed mismatch: live={live}, expected={expected}"


@registry.register
@ui_action(
    narrate="Create catalogue -> {result}",
    model_update=lambda model, result: (
        model.catalogues.append(result),
        model.select_catalogue([result]),
    ),
    verify=_verify_catalogues,
    settle_timeout_ms=500,
)
def create_catalogue(gui: TSCatGUI, model: AppModel):
    before = set(catalogue_uuids(gui))
    gui.state.push_undo_command(NewCatalogue)
    settle(500)
    after = set(catalogue_uuids(gui))
    new = after - before
    assert len(new) == 1, f"Expected 1 new catalogue, got {len(new)}"
    return new.pop()


@registry.register
@ui_action(
    narrate="Select catalogue (idx={idx})",
    strategies={"idx": st.integers(min_value=0, max_value=999)},
    precondition=lambda model: model.has_catalogues,
    model_update=lambda model, uuid: model.select_catalogue([uuid]),
    verify=lambda gui, model, uuid: uuid in selected_catalogue_uuids(gui),
    settle_timeout_ms=500,
    manages_own_snapshots=True,
)
def select_catalogue(gui: TSCatGUI, model: AppModel, idx: int):
    active = [u for u in model.catalogues if u not in model.trashed]
    if not active:
        return SKIP
    uuid = active[idx % len(active)]
    source_index = gui.catalogue_model.index_from_uuid(uuid)
    proxy_index = gui.catalogue_sort_filter_model.mapFromSource(source_index)
    assert proxy_index.isValid(), f"Could not find proxy index for {uuid}"
    gui.catalogues_view.selectionModel().select(
        proxy_index, QItemSelectionModel.SelectionFlag.ClearAndSelect
    )
    settle(500)
    return {"uuid": uuid}


@registry.register
@ui_action(
    narrate="Trash catalogue (idx={idx})",
    strategies={"idx": st.integers(min_value=0, max_value=999)},
    model_update=lambda model, uuid: (
        model.trashed.add(uuid),
        model.selected_catalogues.remove(uuid) if uuid in model.selected_catalogues else None,
    ),
    verify=_verify_trashed,
    precondition=lambda model: model.has_catalogues,
    settle_timeout_ms=500,
)
def trash_catalogue(gui: TSCatGUI, model: AppModel, idx: int):
    active = [u for u in model.catalogues if u not in model.trashed]
    if not active:
        return SKIP
    uuid = active[idx % len(active)]
    gui.state.updated("active_select", tscat._Catalogue, [uuid])
    settle(100)
    gui.state.push_undo_command(MoveEntityToTrash)
    settle(500)
    return {"uuid": uuid}


@registry.register
@ui_action(
    narrate="Restore catalogue (idx={idx})",
    strategies={"idx": st.integers(min_value=0, max_value=999)},
    model_update=lambda model, uuid: model.trashed.discard(uuid),
    verify=_verify_catalogues,
    precondition=lambda model: model.has_trashed,
    settle_timeout_ms=500,
)
def restore_catalogue(gui: TSCatGUI, model: AppModel, idx: int):
    trashed_cats = [u for u in model.catalogues if u in model.trashed]
    if not trashed_cats:
        return SKIP
    uuid = trashed_cats[idx % len(trashed_cats)]
    gui.state.updated("active_select", tscat._Catalogue, [uuid])
    settle(100)
    gui.state.push_undo_command(RestoreEntityFromTrash)
    settle(500)
    return {"uuid": uuid}


@registry.register
@ui_action(
    narrate="Delete catalogue permanently (idx={idx})",
    strategies={"idx": st.integers(min_value=0, max_value=999)},
    model_update=lambda model, uuid: (
        model.catalogues.remove(uuid),
        model.trashed.discard(uuid),
        model.selected_catalogues.remove(uuid) if uuid in model.selected_catalogues else None,
    ),
    verify=_verify_catalogues,
    precondition=lambda model: model.has_trashed,
    settle_timeout_ms=500,
)
def delete_permanently(gui: TSCatGUI, model: AppModel, idx: int):
    trashed_cats = [u for u in model.catalogues if u in model.trashed]
    if not trashed_cats:
        return SKIP
    uuid = trashed_cats[idx % len(trashed_cats)]
    gui.state.updated("active_select", tscat._Catalogue, [uuid])
    settle(100)
    gui.state.push_undo_command(DeletePermanently)
    settle(500)
    return {"uuid": uuid}
