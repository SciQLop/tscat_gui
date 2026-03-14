"""Tests for CatalogModel."""
import datetime as dt

from PySide6.QtCore import QModelIndex, Qt
from tscat import _Catalogue, _Event

from tscat_gui.tscat_driver.actions import (
    AddEventsToCatalogueAction,
    CreateEntityAction,
)
from tscat_gui.tscat_driver.driver import tscat_driver
from tscat_gui.model_base.constants import UUIDDataRole


def _unparent_driver():
    tscat_driver.setParent(None)


def _create_catalogue(wait_for_action, name='TestCat'):
    return wait_for_action(CreateEntityAction(None, _Catalogue, {
        'name': name, 'author': 'test'
    }))


def _create_event(wait_for_action, **kwargs):
    params = {
        'start': dt.datetime(2020, 1, 1),
        'stop': dt.datetime(2020, 1, 2),
        'author': 'test',
    }
    params.update(kwargs)
    return wait_for_action(CreateEntityAction(None, _Event, params))


def _get_catalog_model(uuid, qtbot):
    from tscat_gui.tscat_driver.model import tscat_model
    qtbot.wait(200)  # let TscatRootModel's initial GetCataloguesActions populate the tree
    model = tscat_model.catalog(uuid)
    qtbot.wait(100)
    return model


class TestCatalogModelHeader:
    def test_header_returns_column_names(self, qtbot, wait_for_action):
        cat = _create_catalogue(wait_for_action)
        model = _get_catalog_model(cat.entity.uuid, qtbot)

        expected = ['Start', 'Stop', 'Author', 'Tags', 'Products', 'Rating', 'Attributes']
        for i, name in enumerate(expected):
            assert model.headerData(i, Qt.Orientation.Horizontal, Qt.DisplayRole) == name

        _unparent_driver()

    def test_header_vertical_returns_none(self, qtbot, wait_for_action):
        cat = _create_catalogue(wait_for_action)
        model = _get_catalog_model(cat.entity.uuid, qtbot)

        assert model.headerData(0, Qt.Orientation.Vertical, Qt.DisplayRole) is None

        _unparent_driver()


class TestCatalogModelCounts:
    def test_column_count_is_seven(self, qtbot, wait_for_action):
        cat = _create_catalogue(wait_for_action)
        model = _get_catalog_model(cat.entity.uuid, qtbot)

        assert model.columnCount() == 7

        _unparent_driver()

    def test_row_count_starts_at_zero(self, qtbot, wait_for_action):
        cat = _create_catalogue(wait_for_action)
        model = _get_catalog_model(cat.entity.uuid, qtbot)

        assert model.rowCount() == 0

        _unparent_driver()

    def test_adding_events_updates_row_count(self, qtbot, wait_for_action):
        cat = _create_catalogue(wait_for_action)
        evt1 = _create_event(wait_for_action)
        evt2 = _create_event(wait_for_action, start=dt.datetime(2021, 1, 1),
                             stop=dt.datetime(2021, 1, 2))

        model = _get_catalog_model(cat.entity.uuid, qtbot)

        wait_for_action(AddEventsToCatalogueAction(
            None, [evt1.entity.uuid, evt2.entity.uuid], cat.entity.uuid
        ))
        qtbot.wait(100)

        assert model.rowCount() == 2

        _unparent_driver()


class TestCatalogModelIndexFromUuid:
    def test_returns_correct_index(self, qtbot, wait_for_action):
        cat = _create_catalogue(wait_for_action)
        evt = _create_event(wait_for_action)

        model = _get_catalog_model(cat.entity.uuid, qtbot)

        wait_for_action(AddEventsToCatalogueAction(
            None, [evt.entity.uuid], cat.entity.uuid
        ))
        qtbot.wait(100)

        index = model.index_from_uuid(evt.entity.uuid)
        assert index.isValid()
        assert index.row() == 0

        _unparent_driver()

    def test_returns_invalid_for_unknown_uuid(self, qtbot, wait_for_action):
        cat = _create_catalogue(wait_for_action)
        model = _get_catalog_model(cat.entity.uuid, qtbot)

        index = model.index_from_uuid('00000000-dead-beef-0000-000000000000')
        assert not index.isValid()

        _unparent_driver()


class TestCatalogModelData:
    def test_display_role_returns_values(self, qtbot, wait_for_action):
        cat = _create_catalogue(wait_for_action)
        evt = _create_event(wait_for_action, author='alice')

        model = _get_catalog_model(cat.entity.uuid, qtbot)

        wait_for_action(AddEventsToCatalogueAction(
            None, [evt.entity.uuid], cat.entity.uuid
        ))
        qtbot.wait(100)

        # author is column 2
        index = model.index(0, 2, QModelIndex())
        assert model.data(index, Qt.DisplayRole) == 'alice'

        _unparent_driver()

    def test_uuid_data_role_returns_uuid(self, qtbot, wait_for_action):
        cat = _create_catalogue(wait_for_action)
        evt = _create_event(wait_for_action)

        model = _get_catalog_model(cat.entity.uuid, qtbot)

        wait_for_action(AddEventsToCatalogueAction(
            None, [evt.entity.uuid], cat.entity.uuid
        ))
        qtbot.wait(100)

        index = model.index(0, 0, QModelIndex())
        assert model.data(index, UUIDDataRole) == evt.entity.uuid

        _unparent_driver()

    def test_invalid_index_returns_none(self, qtbot, wait_for_action):
        cat = _create_catalogue(wait_for_action)
        model = _get_catalog_model(cat.entity.uuid, qtbot)

        assert model.data(QModelIndex(), Qt.DisplayRole) is None

        _unparent_driver()
