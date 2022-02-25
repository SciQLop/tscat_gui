from PySide2 import QtCore

import tscat
from typing import Any

from .utils.helper import get_entity_from_uuid_safe


class CatalogueModel(QtCore.QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.uuids = [c.uuid for c in tscat.get_catalogues()]
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
            return len(self.uuids)
        return 0  # no children

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlags:
        if index.isValid():
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        return QtCore.Qt.NoItemFlags

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole) -> Any:
        if index.isValid() and role == QtCore.Qt.DisplayRole:
            entity = get_entity_from_uuid_safe(index.internalPointer())
            assert isinstance(entity, tscat.Catalogue)
            return entity.name
        return None

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()
        index = self.createIndex(row, column, self.uuids[row])
        self.uuid_index[self.uuids[row]] = index
        return index

    def index_from_uuid(self, uuid: str) -> QtCore.QModelIndex:
        return self.uuid_index[uuid]

    def create(self, name='New Catalogue', author='Author', **kwargs) -> tscat.Catalogue:
        row_index = self.rowCount()

        self.beginInsertRows(QtCore.QModelIndex(), row_index, row_index + 1)
        catalogue = tscat.Catalogue(name, author=author, **kwargs)
        print(catalogue, catalogue.uuid)
        self.uuids += [catalogue.uuid]
        self.uuid_index[catalogue.uuid] = self.index(row_index, 0)
        self.endInsertRows()

        return catalogue

    def delete(self, uuid: str):
        row_index = self.index_from_uuid(uuid).row()
        self.beginRemoveRows(QtCore.QModelIndex(), row_index, row_index + 1)

        catalogue = get_entity_from_uuid_safe(uuid)
        catalogue.remove(permanently=True)

        del self.uuid_index[uuid]
        self.uuids.remove(uuid)
        self.endRemoveRows()
