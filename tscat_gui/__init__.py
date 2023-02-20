"""Top-level package for Time series catalogue - GUI."""

__author__ = """Patrick Boettcher"""
__email__ = 'p@yai.se'
__version__ = '0.2.0'

from PySide6 import QtWidgets, QtGui
from PySide6 import QtCore

from typing import Union, Sequence, Optional, Type
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
    events_selected = QtCore.Signal(list)
    catalogues_selected = QtCore.Signal(list)
    events_changed = QtCore.Signal(list)
    catalogues_changed = QtCore.Signal(list)

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
        self.events_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.events_view.setDragEnabled(True)
        self.events_view.setDragDropMode(QtWidgets.QTreeView.DragDropMode.DragOnly)

        self.programmatic_select = False

        def current_event_changed(_: QtCore.QModelIndex, __: QtCore.QModelIndex):
            if self.programmatic_select:
                return

            uuids = [index.data(UUIDRole) for index in self.events_view.selectedIndexes() if index.column() == 0]
            self.state.updated('active_select', tscat._Event, uuids)

        self.events_view.selectionModel().selectionChanged.connect(current_event_changed,
                                                                   type=QtCore.Qt.DirectConnection)

        self.edit_view = EntityEditView(self.state, self)

        self.splitter_right = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        self.splitter_right.addWidget(self.events_view)
        self.splitter_right.addWidget(self.edit_view)

        self.catalogue_model = CatalogueModel(self.state, self)

        self.catalogues_view = QtWidgets.QTreeView()
        self.catalogues_view.setMinimumSize(300, 900)
        self.catalogues_view.setDragEnabled(True)
        self.catalogues_view.setDragDropMode(QtWidgets.QTreeView.DragDropMode.DragDrop)
        self.catalogues_view.setAcceptDrops(True)
        self.catalogues_view.setDropIndicatorShown(True)
        self.catalogues_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.catalogue_sort_filter_model = _TrashAlwaysTopOrBottomSortFilterModel()
        self.catalogue_sort_filter_model.setSourceModel(self.catalogue_model)
        self.catalogue_sort_filter_model.setRecursiveFilteringEnabled(True)
        self.catalogue_sort_filter_model.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)

        self.catalogues_view.setModel(self.catalogue_sort_filter_model)
        self.catalogues_view.setSortingEnabled(True)
        self.catalogues_view.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)

        self.catalogues_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        def catalogue_selection_changed(_: QtCore.QItemSelection, __: QtCore.QItemSelection) -> None:
            if self.programmatic_select:
                return

            uuids = [index.data(UUIDRole) for index in self.catalogues_view.selectedIndexes()]
            self.state.updated('active_select', tscat._Catalogue, uuids)

        self.catalogues_view.selectionModel().selectionChanged.connect(catalogue_selection_changed,
                                                                       type=QtCore.Qt.DirectConnection)

        def state_changed(action: str, type: Union[Type[tscat._Catalogue], Type[tscat._Event]],
                          uuids: Sequence[str]) -> None:
            if action in ['changed', 'moved', 'inserted', 'deleted', 'active_select', 'passive_select']:
                if type == tscat._Catalogue:
                    if action not in ['active_select', 'passive_select']:
                        self.catalogue_model.reset()

                    indexes = list(map(self.catalogue_model.index_from_uuid, uuids))
                    indexes = list(map(self.catalogue_sort_filter_model.mapFromSource, indexes))
                    self.programmatic_select = True
                    self.catalogues_view.clearSelection()
                    for index in indexes:
                        self.catalogues_view.selectionModel().select(index,
                                                                     QtCore.QItemSelectionModel.SelectionFlag.Select)
                    self.programmatic_select = False
                else:
                    if action not in ['active_select', 'passive_select']:
                        self.events_model.reset()

                    indexes = list(map(self.events_model.index_from_uuid, uuids))
                    indexes = list(map(self.events_sort_model.mapFromSource, indexes))
                    self.programmatic_select = True
                    self.events_view.clearSelection()
                    for index in indexes:
                        self.events_view.selectionModel().select(index,
                                                                 QtCore.QItemSelectionModel.SelectionFlag.Select |
                                                                 QtCore.QItemSelectionModel.SelectionFlag.Rows)
                    self.programmatic_select = False

            if action == 'active_select':
                self.move_to_trash_action.setEnabled(False)
                self.restore_from_trash_action.setEnabled(False)
                self.delete_action.setEnabled(False)
                self.new_event_action.setEnabled(False)
                self.export_action.setEnabled(False)

                if uuids:
                    if len(uuids) == 1:
                        self.new_event_action.setEnabled(True)

                    enable_restore = False
                    enable_move_to_trash = False
                    for entity in map(get_entity_from_uuid_safe, uuids):
                        if entity.is_removed():
                            enable_restore |= True
                        else:
                            enable_move_to_trash |= True

                    self.restore_from_trash_action.setEnabled(enable_restore)
                    self.move_to_trash_action.setEnabled(enable_move_to_trash)
                    self.delete_action.setEnabled(True)
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
                self.state.updated('passive_select', tscat._Catalogue, current_selection.selected_catalogues)
            self.state.updated('active_select', current_selection.type, current_selection.selected)

        action.triggered.connect(refresh)
        toolbar.addAction(action)

        self.refresh_action = action

        toolbar.addSeparator()

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowUp), "Import Catalogue",
                               self)

        def import_from_file():
            filename, filetype = QtWidgets.QFileDialog.getOpenFileName(
                self,
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
                QtWidgets.QMessageBox.critical(self,
                                               "Catalogue import",
                                               f"The selected file could not be imported: '{e}'.")

        action.triggered.connect(import_from_file)
        toolbar.addAction(action)

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowDown),
                               "Export Catalogue",
                               self)

        def export_to_file():
            filename, filetype = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Specify the filename for exporting the selected catalogues",
                str(Path.home()),
                "JSON Document (*.json)")
            if filename == '':
                return
            split_filename = os.path.splitext(filename)
            if split_filename[1] != '.json':
                filename = split_filename[0] + '.json'

            try:
                with open(filename, 'w+') as f:
                    catalogues = [get_entity_from_uuid_safe(uuid)
                                  for uuid in self.state.select_state().selected_catalogues]
                    json = tscat.export_json(catalogues)
                    f.write(json)
                QtWidgets.QMessageBox.information(self,
                                                  "Catalogue export",
                                                  "The selected catalogues have been successfully exported")
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Catalogue export",
                    f"The selected catalogues could not be exported to {filename} due to '{e}'.")

        action.triggered.connect(export_to_file)
        action.setEnabled(False)
        toolbar.addAction(action)

        self.export_action = action

        layout.addWidget(toolbar)
        layout.addWidget(splitter)
        self.setLayout(layout)

    def _external_signal_emission(self, action: str, type: Union[tscat._Catalogue, tscat._Event], uuids: Sequence[str]):
        if action == "active_select":
            if type == tscat._Catalogue:
                self.catalogues_selected.emit(uuids)
            else:
                self.events_selected.emit(uuids)

        elif action == 'changed':
            if type == tscat._Catalogue:
                self.catalogues_changed.emit(uuids)
            else:
                self.events_changed.emit(uuids)

    def update_event_range(self, uuid: str, start: dt.datetime, stop: dt.datetime) -> None:
        event = get_entity_from_uuid_safe(uuid)
        event.start = start
        event.stop = stop
        self.state.updated('changed', tscat._Event, [uuid])

    def create_event(self, start: dt.datetime, stop: dt.datetime, author: str, catalogue_uuid: str) -> tscat._Event:
        catalogue = get_entity_from_uuid_safe(catalogue_uuid)
        assert isinstance(catalogue, tscat._Catalogue)
        with tscat.Session() as s:
            event = s.create_event(start, stop, author)
            tscat.add_events_to_catalogue(catalogue, event)

        self.state.updated('inserted', tscat._Event, [event.uuid])

        return event

    def move_to_trash(self, uuid: str) -> None:
        entity = get_entity_from_uuid_safe(uuid)
        entity.remove()
        self.state.updated('moved', type(entity), [uuid])

    def save(self) -> None:
        tscat.save()
        self.state.set_undo_stack_clean()
