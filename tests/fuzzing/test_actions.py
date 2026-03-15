import inspect

import pytest

from tests.fuzzing.actions import ui_action, ActionRegistry, StoryRunner
from tests.fuzzing.model import AppModel


def test_ui_action_stores_metadata():
    @ui_action(
        narrate="Did something",
        model_update=lambda model: None,
        verify=lambda gui, model: True,
    )
    def my_action(gui, model):
        return "ok"

    assert my_action._ui_meta.narrate == "Did something"
    assert my_action._ui_meta.precondition is None
    assert my_action._ui_meta.manages_own_snapshots is False


def test_ui_action_with_precondition():
    @ui_action(
        narrate="X",
        model_update=lambda model: None,
        verify=lambda gui, model: True,
        precondition=lambda model: model.has_catalogues,
    )
    def guarded(gui, model):
        pass

    assert guarded._ui_meta.precondition is not None
    model = AppModel()
    assert not guarded._ui_meta.precondition(model)
    model.catalogues.append("C")
    assert guarded._ui_meta.precondition(model)


def test_ui_action_with_target():
    @ui_action(
        target="catalogues",
        narrate="Created '{result}'",
        model_update=lambda model, result: model.catalogues.append(result),
        verify=lambda gui, model: True,
    )
    def create(gui, model):
        return "cat-1"

    assert create._ui_meta.target == "catalogues"


def test_ui_action_manages_own_snapshots():
    @ui_action(
        narrate="Undo",
        model_update=lambda model: None,
        verify=lambda gui, model: True,
        manages_own_snapshots=True,
    )
    def undo(gui, model):
        pass

    assert undo._ui_meta.manages_own_snapshots is True


def test_registry_collects_actions():
    registry = ActionRegistry()

    @registry.register
    @ui_action(
        narrate="A", model_update=lambda model: None, verify=lambda gui, model: True
    )
    def action_a(gui, model):
        pass

    @registry.register
    @ui_action(
        narrate="B", model_update=lambda model: None, verify=lambda gui, model: True
    )
    def action_b(gui, model):
        pass

    assert len(registry.actions) == 2
    assert registry.actions[0].__name__ == "action_a"


def test_callback_binding_introspects_signature():
    received = {}

    def capture_update(model, result):
        received["model"] = model
        received["result"] = result

    @ui_action(
        narrate="",
        model_update=capture_update,
        verify=lambda gui, model: True,
    )
    def act(gui, model):
        return "val"

    meta = act._ui_meta
    kwargs = {"result": "val", "extra": "ignored"}
    params = set(inspect.signature(meta.model_update).parameters.keys())
    bound = {k: v for k, v in kwargs.items() if k in params}
    meta.model_update(model=AppModel(), **bound)
    assert received["result"] == "val"
    assert "extra" not in received


class _FakeGui:
    pass


def test_story_runner_records_steps():
    @ui_action(
        target="catalogues",
        narrate="Created catalogue '{result}'",
        model_update=lambda model, result: model.catalogues.append(result),
        verify=lambda gui, model: True,
    )
    def create(gui, model):
        return "cat-1"

    runner = StoryRunner(_FakeGui())
    result = runner.run(create)

    assert result == "cat-1"
    assert runner.model.catalogues == ["cat-1"]
    assert len(runner.story.steps) == 1
    assert "cat-1" in runner.story.steps[0].narrative


def test_story_runner_dumps_on_failure():
    @ui_action(
        narrate="Boom",
        model_update=lambda model: None,
        verify=lambda gui, model: False,
    )
    def failing(gui, model):
        return None

    runner = StoryRunner(_FakeGui())
    with pytest.raises(AssertionError, match="Verification failed"):
        runner.run(failing)

    assert len(runner.story.steps) == 1
    assert runner.story.steps[0].error is not None


def test_run_action_pushes_snapshot_for_normal_actions():
    @ui_action(
        narrate="Normal",
        model_update=lambda model: None,
        verify=lambda gui, model: True,
    )
    def normal(gui, model):
        return None

    runner = StoryRunner(_FakeGui())
    runner.run(normal)
    assert len(runner.model._snapshots) == 1


def test_run_action_skips_snapshot_for_manages_own():
    @ui_action(
        narrate="Self-managed",
        model_update=lambda model: None,
        verify=lambda gui, model: True,
        manages_own_snapshots=True,
    )
    def self_managed(gui, model):
        return None

    runner = StoryRunner(_FakeGui())
    runner.run(self_managed)
    assert len(runner.model._snapshots) == 0
