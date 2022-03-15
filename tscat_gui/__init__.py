"""Top-level package for Time series catalogue - GUI."""

__author__ = """Patrick Boettcher"""
__email__ = 'p@yai.se'
__version__ = '0.1.0'

from PySide2 import QtWidgets
from PySide2 import QtCore
from PySide2 import QtGui

import tscat

from .model import CatalogueModel, UUIDRole, InTrashRole

from .edit import EntityEditWidget

from .undo import NewCatalogue, MoveEntityToTrash, RestoreEntityFromTrash, DeletePermanently

from .utils.helper import get_entity_from_uuid_safe


class _UndoStack(QtWidgets.QUndoStack):
    def __init__(self, main_widget: QtWidgets.QWidget):
        super().__init__(None)

        self.main_widget = main_widget

    def push(self, cmd: QtWidgets.QUndoCommand) -> None:
        cmd.set_stack(self)
        super().push(cmd)


class TSCatGUI(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.undo_stack = _UndoStack(self)

        events = QtWidgets.QTableView()
        events.setMinimumSize(1000, 500)

        self.empty_edit = QtWidgets.QWidget()
        self.empty_edit.setMinimumHeight(400)

        self.edit = self.empty_edit

        splitter_right = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        splitter_right.addWidget(events)
        splitter_right.addWidget(self.edit)

        self.catalogue_model = CatalogueModel(self)

        self.catalogues = QtWidgets.QTreeView()
        self.catalogues.setMinimumSize(300, 900)
        self.catalogues.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.catalogues.setModel(self.catalogue_model)

        self.catalogues.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        def restore_triggered(checked: bool):
            print("triggered")
            for i in self.catalogues.selectedIndexes():
                print(i.internalPointer())

        def ctxMenu(pos: QtCore.QPoint):
            context_menu = QtWidgets.QMenu(self)
            action = QtWidgets.QAction(QtGui.QIcon.fromTheme('view-refresh'), "Restore", self)
            action.triggered.connect(restore_triggered)
            context_menu.addAction(action)
            context_menu.exec_(self.catalogues.viewport().mapToGlobal(pos))

        self.catalogues.customContextMenuRequested.connect(ctxMenu)

        def sel_changed(selected: QtCore.QItemSelection, deselected: QtCore.QItemSelection):
            print("selected:", [i for i in selected.indexes()])
            if len(selected.indexes()) == 1:
                print('edit-window-update')

            # print("deselected:", [i for i in deselected.indexes()])

        def current_model_data_changed(uuid: str):
            self.catalogue_model.dataChanged.emit(
                self.current_selected_catalogue,
                self.current_selected_catalogue,
                QtCore.Qt.EditRole)

        def cur_changed(selected: QtCore.QModelIndex, deselected: QtCore.QModelIndex):
            # print("cur_changed", selected, deselected)
            if self.edit:
                self.edit.deleteLater()
                self.edit = None

            self.move_to_trash_action.setEnabled(False)
            self.restore_from_trash_action.setEnabled(False)
            self.delete_action.setEnabled(False)

            if selected.isValid():
                self.current_selected_catalogue = selected
                uuid = self.catalogue_model.data(selected, UUIDRole)
                in_trash = self.catalogue_model.data(selected, InTrashRole)

                if uuid:
                    self.edit = EntityEditWidget(uuid, self.undo_stack, in_trash, self)
                    self.edit.valuesChanged.connect(current_model_data_changed)
                    splitter_right.addWidget(self.edit)

                    self.move_to_trash_action.setEnabled(not in_trash)
                    self.restore_from_trash_action.setEnabled(in_trash)
                    self.delete_action.setEnabled(True)

        # self.catalogues.selectionModel().selectionChanged.connect(sel_changed)
        self.catalogues.selectionModel().currentChanged.connect(cur_changed)
        self.catalogues.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        splitter.addWidget(self.catalogues)
        splitter.addWidget(splitter_right)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QtWidgets.QToolBar()

        action = QtWidgets.QAction(QtGui.QIcon.fromTheme('folder-new'), "Create Catalogue", self)

        def new_catalogue():
            self.undo_stack.push(NewCatalogue())

        action.triggered.connect(new_catalogue)
        toolbar.addAction(action)

        action = QtWidgets.QAction(QtGui.QIcon.fromTheme('document-save'), "Save To Disk", self)

        def save():
            tscat.save()
            self.undo_stack.setClean()

        action.triggered.connect(save)
        toolbar.addAction(action)
        action.setEnabled(False)
        self.undo_stack.cleanChanged.connect(lambda state, a=action: a.setEnabled(not state))

        action = self.undo_stack.createUndoAction(self)
        action.setIcon(QtGui.QIcon.fromTheme('edit-undo'))
        toolbar.addAction(action)

        action = self.undo_stack.createRedoAction(self)
        action.setIcon(QtGui.QIcon.fromTheme('edit-redo'))
        toolbar.addAction(action)

        action = QtWidgets.QAction(QtGui.QIcon.fromTheme('user-trash'), "Move to Trash", self)

        def trash():
            uuid = self.catalogue_model.data(self.current_selected_catalogue, UUIDRole)
            self.undo_stack.push(MoveEntityToTrash(uuid))

        action.triggered.connect(trash)
        action.setEnabled(False)
        toolbar.addAction(action)
        self.move_to_trash_action = action

        action = QtWidgets.QAction(QtGui.QIcon.fromTheme('todo'), "Restore from Trash", self)

        def restore():
            uuid = self.catalogue_model.data(self.current_selected_catalogue, UUIDRole)
            self.undo_stack.push(RestoreEntityFromTrash(uuid))

        action.triggered.connect(restore)
        action.setEnabled(False)
        toolbar.addAction(action)
        self.restore_from_trash_action = action

        action = QtWidgets.QAction(QtGui.QIcon.fromTheme('edit-delete'), "Delete permanently", self)

        def delete():
            uuid = self.catalogue_model.data(self.current_selected_catalogue, UUIDRole)
            self.undo_stack.push(DeletePermanently(uuid))

        action.triggered.connect(delete)
        action.setEnabled(False)
        toolbar.addAction(action)
        self.delete_action = action

        layout.addWidget(toolbar)
        layout.addWidget(splitter)
        self.setLayout(layout)

    def select(self, entity_uuid: str, catalogue_uuid: str = None) -> None:
        self.catalogue_model.reset()
        if entity_uuid is not None:
            entity = get_entity_from_uuid_safe(entity_uuid)

            if type(entity) is tscat.Catalogue:
                print('select catalogue', entity.name)
                index = self.catalogue_model.index_from_uuid(entity.uuid)
                if index.isValid():
                    self.catalogues.setCurrentIndex(index)
                    self.edit.setup()
                    print('update edit')
                else:
                    print('catalogue not in model')
            else:
                print('select event', entity)
        else:
            if self.edit:
                self.edit.deleteLater()
                self.edit = None

        if catalogue_uuid:
            catalogue = get_entity_from_uuid_safe(catalogue_uuid)

            print("  and select catalogue", catalogue.name)
