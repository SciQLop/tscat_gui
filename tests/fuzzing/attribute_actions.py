from __future__ import annotations

import datetime as dt

from hypothesis import strategies as st

from tests.fuzzing.actions import SKIP, ActionRegistry, settle, ui_action
from tests.fuzzing.introspect import entity_attribute
from tests.fuzzing.model import AppModel
from tscat_gui import TSCatGUI
from tscat_gui.undo import DeleteAttribute, NewAttribute, RenameAttribute, SetAttributeValue

registry = ActionRegistry()


@registry.register
@ui_action(
    narrate="Add attribute '{attr_name}' = {attr_value}",
    model_update=lambda model, attr_name, attr_value: (
        model.custom_attributes.update(
            {
                uuid: {**model.custom_attributes.get(uuid, {}), attr_name: attr_value}
                for uuid in model.selected_catalogues + model.selected_events
            }
        ),
    ),
    verify=lambda gui, model, attr_name, attr_value: all(
        entity_attribute(gui, uuid, attr_name) == attr_value
        for uuid in model.selected_catalogues + model.selected_events
    ),
    precondition=lambda model: (
        len(model.selected_catalogues) > 0 or len(model.selected_events) > 0
    ),
    settle_timeout_ms=500,
)
def add_custom_attribute(
    gui: TSCatGUI,
    model: AppModel,
    attr_name: str = "test_attr",
    attr_value: str = "test_value",
):
    gui.state.push_undo_command(NewAttribute, attr_name, attr_value)
    settle(500)


@registry.register
@ui_action(
    narrate="Set attribute '{attr_name}' = {attr_value}",
    model_update=lambda model, attr_name, attr_value: (
        model.custom_attributes.update(
            {
                uuid: {**model.custom_attributes.get(uuid, {}), attr_name: attr_value}
                for uuid in model.selected_catalogues + model.selected_events
            }
        ),
    ),
    verify=lambda gui, model, attr_name, attr_value: all(
        entity_attribute(gui, uuid, attr_name) == attr_value
        for uuid in model.selected_catalogues + model.selected_events
    ),
    precondition=lambda model: model.selected_have_attribute,
    settle_timeout_ms=500,
)
def set_attribute(
    gui: TSCatGUI,
    model: AppModel,
    attr_name: str = "test_attr",
    attr_value: str = "new_value",
):
    gui.state.push_undo_command(SetAttributeValue, attr_name, attr_value)
    settle(500)


@registry.register
@ui_action(
    narrate="Rename attribute '{old_name}' -> '{new_name}'",
    model_update=lambda model, old_name, new_name: (
        model.custom_attributes.update(
            {
                uuid: {
                    **(
                        {k: v for k, v in model.custom_attributes.get(uuid, {}).items() if k != old_name}
                    ),
                    new_name: model.custom_attributes.get(uuid, {}).get(old_name),
                }
                for uuid in model.selected_catalogues + model.selected_events
            }
        ),
    ),
    verify=lambda gui, model, new_name: all(
        entity_attribute(gui, uuid, new_name) is not None
        for uuid in model.selected_catalogues + model.selected_events
    ),
    precondition=lambda model: model.selected_have_attribute,
    settle_timeout_ms=500,
)
def rename_attribute(
    gui: TSCatGUI,
    model: AppModel,
    old_name: str = "test_attr",
    new_name: str = "renamed_attr",
):
    gui.state.push_undo_command(RenameAttribute, old_name, new_name)
    settle(500)


@registry.register
@ui_action(
    narrate="Delete attribute '{attr_name}'",
    model_update=lambda model, attr_name: (
        model.custom_attributes.update(
            {
                uuid: {
                    k: v
                    for k, v in model.custom_attributes.get(uuid, {}).items()
                    if k != attr_name
                }
                for uuid in model.selected_catalogues + model.selected_events
            }
        ),
    ),
    verify=lambda gui, model, attr_name: all(
        entity_attribute(gui, uuid, attr_name) is None
        for uuid in model.selected_catalogues + model.selected_events
    ),
    precondition=lambda model: model.selected_have_attribute,
    settle_timeout_ms=500,
)
def delete_attribute(
    gui: TSCatGUI,
    model: AppModel,
    attr_name: str = "test_attr",
):
    gui.state.push_undo_command(DeleteAttribute, attr_name)
    settle(500)


@registry.register
@ui_action(
    narrate="Edit catalogue name (idx={idx}) -> '{new_name}'",
    strategies={
        "idx": st.integers(min_value=0, max_value=999),
        "new_name": st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
            min_size=1,
            max_size=30,
        ),
    },
    model_update=lambda model, uuid, new_name: None,
    verify=lambda gui, model, uuid, new_name: entity_attribute(gui, uuid, "name") == new_name,
    precondition=lambda model: len([c for c in model.catalogues if c not in model.trashed]) > 0,
    settle_timeout_ms=500,
)
def edit_catalogue_name(gui: TSCatGUI, model: AppModel, idx: int, new_name: str):
    active = [c for c in model.catalogues if c not in model.trashed]
    if not active:
        return SKIP
    uuid = active[idx % len(active)]
    gui.state.updated("active_select", __import__("tscat")._Catalogue, [uuid])
    settle(100)
    gui.state.push_undo_command(SetAttributeValue, "name", new_name)
    settle(500)
    return {"uuid": uuid, "new_name": new_name}


@registry.register
@ui_action(
    narrate="Edit event dates (idx={idx})",
    strategies={
        "idx": st.integers(min_value=0, max_value=999),
        "offset_hours": st.integers(min_value=1, max_value=720),
    },
    model_update=lambda model, uuid, new_start, new_stop: None,
    verify=lambda gui, model, uuid, new_start, new_stop: (
        entity_attribute(gui, uuid, "start") == new_start
        and entity_attribute(gui, uuid, "stop") == new_stop
    ),
    precondition=lambda model: model.has_events,
    settle_timeout_ms=500,
)
def edit_event_dates(gui: TSCatGUI, model: AppModel, idx: int, offset_hours: int):
    import tscat
    all_events = [ev for evts in model.events.values() for ev in evts if ev not in model.trashed]
    if not all_events:
        return SKIP
    uuid = all_events[idx % len(all_events)]

    new_start = dt.datetime(2020, 1, 1) + dt.timedelta(hours=offset_hours)
    new_stop = new_start + dt.timedelta(hours=1)

    gui.state.updated("active_select", tscat._Event, [uuid])
    settle(100)
    gui.state.push_undo_command(SetAttributeValue, "start", new_start)
    settle(300)
    gui.state.push_undo_command(SetAttributeValue, "stop", new_stop)
    settle(500)
    return {"uuid": uuid, "new_start": new_start, "new_stop": new_stop}
