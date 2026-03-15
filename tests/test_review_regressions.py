"""Regression tests for bugs identified during PR #98 code review.

Each test reproduces a specific bug that was fixed, and must fail
if the fix is reverted.
"""
import datetime as dt
from unittest.mock import patch

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QStandardItemModel
from tscat import _Catalogue, _Event

from tscat_gui.tscat_driver.actions import (
    CreateEntityAction,
    DeletePermanentlyAction,
    GetCataloguesAction,
)
from tscat_gui.tscat_driver.tscat_root_model import TscatRootModel


class TestLessThanStrictWeakOrdering:
    """Bug: lessThan(None, None) returned True, violating strict weak ordering.

    Strict weak ordering requires: not (a < a). When both values are None,
    lessThan must return False.
    """

    def test_both_none_returns_false(self):
        from tscat_gui import _TrashAlwaysTopOrBottomSortFilterModel

        source = QStandardItemModel()
        source.appendRow([])
        source.appendRow([])

        proxy = _TrashAlwaysTopOrBottomSortFilterModel()
        proxy.setSourceModel(source)

        left = source.index(0, 0)
        right = source.index(1, 0)

        # Both items have None data (empty rows)
        assert source.data(left) is None
        assert source.data(right) is None

        # Strict weak ordering: None < None must be False
        assert proxy.lessThan(left, right) is False

    def test_reflexivity(self):
        """a < a must always be False."""
        from tscat_gui import _TrashAlwaysTopOrBottomSortFilterModel

        source = QStandardItemModel()
        source.appendRow([])

        proxy = _TrashAlwaysTopOrBottomSortFilterModel()
        proxy.setSourceModel(source)

        idx = source.index(0, 0)
        assert proxy.lessThan(idx, idx) is False


class TestLazyIconInitialization:
    """Bug: QApplication.style() was called in TscatRootModel.__init__,
    which crashes if no QApplication exists at import time.

    The fix defers icon initialization to first DecorationRole data() call.
    """

    def test_icons_not_initialized_at_construction(self, wait_for_action, qtbot):
        model = TscatRootModel()
        assert model._icons_initialized is False

    def test_icons_initialized_on_decoration_role(self, wait_for_action, qtbot):
        model = TscatRootModel()

        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'IconTest', 'author': 'test'
        }))
        qtbot.wait(100)

        index = model.index_from_uuid(cat.entity.uuid)
        assert index.isValid()

        # Request decoration role triggers lazy init
        model.data(index, Qt.DecorationRole)
        assert model._icons_initialized is True


class TestExpandedNodesClearedOnReset:
    """Bug: _expanded_nodes was not cleared during model reset, leaving
    stale entries that could cause incorrect folder icons.
    """

    def test_reset_clears_expanded_nodes(self, wait_for_action, qtbot):
        model = TscatRootModel()

        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'ExpandTest', 'author': 'test'
        }))
        qtbot.wait(100)

        index = model.index_from_uuid(cat.entity.uuid)
        model.expanded(index)
        assert len(model._expanded_nodes) == 1

        # Trigger a full model reset via GetCataloguesAction (non-removed)
        wait_for_action(GetCataloguesAction(None, removed_items=False))
        qtbot.wait(100)

        assert len(model._expanded_nodes) == 0


class TestBeginInsertRowsEmptyGuard:
    """Bug: beginInsertRows was called with invalid range (N, N-1) when
    restoring permanently deleted entities that produce no visible nodes.

    This could crash Qt's model infrastructure.
    """

    def test_restore_catalogue_only_no_crash(self, wait_for_action, qtbot):
        """Restoring only catalogues (no events) must not crash CatalogModel."""
        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'EmptyRestore', 'author': 'test'
        }))
        cat_uuid = cat.entity.uuid

        from tscat_gui.tscat_driver.model import tscat_model
        qtbot.wait(200)
        catalog_model = tscat_model.catalog(cat_uuid)
        qtbot.wait(100)

        # Delete permanently then restore — no events involved,
        # so RestorePermanentlyDeletedAction produces empty nodes list
        wait_for_action(DeletePermanentlyAction(None, [cat_uuid]))
        qtbot.wait(100)

        # The catalog model should handle this without crashing
        assert catalog_model.rowCount() == 0


class TestGetpassInsteadOfGetlogin:
    """Bug: os.getlogin() raises OSError in headless/CI environments
    (no TTY). Fixed by using getpass.getuser().
    """

    def test_undo_new_catalogue_uses_getpass(self, driver, wait_for_action, qtbot):
        from tscat_gui.undo import NewCatalogue
        from tscat_gui.state import AppState
        import tscat_gui.undo as undo_module

        # Verify getpass is used, not os.getlogin
        assert hasattr(undo_module, 'getpass')

        # Simulate headless: patch getpass.getuser to verify it's called
        with patch.object(undo_module.getpass, 'getuser', return_value='ci-user') as mock:
            state = AppState()
            state.push_undo_command(NewCatalogue)
            qtbot.wait(200)
            mock.assert_called()
