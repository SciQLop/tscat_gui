from tests.fuzzing.catalogue_actions import create_catalogue, select_catalogue
from tests.fuzzing.event_actions import create_event
from tests.fuzzing.introspect import catalogue_uuids, visible_event_count
from tests.fuzzing.undo_actions import redo, undo


def test_create_catalogue_and_undo(story_runner):
    uuid = story_runner.run(create_catalogue)
    assert uuid in catalogue_uuids(story_runner.gui)

    story_runner.run(undo)
    assert uuid not in catalogue_uuids(story_runner.gui)


def test_create_catalogue_undo_redo(story_runner):
    uuid = story_runner.run(create_catalogue)

    story_runner.run(undo)
    assert uuid not in catalogue_uuids(story_runner.gui)

    story_runner.run(redo)
    assert uuid in catalogue_uuids(story_runner.gui)


def test_create_event_and_undo(story_runner):
    story_runner.run(create_catalogue)

    story_runner.run(select_catalogue, idx=0)

    story_runner.run(create_event)
    assert visible_event_count(story_runner.gui) == 1

    story_runner.run(undo)
    assert visible_event_count(story_runner.gui) == 0
