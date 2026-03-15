from tests.fuzzing.story import Step, Story


def test_step_narrative_formats_args():
    step = Step(
        action_name="create_catalogue",
        args={"name": "MyCat"},
        narrate_template="Created catalogue '{name}'",
    )
    assert step.narrative == "Created catalogue 'MyCat'"


def test_step_narrative_with_result():
    step = Step(
        action_name="create_catalogue",
        args={},
        narrate_template="Created catalogue '{result}'",
        result="cat-uuid-1",
    )
    assert step.narrative == "Created catalogue 'cat-uuid-1'"


def test_step_as_code():
    step = Step(
        action_name="create_catalogue",
        args={"name": "MyCat"},
        narrate_template="",
    )
    assert step.as_code() == "actions.create_catalogue(name='MyCat')"


def test_story_narrative_numbers_steps():
    story = Story()
    story.record(Step("a", {}, "Did A"))
    story.record(Step("b", {"x": "1"}, "Did B with {x}"))
    lines = story.narrative().split("\n")
    assert lines[0] == "1. Did A"
    assert lines[1] == "2. Did B with 1"


def test_story_reproducer():
    story = Story()
    story.record(Step("create_catalogue", {}, ""))
    story.record(Step("select", {"uuid": "abc"}, ""))
    code = story.reproducer()
    assert "def test_reproducer(gui, qtbot):" in code
    assert "actions.create_catalogue()" in code
    assert "actions.select(uuid='abc')" in code


def test_empty_story():
    story = Story()
    assert story.narrative() == ""
    assert "def test_reproducer" in story.reproducer()
