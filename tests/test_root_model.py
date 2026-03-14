"""Tests for TscatRootModel tree operations."""
import datetime as dt

from PySide6.QtCore import QPersistentModelIndex, QModelIndex, Qt
from tscat import _Catalogue, _Event

from tscat_gui.model_base.constants import EntityRole, UUIDDataRole
from tscat_gui.tscat_driver.actions import (
    CreateEntityAction,
    GetCataloguesAction,
    MoveToTrashAction,
    RestoreFromTrashAction,
)
from tscat_gui.tscat_driver.tscat_root_model import TscatRootModel


class TestTscatRootModel:

    def test_initial_state_has_trash(self, wait_for_action, qtbot):
        model = TscatRootModel()
        # Trash is always the first child of root
        assert model.rowCount() >= 1
        trash_index = model.index(0, 0)
        assert trash_index.data(Qt.DisplayRole) == 'Trash'

    def test_create_catalogue_appears_in_tree(self, driver, wait_for_action, qtbot):
        model = TscatRootModel()

        action = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'My Catalogue', 'author': 'test'
        }))

        # Process pending events so the model updates
        qtbot.wait(100)

        found = False
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            if index.data(Qt.DisplayRole) == 'My Catalogue':
                found = True
                assert index.data(UUIDDataRole) == action.entity.uuid
                assert isinstance(index.data(EntityRole), _Catalogue)
                break

        assert found, "Created catalogue not found in model"

    def test_empty_trash_no_crash(self, wait_for_action, qtbot):
        """Bug #5: beginRemoveRows(0, -1) when trash is empty must not crash."""
        model = TscatRootModel()

        # Fetching removed items with empty trash should not crash
        wait_for_action(GetCataloguesAction(None, removed_items=True))
        qtbot.wait(100)

        trash_index = model.index(0, 0)
        assert model.rowCount(trash_index) == 0

    def test_move_to_trash_and_restore(self, driver, wait_for_action, qtbot):
        model = TscatRootModel()

        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Trashable', 'author': 'test'
        }))
        qtbot.wait(100)
        uuid = cat.entity.uuid

        wait_for_action(MoveToTrashAction(None, [uuid]))
        qtbot.wait(100)

        # Should be in trash now
        trash_index = model.index(0, 0)
        assert model.rowCount(trash_index) >= 1

        wait_for_action(RestoreFromTrashAction(None, [uuid]))
        qtbot.wait(100)

        # Should be back in the tree (not in trash)
        node = model._node_from_uuid(uuid)
        assert node is not None

    def test_expanded_indexes_use_persistent(self, wait_for_action, qtbot):
        """Bug #4/stale indexes: expanded_indexes must use QPersistentModelIndex."""
        model = TscatRootModel()

        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Test', 'author': 'test'
        }))
        qtbot.wait(100)

        index = model.index_from_uuid(cat.entity.uuid)
        assert index.isValid()

        model.expanded(index)
        assert len(model.expanded_indexes) == 1
        stored = next(iter(model.expanded_indexes))
        assert isinstance(stored, QPersistentModelIndex)

        model.collapsed(index)
        assert len(model.expanded_indexes) == 0

    def test_data_changed_signal_correct_signature(self, wait_for_action, qtbot):
        """Bug #4: dataChanged must emit (index, index, [role]), not (index, role)."""
        model = TscatRootModel()

        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Test', 'author': 'test'
        }))
        qtbot.wait(100)

        index = model.index_from_uuid(cat.entity.uuid)

        received = []
        model.dataChanged.connect(lambda tl, br, roles=None: received.append((tl, br, roles)))

        model.expanded(index)

        assert len(received) == 1
        top_left, bottom_right, roles = received[0]
        assert top_left == index
        assert bottom_right == index
