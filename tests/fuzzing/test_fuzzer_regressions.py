"""Regression tests for bugs found by the story-driven UI fuzzer.

Each test reproduces a specific bug. The test must fail before the fix
and pass after.
"""
from tests.fuzzing.actions import settle


def test_entity_from_uuid_returns_none_for_missing(story_runner):
    """Bug: entity_from_uuid raises KeyError for UUIDs not in cache.

    During rapid undo/redo sequences the driver's entity cache can be
    out of sync with signal handlers referencing stale UUIDs. The method
    must return None instead of crashing.
    """
    from tscat_gui.tscat_driver.driver import tscat_driver

    bogus_uuid = "00000000-dead-beef-0000-000000000000"
    result = tscat_driver.entity_from_uuid(bogus_uuid)
    assert result is None


def test_new_event_redo_with_empty_selected_catalogues(story_runner):
    """Bug: NewEvent._redo() crashes with IndexError on selected_catalogues[0].

    When NewEvent is created with no catalogue selected (empty selected_catalogues
    in the captured state), _redo() must not crash.
    """
    from tscat_gui.undo import NewEvent
    from tscat_gui.state import AppState

    state = AppState()
    # Don't select any catalogue — selected_catalogues is []
    cmd = NewEvent(state)
    assert state.select_state().selected_catalogues == []

    # _redo should not crash — it should gracefully skip
    cmd._redo()
    settle(200)


def test_event_count_after_undo_catalogue_creation(gui):
    """Bug: passive_select didn't update selected_catalogues in AppState.

    Sequence: create_event -> create_catalogue -> undo -> create_event
    After undoing a catalogue creation, the undo command restores event
    selection via passive_select (catalogue) + active_select (event).
    But passive_select didn't update selected_catalogues, so the state
    still pointed to the deleted catalogue's UUID. The next NewEvent
    would then try to add an event to a non-existent catalogue.
    """
    from tests.fuzzing.introspect import visible_event_count
    from tscat_gui.undo import NewCatalogue, NewEvent

    gui.state.push_undo_command(NewCatalogue)
    settle(500)

    gui.state.push_undo_command(NewEvent)
    settle(500)
    assert visible_event_count(gui) == 1

    gui.state.push_undo_command(NewCatalogue)
    settle(500)
    assert visible_event_count(gui) == 0

    gui.state.undo_stack().undo()
    settle(500)
    assert visible_event_count(gui) == 1

    gui.state.push_undo_command(NewEvent)
    settle(500)
    assert visible_event_count(gui) == 2
