from __future__ import annotations

import tscat

from tests.fuzzing.actions import ActionRegistry, settle, ui_action
from tests.fuzzing.introspect import selected_event_uuids, visible_event_count
from tests.fuzzing.model import AppModel
from tscat_gui import TSCatGUI
from tscat_gui.undo import AddEventsToCatalogue, MoveEntityToTrash, NewEvent

registry = ActionRegistry()


def _verify_event_count(gui: TSCatGUI, model: AppModel) -> None:
    expected = len(model.active_events)
    live = visible_event_count(gui)
    assert live == expected, f"event count mismatch: live={live}, expected={expected}"


@registry.register
@ui_action(
    target="events",
    narrate="Create event -> {result}",
    model_update=lambda model, result: (
        model.events.setdefault(model.selected_catalogues[0], []).append(result),
    ),
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
    narrate="Add events {event_uuids} to catalogue {catalogue_uuid}",
    model_update=lambda model, event_uuids, catalogue_uuid: (
        model.events.setdefault(catalogue_uuid, []).extend(event_uuids),
    ),
    verify=lambda gui, model: True,
    precondition=lambda model: model.has_events and len(model.catalogues) > 1,
    settle_timeout_ms=500,
)
def add_event_to_catalogue(
    gui: TSCatGUI, model: AppModel, event_uuids: list[str], catalogue_uuid: str
):
    gui.state.push_undo_command(AddEventsToCatalogue, catalogue_uuid, event_uuids)
    settle(500)


@registry.register
@ui_action(
    narrate="Trash event {uuid}",
    model_update=lambda model, uuid: model.trashed.add(uuid),
    verify=_verify_event_count,
    precondition=lambda model: model.has_events,
    settle_timeout_ms=500,
)
def trash_event(gui: TSCatGUI, model: AppModel, uuid: str):
    gui.state.updated("active_select", tscat._Event, [uuid])
    settle(100)
    gui.state.push_undo_command(MoveEntityToTrash)
    settle(500)
