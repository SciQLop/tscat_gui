"""Tests for undo commands."""
import datetime as dt

from tscat import _Catalogue, _Event

from tscat_gui.state import AppState
from tscat_gui.tscat_driver.actions import (
    AddEventsToCatalogueAction,
    CreateEntityAction,
    SetAttributeAction,
)
from tscat_gui.undo import RenameAttribute, SetAttributeValue, DeleteAttribute


class TestRenameAttribute:
    """Bug #10: RenameAttribute must capture values at construction, not execution."""

    def test_values_captured_at_init(self, driver, wait_for_action, qtbot):
        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Test', 'author': 'test'
        }))
        uuid = cat.entity.uuid

        # Set a custom attribute
        wait_for_action(SetAttributeAction(None, [uuid], 'color', ['red']))

        state = AppState()
        state.updated('active_select', _Catalogue, [uuid])

        cmd = RenameAttribute(state, 'color', 'colour')

        # Values should be captured at construction
        assert hasattr(cmd, 'values')
        assert cmd.values == ['red']

    def test_captured_values_survive_external_change(self, driver, wait_for_action, qtbot):
        """Values captured at init should not change if the entity is modified later."""
        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Test', 'author': 'test'
        }))
        uuid = cat.entity.uuid

        wait_for_action(SetAttributeAction(None, [uuid], 'color', ['red']))

        state = AppState()
        state.updated('active_select', _Catalogue, [uuid])

        cmd = RenameAttribute(state, 'color', 'colour')
        assert cmd.values == ['red']

        # Modify the attribute externally after command construction
        wait_for_action(SetAttributeAction(None, [uuid], 'color', ['blue']))

        # The captured values should still be 'red'
        assert cmd.values == ['red']


class TestSetAttributeValue:

    def test_captures_previous_values(self, driver, wait_for_action, qtbot):
        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Original', 'author': 'test'
        }))
        uuid = cat.entity.uuid

        state = AppState()
        state.updated('active_select', _Catalogue, [uuid])

        cmd = SetAttributeValue(state, 'name', 'Updated')
        assert cmd.previous_values == ['Original']
        assert cmd.new_value == 'Updated'


class TestDeleteAttribute:

    def test_captures_values_at_init(self, driver, wait_for_action, qtbot):
        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Test', 'author': 'test'
        }))
        uuid = cat.entity.uuid

        wait_for_action(SetAttributeAction(None, [uuid], 'priority', [42]))

        state = AppState()
        state.updated('active_select', _Catalogue, [uuid])

        cmd = DeleteAttribute(state, 'priority')
        assert cmd.values == [42]
