"""Top-level package for Time series catalogue - GUI."""

__author__ = """Patrick Boettcher"""
__email__ = 'p@yai.se'
__version__ = '0.2.0'

from PySide6 import QtWidgets, QtGui
from PySide6 import QtCore

from typing import Union
import datetime as dt
from pathlib import Path
import os

import tscat

from .model import CatalogueModel, EventModel, UUIDRole

from .edit import EntityEditView
from .state import AppState

from .undo import NewCatalogue, MoveEntityToTrash, RestoreEntityFromTrash, DeletePermanently, NewEvent, Import

from .utils.helper import get_entity_from_uuid_safe


class _TrashAlwaysTopOrBottomSortFilterModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)

    def lessThan(self, source_left: Union[QtCore.QModelIndex, QtCore.QPersistentModelIndex],
                 source_right: Union[QtCore.QModelIndex, QtCore.QPersistentModelIndex]) -> bool:
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
        self.events_view.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)

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
                    self.state.updated('active_select', tscat._Event, uuid)
            else:
                self.state.updated('active_select', tscat._Event, None)

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
        self.catalogues_view.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)

        self.catalogues_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        def current_catalogue_activated(index: QtCore.QModelIndex) -> None:
            if self.programmatic_select:
                return

            if index.isValid():
                uuid = self.catalogue_sort_filter_model.data(index, UUIDRole)
                self.state.updated('active_select', tscat._Catalogue, uuid)
            else:
                self.state.updated('active_select', tscat._Catalogue, None)

        def current_catalogue_changed(selected: QtCore.QModelIndex, deselected: QtCore.QModelIndex):
            current_catalogue_activated(selected)


        self.catalogues_view.selectionModel().currentChanged.connect(current_catalogue_changed,
                                                                     type=QtCore.Qt.DirectConnection)
        self.catalogues_view.clicked.connect(current_catalogue_activated)

        self.catalogues_view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)

        def state_changed(action, type, uuid):
            if action in ['changed', 'moved', 'inserted', 'deleted', 'active_select', 'passive_select']:
                if type == tscat._Catalogue:
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
                self.new_event_action.setEnabled(False)
                self.export_action.setEnabled(False)

                if uuid:
                    entity = get_entity_from_uuid_safe(uuid)
                    if entity.is_removed():
                        self.restore_from_trash_action.setEnabled(True)
                    else:
                        self.move_to_trash_action.setEnabled(True)
                    self.delete_action.setEnabled(True)
                    self.new_event_action.setEnabled(True)
                    self.export_action.setEnabled(True)

        self.state.state_changed.connect(state_changed)

        hlayout = QtWidgets.QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.addWidget(QtWidgets.QLabel('Filter:'))
        catalogue_filter = QtWidgets.QLineEdit()
        catalogue_filter.textChanged.connect(lambda t: self.catalogue_sort_filter_model.setFilterRegularExpression(t))

        hlayout.addWidget(catalogue_filter)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(hlayout)
        layout.addWidget(self.catalogues_view)

        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(layout)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        splitter.addWidget(left_widget)
        splitter.addWidget(self.splitter_right)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QtWidgets.QToolBar()

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogNewFolder),
                               "Create Catalogue", self)

        def new_catalogue():
            self.state.push_undo_command(NewCatalogue)

        action.triggered.connect(new_catalogue)
        toolbar.addAction(action)

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon),
                               "Create Event", self)

        def new_event():
            self.state.push_undo_command(NewEvent)

        action.triggered.connect(new_event)
        action.setEnabled(False)
        toolbar.addAction(action)

        self.new_event_action = action

        toolbar.addSeparator()
        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton), "Save To Disk",
                               self)

        action.triggered.connect(self.save)
        toolbar.addAction(action)
        action.setEnabled(False)
        self.state.undo_stack_clean_changed.connect(lambda state, a=action: a.setEnabled(not state))

        toolbar.addSeparator()
        undo_action, redo_action = self.state.create_undo_redo_action()

        undo_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowBack))
        undo_action.setShortcut(QtCore.Qt.CTRL | QtCore.Qt.Key_Z)
        toolbar.addAction(undo_action)

        redo_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowForward))
        redo_action.setShortcut(QtCore.Qt.CTRL | QtCore.Qt.SHIFT | QtCore.Qt.Key_Z)
        toolbar.addAction(redo_action)

        toolbar.addSeparator()

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon), "Move to Trash", self)

        def trash():
            self.state.push_undo_command(MoveEntityToTrash)

        action.triggered.connect(trash)
        action.setEnabled(False)
        toolbar.addAction(action)
        self.move_to_trash_action = action

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_DialogResetButton),
                               "Restore from Trash", self)

        def restore():
            self.state.push_undo_command(RestoreEntityFromTrash)

        action.triggered.connect(restore)
        action.setEnabled(False)
        toolbar.addAction(action)
        self.restore_from_trash_action = action

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserStop), "Delete permanently",
                               self)

        def delete():
            self.state.push_undo_command(DeletePermanently)

        action.triggered.connect(delete)
        action.setEnabled(False)
        toolbar.addAction(action)
        self.delete_action = action

        toolbar.addSeparator()

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_DialogRetryButton), "Refresh",
                               self)

        def refresh():
            current_selection = self.state.select_state()
            self.catalogue_model.reset()
            self.events_model.reset()

            if current_selection.type == tscat._Event:
                self.state.updated('passive_select', tscat._Catalogue, current_selection.active_catalogue)
            self.state.updated('active_select', current_selection.type, current_selection.active)

        action.triggered.connect(refresh)
        toolbar.addAction(action)

        self.refresh_action = action

        toolbar.addSeparator()

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowUp), "Import Catalogue",
                               self)

        def import_from_file():
            filename, filetype = QtWidgets.QFileDialog.getOpenFileName(
                self.activateWindow(),
                "Select a catalogue file to be imported",
                str(Path.home()),
                "JSON Document (*.json)")
            if filename == '':
                return

            try:
                with open(filename) as f:
                    data = f.read()
                    import_dict = tscat.canonicalize_json_import(data)
                    self.state.push_undo_command(Import, filename, import_dict)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self.activateWindow(),
                                               "Catalogue import",
                                               f"The selected file could not be imported: '{e}'.")

        action.triggered.connect(import_from_file)
        toolbar.addAction(action)

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowDown), "Export Catalogue",
                               self)

        def export_to_file():
            filename, filetype = QtWidgets.QFileDialog.getSaveFileName(
                self.activateWindow(),
                "Specify the filename for exporting the selected catalogue",
                str(Path.home()),
                "JSON Document (*.json)")
            if filename == '':
                return
            split_filename = os.path.splitext(filename)
            if split_filename[1] != '.json':
                filename = split_filename[0] + '.json'

            try:
                with open(filename, 'w+') as f:
                    catalogue = get_entity_from_uuid_safe(self.state.select_state().active_catalogue)
                    json = tscat.export_json(catalogue)
                    f.write(json)
                QtWidgets.QMessageBox.information(self.activateWindow(),
                                                  "Catalogue export",
                                                  "The selected catalogue has been successfully exported")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self.activateWindow(),
                                               "Catalogue export",
                                               f"The selected catalogue could not be exported to {filename} due to '{e}'.")

        action.triggered.connect(export_to_file)
        action.setEnabled(False)
        toolbar.addAction(action)

        self.export_action = action

        layout.addWidget(toolbar)
        layout.addWidget(splitter)
        self.setLayout(layout)

    def _external_signal_emission(self, action: str, type: Union[tscat._Catalogue, tscat._Event], uuid: str):
        if action == "active_select":
            if type == tscat._Catalogue:
                self.catalogue_selected.emit(uuid)
            else:
                self.event_selected.emit(uuid)

        elif action == 'changed':
            if type == tscat._Catalogue:
                self.catalogue_changed.emit(uuid)
            else:
                self.event_changed.emit(uuid)

    def update_event_range(self, uuid: str, start: dt.datetime, stop: dt.datetime) -> None:
        event = get_entity_from_uuid_safe(uuid)
        event.start = start
        event.stop = stop
        self.state.updated('changed', tscat._Event, uuid)

    def create_event(self, start: dt.datetime, stop: dt.datetime, author: str, catalogue_uuid: str) -> tscat._Event:
        catalogue = get_entity_from_uuid_safe(catalogue_uuid)
        with tscat.Session() as s:
            event = s.create_event(start, stop, author)
            tscat.add_events_to_catalogue(catalogue, event)

        self.state.updated('inserted', tscat._Event, event.uuid)

        return event

    def move_to_trash(self, uuid: str) -> None:
        entity = get_entity_from_uuid_safe(uuid)
        entity.remove()
        self.state.updated('moved', type(entity), uuid)

    def save(self) -> None:
        tscat.save()
        self.state.set_undo_stack_clean()
