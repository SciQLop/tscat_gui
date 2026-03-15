from __future__ import annotations

from tests.fuzzing.actions import ActionRegistry, settle, ui_action
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
    precondition=lambda model: (
        len(model.selected_catalogues) > 0 or len(model.selected_events) > 0
    ),
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
    precondition=lambda model: (
        len(model.selected_catalogues) > 0 or len(model.selected_events) > 0
    ),
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
    precondition=lambda model: (
        len(model.selected_catalogues) > 0 or len(model.selected_events) > 0
    ),
    settle_timeout_ms=500,
)
def delete_attribute(
    gui: TSCatGUI,
    model: AppModel,
    attr_name: str = "test_attr",
):
    gui.state.push_undo_command(DeleteAttribute, attr_name)
    settle(500)
