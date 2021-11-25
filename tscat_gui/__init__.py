"""Top-level package for Time series catalogue - GUI."""

__author__ = """Patrick Boettcher"""
__email__ = 'p@yai.se'
__version__ = '0.1.0'

from PySide2 import QtWidgets
from PySide2 import QtCore
from PySide2 import QtGui

from .model import CatalogueModel


class TSCatGUI(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        events = QtWidgets.QTableView()
        events.setMinimumSize(1000, 500)

        details = QtWidgets.QWidget(self)
        details.setMinimumHeight(400)
        details_layout = QtWidgets.QGridLayout(details)
        details_layout.setMargin(0)

        splitter_right = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        splitter_right.addWidget(events)
        splitter_right.addWidget(details)

        catalogues = QtWidgets.QTreeView()
        catalogues.setMinimumSize(300, 900)
        catalogues.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

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

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        splitter.addWidget(catalogues)
        splitter.addWidget(splitter_right)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QtWidgets.QToolBar()
        toolbar.addAction(QtWidgets.QAction(QtGui.QIcon.fromTheme('folder-new'), "Create Catalogue", self))

        layout.addWidget(toolbar)
        layout.addWidget(splitter)
        self.setLayout(layout)

        self.catalogue_model = CatalogueModel(self)

        catalogues.setModel(self.catalogue_model)
