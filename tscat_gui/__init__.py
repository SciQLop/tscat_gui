"""Top-level package for Time series catalogue - GUI."""

__author__ = """Patrick Boettcher"""
__email__ = 'p@yai.se'
__version__ = '0.5.0'

import datetime as dt
import os
from pathlib import Path
from typing import List, Optional, Sequence, Type, Union, cast

import itertools
import sys
from PySide6 import QtCore, QtGui, QtWidgets

from tscat import _Catalogue, _Event
from .edit import EntityEditView
from .model_base.constants import EntityRole, UUIDDataRole
from .state import AppState
from .tscat_driver.actions import Action, AddEventsToCatalogueAction, CanonicalizeImportAction, CreateEntityAction, \
    DeleteAttributeAction, MoveToTrashAction, SaveAction, SetAttributeAction
from .undo import AddEventsToCatalogue, CreateOrSetCataloguePath, DeletePermanently, Import, MoveEntityToTrash, \
    NewCatalogue, NewEvent, RestoreEntityFromTrash, SetAttributeValue
from .utils.import_export import export_to_json, export_to_votable, import_json, import_votable


class _TSCatConcatenateTablePM(QtCore.QConcatenateTablesProxyModel):
    def __init__(self, parent: Optional[QtCore.QObject]):
        super().__init__(parent)

    def indexes_from_uuid(self, uuid: str) -> List[QtCore.QModelIndex]:
        from .tscat_driver.catalog_model import CatalogModel

        indexes = []
        for model in self.sourceModels():
            assert isinstance(model, CatalogModel)
            indexes.append(model.index_from_uuid(uuid))

        indexes = list(map(self.mapFromSource, indexes))
        return indexes


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

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.state = AppState()

        from .tscat_driver.driver import tscat_driver
        tscat_driver.setParent(self)
        # used a state-variable to differentiate user-induced selections of entities vs programmatically ones
        # needs direct-connected signal to work properly
        self.programmatic_select = False

        self.__setup_ui()
        from .tscat_driver.model import tscat_model
        tscat_model.action_done.connect(self._external_signal_emission_changed)

        self.state.state_changed.connect(self.__state_changed)

    def __state_changed(self, action: str, type: Union[Type[_Catalogue], Type[_Event]],
                        uuids: Sequence[str]) -> None:
        if action in ['active_select', 'passive_select']:
            if type == _Catalogue:
                indexes = list(map(self.catalogue_model.index_from_uuid, uuids))
                indexes = list(map(self.catalogue_sort_filter_model.mapFromSource, indexes))

                if set(self.catalogues_view.selectedIndexes()) != set(indexes):
                    self.programmatic_select = True
                    self.catalogues_view.selectionModel().clear()
                    for index in indexes:
                        self.catalogues_view.selectionModel().select(index,
                                                                     QtCore.QItemSelectionModel.SelectionFlag.Select)
                    self.programmatic_select = False

                current_models = set(self.event_model.sourceModels())
                from .tscat_driver.model import tscat_model
                new_models = set(map(tscat_model.catalog, uuids))

                # temporarily disconnect the selectionChanged signal to avoid unnecessary updates
                self.events_view.selectionModel().selectionChanged.disconnect(  # type: ignore
                    self.__current_event_changed)

                for i in current_models - new_models:
                    self.event_model.removeSourceModel(i)
                for i in new_models - current_models:
                    self.event_model.addSourceModel(i)

                self.events_view.selectionModel().selectionChanged.connect(  # type: ignore
                    self.__current_event_changed, type=QtCore.Qt.DirectConnection)  # type: ignore

            else:
                indexes = list(itertools.chain(*list(map(self.event_model.indexes_from_uuid, uuids))))
                indexes = list(map(self.events_sort_model.mapFromSource, indexes))

                current_selected_indexes_first_column = set(index for index in self.events_view.selectedIndexes()
                                                            if index.column() == 0)
                if current_selected_indexes_first_column != set(indexes):
                    self.programmatic_select = True
                    self.events_view.selectionModel().clear()
                    for index in indexes:
                        self.events_view.selectionModel().select(index,
                                                                 QtCore.QItemSelectionModel.SelectionFlag.Select |
                                                                 QtCore.QItemSelectionModel.SelectionFlag.Rows)
                    self.programmatic_select = False

            if action == 'active_select':
                self._enable_disable_symbol_actions(uuids)

    def _enable_disable_symbol_actions(self, uuids: Sequence[str]) -> None:
        # Enable/disable actions based on the current selection
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

            from .tscat_driver.model import tscat_model
            for entity in tscat_model.entities_from_uuids(uuids):
                if entity.is_removed():
                    enable_restore |= True
                else:
                    enable_move_to_trash |= True

            self.restore_from_trash_action.setEnabled(enable_restore)
            self.move_to_trash_action.setEnabled(enable_move_to_trash)
            self.delete_action.setEnabled(True)
            self.export_action.setEnabled(True)

    def __current_event_changed(self, _: QtCore.QModelIndex, __: QtCore.QModelIndex) -> None:
        if not self.programmatic_select:
            uuids = [index.data(UUIDDataRole) for index in self.events_view.selectedIndexes() if index.column() == 0]
            self.state.updated('active_select', _Event, uuids)
            self.events_selected.emit(uuids)

    def __catalogue_selection_changed(self, _: QtCore.QItemSelection, __: QtCore.QItemSelection) -> None:
        if not self.programmatic_select:
            catalogue_uuids = []
            selected_indexes = self.catalogues_view.selectedIndexes()
            for index in selected_indexes:
                if index.data(EntityRole) is not None:  # if not a folder
                    catalogue_uuids.append(index.data(UUIDDataRole))

            if selected_indexes:
                self.state.set_catalogue_path(self.catalogue_model.current_path(selected_indexes[-1]))
            if catalogue_uuids:
                self.state.updated('active_select', _Catalogue, catalogue_uuids)
                self.catalogues_selected.emit(catalogue_uuids)

    def __create_undo_redo_action_menu_on_toolbutton(self,
                                                     index_range: range,
                                                     toolbutton: QtWidgets.QToolButton,
                                                     index_inc: int,
                                                     more_items: bool,
                                                     more_items_text: str) -> None:

        menu = QtWidgets.QMenu(toolbutton)
        for i in index_range:
            action = QtGui.QAction(f'{self.state.undo_stack().command(i).text()}', menu)
            action.triggered[bool].connect(lambda state, _i=i, inc=index_inc:  # type: ignore
                                           self.state.undo_stack().setIndex(_i + inc))
            menu.addAction(action)

        if more_items:
            more = QtGui.QAction(more_items_text, menu)
            more.setEnabled(False)
            menu.addAction(more)

        toolbutton.setMenu(menu)

    def __undo_redo_index_changed(self, index: int) -> None:
        max_action_count = 10

        first_index = max(0, index - max_action_count)
        self.__create_undo_redo_action_menu_on_toolbutton(
            range(index - 1, first_index - 1, -1),
            self.undo_toolbar_button, 0, first_index != 0,
            f'{first_index} more undo actions')

        last_index = min(self.state.undo_stack().count(), index + max_action_count)
        self.__create_undo_redo_action_menu_on_toolbutton(
            range(index, last_index), self.redo_toolbar_button, 1,
            last_index != self.state.undo_stack().count(),
            f'{self.state.undo_stack().count() - last_index} more redo actions')

    def __refresh_current_selection(self) -> None:
        current_selection = self.state.select_state()
        if current_selection.type == _Event:
            self.state.updated('passive_select', _Catalogue, current_selection.selected_catalogues)
        self.state.updated('active_select', current_selection.type, current_selection.selected)

    def __import_from_file(self) -> None:
        filename, filetype = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select a catalogue file to be imported",
            str(Path.home()),
            "JSON Document (*.json);;VOTable (*.xml)")

        if filename != '':
            if filetype == 'VOTable (*.xml)':
                result = import_votable(filename, self.state)
            elif filetype == 'JSON Document (*.json)':
                result = import_json(filename, self.state)
            else:
                result = ValueError(f"Unknown filetype '{filetype}'")

            if result:
                QtWidgets.QMessageBox.critical(self,
                                               "Catalogue import",
                                               f"The selected file could not be imported: '{result}'.")

    def __export_to_file(self) -> None:
        filename, filetype = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Specify the filename for exporting the selected catalogues",
            str(Path.home()),
            "JSON Document (*.json);;VOTable (*.xml)")
        if filename != '':
            if filetype == 'VOTable (*.xml)':
                filename = os.path.splitext(filename)[0] + '.xml'

                result = export_to_votable(filename, self.state.select_state().selected_catalogues)
            elif filetype == 'JSON Document (*.json)':
                filename = os.path.splitext(filename)[0] + '.json'
                result = export_to_json(filename, self.state.select_state().selected_catalogues)
            else:
                result = ValueError(f"Unknown filetype '{filetype}'")

            if result:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Catalogue export",
                    f"The selected catalogues could not be exported to {filename} due to '{result}'.")
            else:
                QtWidgets.QMessageBox.information(self,
                                                  "Catalogue export",
                                                  "The selected catalogues have been successfully exported")

    def __new_folder(self) -> None:
        # use QInputDialog to get the new folder name
        folder_name, ok = QtWidgets.QInputDialog.getText(self, 'Create Folder', 'Folder name:')

        if ok:
            new_path = self.state.current_catalogue_path() + [folder_name]
            node = self.catalogue_model.node_from_path(new_path, True)
            index = self.catalogue_model._index_from_node(node)
            index = self.catalogue_sort_filter_model.mapFromSource(index)

            self.catalogues_view.selectionModel().clear()
            self.catalogues_view.selectionModel().select(index,
                                                         QtCore.QItemSelectionModel.SelectionFlag.Select)
            # expand the new folder
            self.catalogues_view.expand(index)

    def __setup_ui(self) -> None:

        # Event Model and View
        self.event_model = _TSCatConcatenateTablePM(self)

        self.events_sort_model = QtCore.QSortFilterProxyModel()
        self.events_sort_model.setSourceModel(self.event_model)

        self.events_view = QtWidgets.QTableView()
        self.events_view.setMinimumSize(1000, 500)
        self.events_view.setSortingEnabled(True)
        self.events_view.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)

        self.events_view.setModel(self.events_sort_model)
        self.events_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.events_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)  # type: ignore
        self.events_view.setDragEnabled(True)
        self.events_view.setDragDropMode(QtWidgets.QTreeView.DragDropMode.DragOnly)

        self.events_view.selectionModel().selectionChanged.connect(  # type: ignore
            self.__current_event_changed, type=QtCore.Qt.DirectConnection)  # type: ignore

        # Edit View
        self.edit_view = EntityEditView(self.state, self)

        # Event/Edit Vertial Splitter
        self.splitter_right = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)  # type: ignore
        self.splitter_right.addWidget(self.events_view)
        self.splitter_right.addWidget(self.edit_view)

        # Catalogue Model and View

        from .tscat_driver.model import tscat_model
        self.catalogue_model = tscat_model.tscat_root()
        self.catalogue_model.events_dropped_on_catalogue.connect(lambda uuid, event_list:
                                                                 self.state.push_undo_command(AddEventsToCatalogue,
                                                                                              uuid,
                                                                                              event_list))
        self.catalogue_model.catalogues_dropped_on_folder.connect(
            lambda catalogues_paths: self.state.push_undo_command(CreateOrSetCataloguePath, catalogues_paths))

        self.catalogues_view = QtWidgets.QTreeView()
        self.catalogues_view.setMinimumSize(300, 900)
        self.catalogues_view.setDragEnabled(True)
        self.catalogues_view.setDragDropMode(QtWidgets.QTreeView.DragDropMode.DragDrop)
        self.catalogues_view.setAcceptDrops(True)
        self.catalogues_view.setDropIndicatorShown(True)
        self.catalogues_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)  # type: ignore

        self.catalogue_sort_filter_model = _TrashAlwaysTopOrBottomSortFilterModel()
        self.catalogue_sort_filter_model.setSourceModel(self.catalogue_model)
        self.catalogue_sort_filter_model.setRecursiveFilteringEnabled(True)
        self.catalogue_sort_filter_model.setFilterCaseSensitivity(
            QtCore.Qt.CaseSensitivity.CaseInsensitive)  # type: ignore

        self.catalogues_view.setModel(self.catalogue_sort_filter_model)
        self.catalogues_view.setSortingEnabled(True)
        self.catalogues_view.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)  # type: ignore

        self.catalogues_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)  # type: ignore

        self.catalogues_view.selectionModel().selectionChanged.connect(  # type: ignore
            self.__catalogue_selection_changed,
            type=QtCore.Qt.DirectConnection)  # type: ignore

        self.catalogues_view.expanded.connect(
            lambda index: self.catalogue_model.expanded(self.catalogue_sort_filter_model.mapToSource(index)))
        self.catalogues_view.collapsed.connect(
            lambda index: self.catalogue_model.collapsed(self.catalogue_sort_filter_model.mapToSource(index)))

        # Catalogue Layout and Filter
        hlayout = QtWidgets.QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.addWidget(QtWidgets.QLabel('Filter:'))

        catalogue_filter = QtWidgets.QLineEdit()
        catalogue_filter.textChanged.connect(  # type: ignore
            lambda t: self.catalogue_sort_filter_model.setFilterRegularExpression(t))

        hlayout.addWidget(catalogue_filter)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(hlayout)
        layout.addWidget(self.catalogues_view)

        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(layout)

        # MainWindow Catalogue/Right Splitter - Horizonal
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)  # type: ignore
        splitter.addWidget(left_widget)
        splitter.addWidget(self.splitter_right)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QtWidgets.QToolBar()

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_DirIcon),  # type: ignore
                               "Create Folder", self)
        action.triggered.connect(self.__new_folder)  # type: ignore
        toolbar.addAction(action)

        self.new_folder_action = action

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogNewFolder),  # type: ignore
                               "Create Catalogue", self)
        action.triggered.connect(lambda: self.state.push_undo_command(NewCatalogue))  # type: ignore
        toolbar.addAction(action)

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon),  # type: ignore
                               "Create Event", self)
        action.triggered.connect(lambda: self.state.push_undo_command(NewEvent))  # type: ignore
        action.setEnabled(False)
        toolbar.addAction(action)

        self.new_event_action = action

        toolbar.addSeparator()
        action = QtGui.QAction(
            self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton), "Save To Disk",  # type: ignore
            self)

        action.triggered.connect(self.save)  # type: ignore
        toolbar.addAction(action)
        action.setEnabled(False)
        self.state.undo_stack_clean_changed.connect(lambda state, a=action: a.setEnabled(not state))

        toolbar.addSeparator()
        undo_action, redo_action = self.state.create_undo_redo_action()

        undo_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowBack))  # type: ignore
        undo_action.setShortcut(QtCore.Qt.CTRL | QtCore.Qt.Key_Z)  # type: ignore
        toolbar.addAction(undo_action)
        self.undo_toolbar_button = cast(QtWidgets.QToolButton, toolbar.widgetForAction(undo_action))
        self.undo_toolbar_button.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)  # type: ignore

        redo_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowForward))  # type: ignore
        redo_action.setShortcut(QtCore.Qt.CTRL | QtCore.Qt.SHIFT | QtCore.Qt.Key_Z)  # type: ignore
        toolbar.addAction(redo_action)
        self.redo_toolbar_button = cast(QtWidgets.QToolButton, toolbar.widgetForAction(redo_action))
        self.redo_toolbar_button.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)  # type: ignore

        self.state.undo_stack().indexChanged.connect(self.__undo_redo_index_changed)  # type: ignore

        toolbar.addSeparator()

        action = QtGui.QAction(
            self.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon), "Move to Trash", self)  # type: ignore

        action.triggered.connect(lambda: self.state.push_undo_command(MoveEntityToTrash))  # type: ignore
        action.setEnabled(False)
        toolbar.addAction(action)
        self.move_to_trash_action = action

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_DialogResetButton),  # type: ignore
                               "Restore from Trash", self)

        action.triggered.connect(lambda: self.state.push_undo_command(RestoreEntityFromTrash))  # type: ignore
        action.setEnabled(False)
        toolbar.addAction(action)
        self.restore_from_trash_action = action

        action = QtGui.QAction(
            self.style().standardIcon(QtWidgets.QStyle.SP_BrowserStop), "Delete permanently",  # type: ignore
            self)

        action.triggered.connect(lambda: self.state.push_undo_command(DeletePermanently))  # type: ignore
        action.setEnabled(False)
        toolbar.addAction(action)
        self.delete_action = action

        toolbar.addSeparator()

        action = QtGui.QAction(
            self.style().standardIcon(QtWidgets.QStyle.SP_DialogRetryButton), "Refresh",  # type: ignore
            self)

        action.triggered.connect(self.__refresh_current_selection)  # type: ignore
        action.setEnabled(False)
        toolbar.addAction(action)

        self.refresh_action = action

        toolbar.addSeparator()

        action = QtGui.QAction(
            self.style().standardIcon(QtWidgets.QStyle.SP_ArrowUp), "Import Catalogue",  # type: ignore
            self)

        action.triggered.connect(self.__import_from_file)  # type: ignore
        toolbar.addAction(action)

        action = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowDown),  # type: ignore
                               "Export Catalogue",
                               self)

        action.triggered.connect(self.__export_to_file)  # type: ignore
        action.setEnabled(False)
        toolbar.addAction(action)

        self.export_action = action

        layout.addWidget(toolbar)
        layout.addWidget(splitter)
        self.setLayout(layout)

    def _external_signal_emission_changed(self, action: Action) -> None:
        if isinstance(action, (SetAttributeAction, DeleteAttributeAction)):
            if isinstance(action.entities[0], _Catalogue):
                self.catalogues_changed.emit([e.uuid for e in action.entities])
            else:
                self.events_changed.emit([e.uuid for e in action.entities])

    @staticmethod
    def update_event_range(uuid: str, start: dt.datetime, stop: dt.datetime) -> None:
        from .tscat_driver.model import tscat_model
        tscat_model.do(SetAttributeAction(None, [uuid], 'start', [start]))
        tscat_model.do(SetAttributeAction(None, [uuid], 'stop', [stop]))

    @staticmethod
    def create_event(start: dt.datetime, stop: dt.datetime, author: str, catalogue_uuid: str) -> _Event:
        event_loop = QtCore.QEventLoop()
        entity = None

        def added_event(_: AddEventsToCatalogueAction) -> None:
            event_loop.quit()

        from .tscat_driver.model import tscat_model

        def creation_callback(action: CreateEntityAction) -> None:
            nonlocal entity
            entity = action.entity
            tscat_model.do(AddEventsToCatalogueAction(added_event, [action.entity.uuid], catalogue_uuid))

        tscat_model.do(CreateEntityAction(creation_callback, _Event,
                                          {
                                              'start': start,
                                              'stop': stop,
                                              'author': author,
                                          }))

        event_loop.exec()

        assert isinstance(entity, _Event)

        return entity

    @staticmethod
    def move_to_trash(uuid: str) -> None:
        from .tscat_driver.model import tscat_model
        tscat_model.do(MoveToTrashAction(None, [uuid]))

    def save(self) -> None:
        def clear_undo_stack(_: SaveAction) -> None:
            self.state.set_undo_stack_clean()

        from .tscat_driver.model import tscat_model
        tscat_model.do(SaveAction(clear_undo_stack))


def main():
    # QtWidgets.QApplication.setDesktopSettingsAware(False)  # defaulting to light mode

    app = QtWidgets.QApplication(sys.argv)

    main = QtWidgets.QMainWindow()

    w = TSCatGUI(main)

    main.setCentralWidget(w)

    #     styles = """
    # QTreeView::!active { selection-background-color: gray;}
    # """
    #     main.setStyleSheet(styles)

    main.show()

    sys.exit(app.exec())
