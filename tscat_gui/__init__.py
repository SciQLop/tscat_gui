"""Top-level package for Time series catalogue - GUI."""

__author__ = """Patrick Boettcher"""
__email__ = 'p@yai.se'
__version__ = '0.1.0'

from PySide2 import QtWidgets
from PySide2 import QtCore
from PySide2 import QtGui

from typing import Union

import tscat

from .model import CatalogueModel

from .edit import CatalogueEditWidget

from .undo import stack


class TSCatGUI(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        stack.setup(self)

        events = QtWidgets.QTableView()
        events.setMinimumSize(1000, 500)

        self.edit = QtWidgets.QWidget()
        self.edit.setMinimumHeight(400)

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

        def current_model_data_changed(catalogue: tscat.Catalogue):
            self.catalogue_model.dataChanged.emit(
                self.current_selected_catalogue,
                self.current_selected_catalogue,
                QtCore.Qt.EditRole)

        def cur_changed(selected: QtCore.QModelIndex, deselected: QtCore.QModelIndex):
            print("cur_changed", selected, deselected)
            if selected.isValid():
                self.current_selected_catalogue = selected

                if self.edit:
                    self.edit.deleteLater()

                self.edit = CatalogueEditWidget(selected.internalPointer(), self)
                self.edit.valuesChanged.connect(current_model_data_changed)
                splitter_right.replaceWidget(1, self.edit)

                # self.current_edit_widget.dataChanged.connect(current_model_data_changed)
                # details.setModel(self.current_edit_model)

        print('edit-window-update')

        # self.catalogues.selectionModel().selectionChanged.connect(sel_changed)
        self.catalogues.selectionModel().currentChanged.connect(cur_changed)
        self.catalogues.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        splitter.addWidget(self.catalogues)
        splitter.addWidget(splitter_right)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QtWidgets.QToolBar()
        toolbar.addAction(QtWidgets.QAction(QtGui.QIcon.fromTheme('folder-new'), "Create Catalogue", self))

        action = QtWidgets.QAction(QtGui.QIcon.fromTheme('document-save'), "Save To Disk", self)

        def save():
            tscat.save()
            stack.setClean()

        action.triggered.connect(save)
        toolbar.addAction(action)
        action.setEnabled(False)
        stack.cleanChanged.connect(lambda state, a=action: a.setEnabled(not state))

        action = stack.createUndoAction(self)
        action.setIcon(QtGui.QIcon.fromTheme('edit-undo'))
        toolbar.addAction(action)

        action = stack.createRedoAction(self)
        action.setIcon(QtGui.QIcon.fromTheme('edit-redo'))
        toolbar.addAction(action)

        layout.addWidget(toolbar)
        layout.addWidget(splitter)
        self.setLayout(layout)

    def select(self, entity: Union[tscat.Catalogue, tscat.Event], catalogue: tscat.Catalogue) -> None:
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

        if catalogue:
            print("  and select catalogue", catalogue.name)
