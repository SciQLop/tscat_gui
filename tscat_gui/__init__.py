"""Top-level package for Time series catalogue - GUI."""

__author__ = """Patrick Boettcher"""
__email__ = 'p@yai.se'
__version__ = '0.1.0'

from PySide2 import QtWidgets
from PySide2 import QtCore
from PySide2 import QtGui

import tscat
from .model import CatalogueModel

from .edit import CatalogueEditWidget


class TSCatGUI(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        events = QtWidgets.QTableView()
        events.setMinimumSize(1000, 500)

        details_placeholder = QtWidgets.QWidget()
        details_placeholder.setMinimumHeight(400)

        splitter_right = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        splitter_right.addWidget(events)
        splitter_right.addWidget(details_placeholder)

        self.catalogue_model = CatalogueModel(self)

        catalogues = QtWidgets.QTreeView()
        catalogues.setMinimumSize(300, 900)
        catalogues.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        catalogues.setModel(self.catalogue_model)

        catalogues.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        def restore_triggered(checked: bool):
            print("triggered")
            for i in catalogues.selectedIndexes():
                print(i.internalPointer())

        def ctxMenu(pos: QtCore.QPoint):
            context_menu = QtWidgets.QMenu(self)
            action = QtWidgets.QAction(QtGui.QIcon.fromTheme('view-refresh'), "Restore", self)
            action.triggered.connect(restore_triggered)
            context_menu.addAction(action)
            context_menu.exec_(catalogues.viewport().mapToGlobal(pos))

        catalogues.customContextMenuRequested.connect(ctxMenu)

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

                w = splitter_right.widget(1)
                w.deleteLater()

                new_edit = CatalogueEditWidget(selected.internalPointer(), self)
                new_edit.valuesChanged.connect(current_model_data_changed)
                splitter_right.replaceWidget(1, new_edit)

                # self.current_edit_widget.dataChanged.connect(current_model_data_changed)
                # details.setModel(self.current_edit_model)

        print('edit-window-update')

        # catalogues.selectionModel().selectionChanged.connect(sel_changed)
        catalogues.selectionModel().currentChanged.connect(cur_changed)
        catalogues.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        splitter.addWidget(catalogues)
        splitter.addWidget(splitter_right)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QtWidgets.QToolBar()
        toolbar.addAction(QtWidgets.QAction(QtGui.QIcon.fromTheme('folder-new'), "Create Catalogue", self))

        action = QtWidgets.QAction(QtGui.QIcon.fromTheme('document-save'), "Save To Disk", self)
        action.triggered.connect(lambda x: tscat.save())
        toolbar.addAction(action)

        layout.addWidget(toolbar)
        layout.addWidget(splitter)
        self.setLayout(layout)
