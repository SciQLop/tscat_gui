"""Tests for AppState."""
from PySide6.QtGui import QUndoCommand

from tscat import _Catalogue, _Event

from tscat_gui.state import AppState


class TestAppStateInitial:
    def test_initial_selection_is_empty(self):
        state = AppState()
        ss = state.select_state()
        assert ss.selected == []
        assert ss.type is _Catalogue
        assert ss.selected_catalogues == []
        assert ss.catalogue_path == []


class TestAppStateUpdated:
    def test_active_select_changes_state(self):
        state = AppState()
        state.updated('active_select', _Catalogue, ['uuid-1'])

        ss = state.select_state()
        assert ss.selected == ['uuid-1']
        assert ss.type is _Catalogue
        assert ss.selected_catalogues == ['uuid-1']

    def test_active_select_with_event_type(self):
        state = AppState()
        state.updated('active_select', _Event, ['evt-1', 'evt-2'])

        ss = state.select_state()
        assert ss.selected == ['evt-1', 'evt-2']
        assert ss.type is _Event
        assert ss.selected_catalogues == []

    def test_updated_emits_state_changed(self, qtbot):
        state = AppState()

        with qtbot.waitSignal(state.state_changed, timeout=1000) as blocker:
            state.updated('active_select', _Catalogue, ['uuid-1'])

        assert blocker.args == ['active_select', _Catalogue, ['uuid-1']]


class TestAppStateSelectStateCopy:
    def test_returns_deepcopy(self):
        state = AppState()
        state.updated('active_select', _Catalogue, ['uuid-1'])

        ss1 = state.select_state()
        ss1.selected.append('uuid-2')

        ss2 = state.select_state()
        assert ss2.selected == ['uuid-1']


class TestAppStateUndoStack:
    def test_push_undo_command(self):
        state = AppState()

        class DummyCommand(QUndoCommand):
            executed = False

            def __init__(self, app_state):
                super().__init__()
                DummyCommand.executed = True

        state.push_undo_command(DummyCommand)
        assert DummyCommand.executed
        assert state.undo_stack().count() == 1


class TestAppStateCataloguePath:
    def test_set_and_get_path(self):
        state = AppState()
        state.set_catalogue_path(['root', 'sub'])
        assert state.current_catalogue_path() == ['root', 'sub']

    def test_initial_path_is_empty(self):
        state = AppState()
        assert state.current_catalogue_path() == []
