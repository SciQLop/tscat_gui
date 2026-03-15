from tests.fuzzing.attribute_actions import edit_catalogue_name, edit_event_dates
from tests.fuzzing.catalogue_actions import create_catalogue, select_catalogue
from tests.fuzzing.event_actions import create_event
from tests.fuzzing.introspect import entity_attribute
from tests.fuzzing.undo_actions import undo


def test_edit_catalogue_name(story_runner):
    uuid = story_runner.run(create_catalogue)
    story_runner.run(edit_catalogue_name, idx=0, new_name="Renamed")
    assert entity_attribute(story_runner.gui, uuid, "name") == "Renamed"


def test_edit_catalogue_name_then_undo(story_runner):
    uuid = story_runner.run(create_catalogue)
    original = entity_attribute(story_runner.gui, uuid, "name")
    story_runner.run(edit_catalogue_name, idx=0, new_name="Changed")
    assert entity_attribute(story_runner.gui, uuid, "name") == "Changed"

    story_runner.run(undo)
    assert entity_attribute(story_runner.gui, uuid, "name") == original


def test_edit_event_dates(story_runner):
    story_runner.run(create_catalogue)
    story_runner.run(select_catalogue, idx=0)
    story_runner.run(create_event)
    story_runner.run(edit_event_dates, idx=0, offset_hours=100)
