"""Top-level package for Time series catalogue - GUI."""

__author__ = """Patrick Boettcher"""
__email__ = 'p@yai.se'
__version__ = '0.1.0'

from PySide2 import QtWidgets
from PySide2 import QtCore

from typing import Union
import datetime as dt

import tscat

from .model import CatalogueModel, EventModel, UUIDRole

from .edit import EntityEditView
from .state import AppState

from .undo import NewCatalogue, MoveEntityToTrash, RestoreEntityFromTrash, DeletePermanently

from .utils.helper import get_entity_from_uuid_safe


class _TrashAlwaysTopOrBottomSortFilterModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)

    def lessThan(self, source_left: QtCore.QModelIndex, source_right: QtCore.QModelIndex) -> bool:
        left = self.sourceModel().data(source_left)
        right = self.sourceModel().data(source_right)

        if left == 'Trash':
            return False
        elif right == 'Trash':
            return True
        else:
            return left.lower() < right.lower()


class TSCatGUI(QtWidgets.QWidget):
    event_selected = QtCore.Signal(str)
    catalogue_selected = QtCore.Signal(str)
    event_changed = QtCore.Signal(str)
    catalogue_changed = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.state = AppState()

        self.state.state_changed.connect(self._external_signal_emission)

        self.events_model = EventModel(self.state, self)
        self.events_sort_model = QtCore.QSortFilterProxyModel()
        self.events_sort_model.setSourceModel(self.events_model)

        self.events_view = QtWidgets.QTableView()
        self.events_view.setMinimumSize(1000, 500)
        self.events_view.setSortingEnabled(True)
        self.events_view.sortByColumn(-1, QtCore.Qt.SortOrder.AscendingOrder)

        self.events_view.setModel(self.events_sort_model)
        self.events_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.events_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

        self.programmatic_select = False

        def current_event_changed(selected: QtCore.QModelIndex, deselected: QtCore.QModelIndex):
            if self.programmatic_select:
                return
            if selected.isValid():
                if not deselected.isValid() or deselected.row() != selected.row():
                    uuid = self.events_sort_model.data(selected, UUIDRole)
                    self.state.updated('active_select', tscat.Event, uuid)
            else:
                self.state.updated('active_select', tscat.Event, None)

        self.events_view.selectionModel().currentChanged.connect(current_event_changed,
                                                                 type=QtCore.Qt.DirectConnection)

        self.edit_view = EntityEditView(self.state, self)

        self.splitter_right = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        self.splitter_right.addWidget(self.events_view)
        self.splitter_right.addWidget(self.edit_view)

        self.catalogue_model = CatalogueModel(self)

        self.catalogues_view = QtWidgets.QTreeView()
        self.catalogues_view.setMinimumSize(300, 900)
        self.catalogues_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.catalogue_sort_filter_model = _TrashAlwaysTopOrBottomSortFilterModel()
        self.catalogue_sort_filter_model.setSourceModel(self.catalogue_model)
        self.catalogue_sort_filter_model.setRecursiveFilteringEnabled(True)
        self.catalogue_sort_filter_model.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)

        self.catalogues_view.setModel(self.catalogue_sort_filter_model)
        self.catalogues_view.setSortingEnabled(True)
        self.catalogues_view.sortByColumn(-1, QtCore.Qt.SortOrder.AscendingOrder)

        self.catalogues_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        def current_catalogue_changed(selected: QtCore.QModelIndex, deselected: QtCore.QModelIndex):
            if self.programmatic_select:
                return

            if selected.isValid():
                uuid = self.catalogue_sort_filter_model.data(selected, UUIDRole)
                self.state.updated('active_select', tscat.Catalogue, uuid)
            else:
                self.state.updated('active_select', tscat.Catalogue, None)

        self.catalogues_view.selectionModel().currentChanged.connect(current_catalogue_changed,
                                                                     type=QtCore.Qt.DirectConnection)

        self.catalogues_view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)

        def state_changed(action, type, uuid):
            if action in ['changed', 'moved', 'inserted', 'deleted', 'active_select', 'passive_select']:
                if type == tscat.Catalogue:
                    if action not in ['active_select', 'passive_select']:
                        self.catalogue_model.reset()

                    index = self.catalogue_model.index_from_uuid(uuid)
                    index = self.catalogue_sort_filter_model.mapFromSource(index)
                    self.programmatic_select = True
                    self.catalogues_view.setCurrentIndex(index)
                    self.programmatic_select = False
                else:
                    if action not in ['active_select', 'passive_select']:
                        self.events_model.reset()
                    index = self.events_model.index_from_uuid(uuid)
                    index = self.events_sort_model.mapFromSource(index)
                    self.programmatic_select = True
                    self.events_view.setCurrentIndex(index)
                    self.programmatic_select = False

            if action == 'active_select':
                self.move_to_trash_action.setEnabled(False)
                self.restore_from_trash_action.setEnabled(False)
                self.delete_action.setEnabled(False)

                if uuid:
                    entity = get_entity_from_uuid_safe(uuid)
                    if entity.is_removed():
                        self.restore_from_trash_action.setEnabled(True)
                    else:
                        self.move_to_trash_action.setEnabled(True)
                    self.delete_action.setEnabled(True)

        self.state.state_changed.connect(state_changed)

        layout = QtWidgets.QVBoxLayout()
        layout.setMargin(0)
        layout.addWidget(self.catalogues_view)

        hlayout = QtWidgets.QHBoxLayout()
        hlayout.setMargin(0)
        hlayout.addWidget(QtWidgets.QLabel('Filter:'))
        catalogue_filter = QtWidgets.QLineEdit()
        catalogue_filter.textChanged.connect(lambda t: self.catalogue_sort_filter_model.setFilterRegExp(t))

        hlayout.addWidget(catalogue_filter)
        layout.addLayout(hlayout)

        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(layout)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        splitter.addWidget(left_widget)
        splitter.addWidget(self.splitter_right)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QtWidgets.QToolBar()

        action = QtWidgets.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogNewFolder),
                                   "Create Catalogue", self)

        def new_catalogue():
            self.state.push_undo_command(NewCatalogue)

        action.triggered.connect(new_catalogue)
        toolbar.addAction(action)

        action = QtWidgets.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton), "Save To Disk",
                                   self)

        action.triggered.connect(self.save)
        toolbar.addAction(action)
        action.setEnabled(False)
        self.state.undo_stack_clean_changed.connect(lambda state, a=action: a.setEnabled(not state))

        undo_action, redo_action = self.state.create_undo_redo_action()

        undo_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowBack))
        toolbar.addAction(undo_action)

        redo_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowForward))
        toolbar.addAction(redo_action)

        action = QtWidgets.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon), "Move to Trash", self)

        def trash():
            self.state.push_undo_command(MoveEntityToTrash)

        action.triggered.connect(trash)
        action.setEnabled(False)
        toolbar.addAction(action)
        self.move_to_trash_action = action

        action = QtWidgets.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_DialogResetButton),
                                   "Restore from Trash", self)

        def restore():
            self.state.push_undo_command(RestoreEntityFromTrash)

        action.triggered.connect(restore)
        action.setEnabled(False)
        toolbar.addAction(action)
        self.restore_from_trash_action = action

        action = QtWidgets.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserStop), "Delete permanently",
                                   self)

        def delete():
            self.state.push_undo_command(DeletePermanently)

        action.triggered.connect(delete)
        action.setEnabled(False)
        toolbar.addAction(action)
        self.delete_action = action

        layout.addWidget(toolbar)
        layout.addWidget(splitter)
        self.setLayout(layout)

    def _external_signal_emission(self, action: str, type: Union[tscat.Catalogue, tscat.Event], uuid: str):
        if action == "active_select":
            if type == tscat.Catalogue:
                self.catalogue_selected.emit(uuid)
            else:
                self.event_selected.emit(uuid)

        elif action == 'changed':
            if type == tscat.Catalogue:
                self.catalogue_changed.emit(uuid)
            else:
                self.event_changed.emit(uuid)

    def update_event_range(self, uuid: str, start: dt.datetime, stop: dt.datetime) -> None:
        event = get_entity_from_uuid_safe(uuid)
        event.start = start
        event.stop = stop
        self.state.updated('changed', tscat.Event, uuid)

    def create_event(self, start: dt.datetime, stop: dt.datetime, author: str, catalogue_uuid: str) -> tscat.Event:
        event = tscat.Event(start, stop, author)
        catalogue = get_entity_from_uuid_safe(catalogue_uuid)
        catalogue.add_events(event)

        self.state.updated('inserted', tscat.Event, event.uuid)

        return event

    def move_to_trash(self, uuid: str) -> None:
        entity = get_entity_from_uuid_safe(uuid)
        entity.remove()
        self.state.updated('moved', type(entity), uuid)

    def save(self) -> None:
        tscat.save()
        self.state.set_undo_stack_clean()
