from tests.fuzzing.catalogue_actions import (
    create_catalogue,
    restore_catalogue,
    select_catalogue,
    trash_catalogue,
)


def test_create_and_select_catalogue(story_runner):
    uuid = story_runner.run(create_catalogue)
    assert uuid is not None

    story_runner.run(select_catalogue, idx=0)
    assert uuid in story_runner.model.selected_catalogues


def test_create_trash_and_restore(story_runner):
    uuid = story_runner.run(create_catalogue)

    story_runner.run(select_catalogue, idx=0)
    story_runner.run(trash_catalogue, idx=0)
    assert uuid in story_runner.model.trashed

    story_runner.run(restore_catalogue, idx=0)
    assert uuid not in story_runner.model.trashed
