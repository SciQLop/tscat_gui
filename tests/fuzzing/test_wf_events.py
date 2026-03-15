from tests.fuzzing.catalogue_actions import create_catalogue, select_catalogue
from tests.fuzzing.event_actions import create_event


def test_create_catalogue_then_event(story_runner):
    cat_uuid = story_runner.run(create_catalogue)

    story_runner.run(select_catalogue, uuid=cat_uuid)
    ev_uuid = story_runner.run(create_event)

    assert ev_uuid is not None
    assert ev_uuid in story_runner.model.events.get(cat_uuid, [])
