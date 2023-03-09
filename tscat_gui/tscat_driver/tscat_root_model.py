from typing import Dict, Any

from PySide6.QtCore import QModelIndex, QAbstractItemModel, QPersistentModelIndex, Qt

from .catalog_model import CatalogModel
from .driver import tscat_driver
from .nodes import Node, CatalogNode

UUIDRole = Qt.UserRole + 1  # type: ignore


def _build_root_hierarchy(catalogs, trash_catalogs) -> Node:
    return Node("root",
                children=
                list(map(lambda c: CatalogNode(c, []), catalogs))
                +
                [Node("Trash", children=list(map(lambda c: CatalogNode(c, []), trash_catalogs)))]
                )


def _build_catalog_model(catalog: CatalogNode) -> CatalogModel:
    return CatalogModel(catalog)


def _update_catalog(catalog: CatalogNode, root_model: QAbstractItemModel, catalog_model: CatalogModel):
    catalog_model.update(catalog)


class TscatRootModel(QAbstractItemModel):
    def __init__(self):
        super().__init__()
        self._root = Node("root", children=[])
        self._catalogs: Dict[str, CatalogModel] = {}
        tscat_driver.get_catalogs(self._update_catalogs)

    def update(self, root: Node):
        self.beginResetModel()
        self._root = root
        self.endResetModel()

    def _update_catalogs(self, catalogs):
        for catalog in catalogs:
            if catalog.uuid not in self._catalogs:
                self._catalogs[catalog.uuid] = CatalogModel(None)
                self._update_catalog(catalog, [])
            tscat_driver.get_catalog(catalog.uuid, self._update_catalog)

    def _update_catalog(self, catalog, events):
        self.update_catalog(CatalogNode(catalog=catalog, events=events))

    def update_catalog(self, catalog: CatalogNode):
        self.beginResetModel()
        self._root.children = list(
            filter(lambda n: not (isinstance(n, CatalogNode) and n.uuid == catalog.uuid),
                   self._root.children)) + [catalog]
        self.endResetModel()
        self._catalogs[catalog.uuid].update(catalog)

    def catalog(self, uid: str) -> CatalogModel:
        return self._catalogs[uid]

    def index(self, row: int, column: int, parent: QModelIndex | QPersistentModelIndex = ...) -> QModelIndex:
        if self.hasIndex(row, column, parent):
            if not parent.isValid():
                parent_item: Node = self._root
            else:
                parent_item: Node = parent.internalPointer()  # type: ignore
            child_item: Node = parent_item.children[row]
            if child_item is not None:
                return self.createIndex(row, column, child_item)
        return QModelIndex()

    def parent(self, index: QModelIndex | QPersistentModelIndex = ...) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        child_item: Node = index.internalPointer()
        parent_item: Node = child_item.parent
        if parent_item is not None:
            return self.createIndex(parent_item.row, 0, parent_item)
        return QModelIndex()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        if parent.column() > 0:
            return 0
        if not parent.isValid():
            parent_item = self._root
        else:
            parent_item: Node = parent.internalPointer()

        if isinstance(parent_item, CatalogNode):
            return 0
        else:
            return len(parent_item.children)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = ...) -> int:
        return 1

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = ...) -> Any:
        if index.isValid():
            item: Node = index.internalPointer()
            if role == Qt.DisplayRole:
                return item.name
            if role == UUIDRole:
                if isinstance(item, CatalogNode):
                    return item.uuid

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> int:
        if index.isValid():
            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
            item: Node = index.internalPointer()
            flags |= Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
            return flags
        return Qt.NoItemFlags

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:  # type: ignore
        if role == Qt.DisplayRole:  # type: ignore
            return "Catalogues"
        return None
