from __future__ import annotations

from hypothesis import strategies as st

import tscat

from tests.fuzzing.actions import SKIP, ActionRegistry, settle, ui_action
from tests.fuzzing.introspect import selected_event_uuids, visible_event_count
from tests.fuzzing.model import AppModel
from tscat_gui import TSCatGUI
from tscat_gui.undo import AddEventsToCatalogue, MoveEntityToTrash, NewEvent

registry = ActionRegistry()


def _verify_event_count(gui: TSCatGUI, model: AppModel) -> None:
    expected = len(model.active_events)
    live = visible_event_count(gui)
    assert live == expected, f"event count mismatch: live={live}, expected={expected}"


def _model_create_event(model: AppModel, result: str) -> None:
    model.events.setdefault(model.selected_catalogues[0], []).append(result)
    model.selected_events = [result]


@registry.register
@ui_action(
    narrate="Create event -> {result}",
    model_update=_model_create_event,
    verify=_verify_event_count,
    precondition=lambda model: (
        len(model.selected_catalogues) == 1
        and model.selected_catalogues[0] not in model.trashed
    ),
    settle_timeout_ms=500,
)
def create_event(gui: TSCatGUI, model: AppModel):
    gui.state.push_undo_command(NewEvent)
    settle(500)
    uuids = selected_event_uuids(gui)
    assert len(uuids) >= 1, f"Expected at least 1 selected event, got {len(uuids)}"
    return uuids[-1]


@registry.register
@ui_action(
    narrate="Add event (eidx={eidx}) to catalogue (cidx={cidx})",
    strategies={
        "eidx": st.integers(min_value=0, max_value=999),
        "cidx": st.integers(min_value=0, max_value=999),
    },
    model_update=lambda model, event_uuid, catalogue_uuid: (
        model.events.setdefault(catalogue_uuid, []).append(event_uuid),
    ),
    verify=lambda gui, model: True,
    precondition=lambda model: model.has_events and len(model.catalogues) > 1,
    settle_timeout_ms=500,
)
def add_event_to_catalogue(gui: TSCatGUI, model: AppModel, eidx: int, cidx: int):
    all_events = [ev for evts in model.events.values() for ev in evts]
    if not all_events:
        return SKIP
    event_uuid = all_events[eidx % len(all_events)]
    catalogue_uuid = model.catalogues[cidx % len(model.catalogues)]
    gui.state.push_undo_command(AddEventsToCatalogue, catalogue_uuid, [event_uuid])
    settle(500)
    return {"event_uuid": event_uuid, "catalogue_uuid": catalogue_uuid}


@registry.register
@ui_action(
    narrate="Trash event (idx={idx})",
    strategies={"idx": st.integers(min_value=0, max_value=999)},
    model_update=lambda model, uuid: (
        model.trashed.add(uuid),
        model.selected_events.clear(),
        model.selected_events.append(uuid),
    ),
    verify=_verify_event_count,
    precondition=lambda model: model.has_events,
    settle_timeout_ms=500,
)
def trash_event(gui: TSCatGUI, model: AppModel, idx: int):
    all_events = [ev for evts in model.events.values() for ev in evts if ev not in model.trashed]
    if not all_events:
        return SKIP
    uuid = all_events[idx % len(all_events)]
    gui.state.updated("active_select", tscat._Event, [uuid])
    settle(100)
    gui.state.push_undo_command(MoveEntityToTrash)
    settle(500)
    return {"uuid": uuid}
