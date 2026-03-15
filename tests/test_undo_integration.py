"""Integration tests for undo commands exercising the full redo/undo cycle through the driver."""
import datetime as dt

from tscat import _Catalogue, _Event

from tscat_gui.state import AppState
from tscat_gui.tscat_driver.actions import (
    CreateEntityAction,
)
from tscat_gui.undo import (
    AddEventsToCatalogue,
    DeletePermanently,
    MoveEntityToTrash,
    NewCatalogue,
    SetAttributeValue,
)


class TestNewCatalogueUndo:

    def test_push_creates_undo_entry(self, driver, wait_for_action, qtbot):
        state = AppState()
        state.push_undo_command(NewCatalogue)
        qtbot.wait(200)

        assert state.undo_stack().count() == 1
        assert 'Catalogue' in state.undo_stack().command(0).text()


class TestMoveToTrashUndo:

    def test_push_creates_undo_entry(self, driver, wait_for_action, qtbot):
        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'TrashMe', 'author': 'test'
        }))
        uuid = cat.entity.uuid

        state = AppState()
        state.updated('active_select', _Catalogue, [uuid])
        qtbot.wait(200)

        state.push_undo_command(MoveEntityToTrash)
        qtbot.wait(200)

        assert state.undo_stack().count() == 1
        assert 'Trash' in state.undo_stack().command(0).text()


class TestAddEventsToCatalogueUndo:

    def test_push_creates_undo_entry(self, driver, wait_for_action, qtbot):
        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'MyCat', 'author': 'test'
        }))
        cat_uuid = cat.entity.uuid

        evt = wait_for_action(CreateEntityAction(None, _Event, {
            'start': dt.datetime(2020, 1, 1), 'stop': dt.datetime(2020, 1, 2), 'author': 'test'
        }))
        evt_uuid = evt.entity.uuid

        state = AppState()
        state.updated('active_select', _Catalogue, [cat_uuid])

        state.push_undo_command(AddEventsToCatalogue, cat_uuid, [evt_uuid])
        qtbot.wait(200)

        assert state.undo_stack().count() == 1


class TestDeletePermanentlyUndo:

    def test_push_creates_undo_entry(self, driver, wait_for_action, qtbot):
        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'DeleteMe', 'author': 'test'
        }))
        uuid = cat.entity.uuid

        state = AppState()
        state.updated('active_select', _Catalogue, [uuid])

        state.push_undo_command(DeletePermanently)
        qtbot.wait(200)

        assert state.undo_stack().count() == 1


class TestSetAttributeValueUndoRedo:

    def test_redo_then_undo_restores_original(self, driver, wait_for_action, qtbot):
        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Original', 'author': 'test'
        }))
        uuid = cat.entity.uuid

        state = AppState()
        state.updated('active_select', _Catalogue, [uuid])

        state.push_undo_command(SetAttributeValue, 'name', 'Changed')
        qtbot.wait(200)

        assert driver.entity_from_uuid(uuid).name == 'Changed'

        state.undo_stack().undo()
        qtbot.wait(200)

        assert driver.entity_from_uuid(uuid).name == 'Original'
