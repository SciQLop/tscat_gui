from PySide2 import QtCore

import tscat
from tscat import get_catalogues
from typing import Any


class CatalogueModel(QtCore.QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.catalogues = get_catalogues()
        self.uuid_index = {}

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole) -> Any:
        if role == QtCore.Qt.DisplayRole:
            return "Catalogues"
        return None

    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        return QtCore.QModelIndex()

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 1

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        if not parent.isValid():  # root
            return len(self.catalogues)
        return 0  # no children

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlags:
        if index.isValid():
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        return QtCore.Qt.NoItemFlags

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole) -> Any:
        if index.isValid() and role == QtCore.Qt.DisplayRole:
            obj = index.internalPointer()
            if isinstance(obj, tscat.Catalogue):
                return obj.name
        return None

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()
        index = self.createIndex(row, column, self.catalogues[row])
        self.uuid_index[self.catalogues[row].uuid] = index
        return index

    def index_from_uuid(self, uuid: str) -> QtCore.QModelIndex:
        return self.uuid_index.get(uuid, QtCore.QModelIndex())
