from tests.fuzzing.model import AppModel


def test_fresh_model_is_empty():
    model = AppModel()
    assert not model.has_catalogues
    assert not model.has_events
    assert not model.has_trashed
    assert not model.has_undo
    assert model.events == {}
    assert model.custom_attributes == {}


def test_add_catalogue():
    model = AppModel()
    model.catalogues.append("cat-1")
    assert model.has_catalogues
    assert len(model.catalogues) == 1


def test_add_event():
    model = AppModel()
    model.catalogues.append("cat-1")
    model.events.setdefault("cat-1", []).append("ev-1")
    assert model.has_events


def test_trash_and_has_trashed():
    model = AppModel()
    model.trashed.add("cat-1")
    assert model.has_trashed


def test_active_events_returns_events_in_selected_catalogues():
    model = AppModel()
    model.catalogues.extend(["cat-1", "cat-2"])
    model.events["cat-1"] = ["ev-1", "ev-2"]
    model.events["cat-2"] = ["ev-3"]
    model.selected_catalogues = ["cat-1"]
    assert model.active_events == ["ev-1", "ev-2"]


def test_active_events_excludes_trashed():
    model = AppModel()
    model.catalogues.append("cat-1")
    model.events["cat-1"] = ["ev-1", "ev-2"]
    model.trashed.add("ev-1")
    model.selected_catalogues = ["cat-1"]
    assert model.active_events == ["ev-2"]


def test_select_catalogue_clears_selected_events():
    model = AppModel()
    model.selected_events = ["ev-1"]
    model.select_catalogue(["cat-1"])
    assert model.selected_catalogues == ["cat-1"]
    assert model.selected_events == []


def test_snapshot_and_restore():
    model = AppModel()
    model.catalogues.append("cat-1")
    model.push_snapshot()
    model.catalogues.append("cat-2")
    assert len(model.catalogues) == 2
    model.pop_snapshot()
    assert model.catalogues == ["cat-1"]
    assert len(model._redo_stack) == 1


def test_new_action_clears_redo_stack():
    model = AppModel()
    model.push_snapshot()
    model.catalogues.append("cat-1")
    model.pop_snapshot()
    assert len(model._redo_stack) == 1
    model.push_snapshot()
    assert len(model._redo_stack) == 0


def test_redo_after_undo():
    model = AppModel()
    model.catalogues.append("cat-1")
    model.push_snapshot()
    model.catalogues.append("cat-2")
    model.pop_snapshot()
    assert model.catalogues == ["cat-1"]
    model.pop_redo()
    assert model.catalogues == ["cat-1", "cat-2"]


def test_reset_clears_everything():
    model = AppModel()
    model.catalogues.extend(["a", "b"])
    model.events["a"] = ["x"]
    model.trashed.add("z")
    model.push_snapshot()
    model.reset()
    assert not model.has_catalogues
    assert model.events == {}
    assert not model.has_trashed
    assert len(model._snapshots) == 0
    assert len(model._redo_stack) == 0
