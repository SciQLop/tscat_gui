from typing import Dict, Any, List

from PySide6.QtCore import QModelIndex, QAbstractItemModel, QPersistentModelIndex, Qt
from tscat import _Event, _Catalogue

from .actions import Action, GetCataloguesAction, GetCatalogueAction, CreateEntityAction, RemoveEntityAction, SetAttributeAction, DeleteAttributeAction
from .catalog_model import CatalogModel
from .driver import tscat_driver
from .nodes import Node, NamedNode, CatalogNode
from ..model_base.constants import UUIDDataRole


class TscatRootModel(QAbstractItemModel):
    def __init__(self):
        super().__init__()
        self._root = NamedNode([])
        self._catalogues: Dict[str, CatalogModel] = {}

        tscat_driver.action_done.connect(self._driver_action_done)

        tscat_driver.do(GetCataloguesAction(None, False))

    def _driver_action_done(self, action: Action) -> None:
        if isinstance(action, GetCataloguesAction):
            self.beginResetModel()
            self._root.children = []
            for c in action.catalogues:
                node = CatalogNode(c)
                self._root.children.append(node)
            self.endResetModel()

        elif isinstance(action, GetCatalogueAction):
            for row, child in enumerate(self._root.children):
                if child.uuid == action.uuid:
                    break
            else:
                return

            index = self.index(row, 0, QModelIndex())
            self.dataChanged.emit(index, index)

        elif isinstance(action, CreateEntityAction):
            if isinstance(action.entity, _Catalogue):
                self.beginInsertRows(QModelIndex(), len(self._root.children), len(self._root.children) + 1)
                node = CatalogNode(action.entity)
                self._root.children.append(node)
                self.endInsertRows()

        elif isinstance(action, RemoveEntityAction):
            for row, c in enumerate(self._root.children[::-1]):
                if c.uuid == action.uuid:
                    self.beginRemoveRows(QModelIndex(), row, row)
                    self._root.children.remove(c)
                    self.endRemoveRows()

        elif isinstance(action, (SetAttributeAction, DeleteAttributeAction)):
            for e in filter(lambda x: isinstance(x, _Catalogue), action.entities):
                for row, child in enumerate(self._root.children):
                    if child.uuid == e.uuid:
                        child.node = e
                        index = self.index(row, 0, QModelIndex())
                        self.dataChanged.emit(index, index)

    def catalog(self, uuid: str) -> CatalogModel:
        if uuid not in self._catalogues:
            for child in self._root.children:
                if uuid == child.uuid:
                    break
            else:
                assert False

            catalogue_model = CatalogModel(child)
            self._catalogues[uuid] = catalogue_model
            tscat_driver.do(GetCatalogueAction(None, uuid=uuid))

        return self._catalogues[uuid]

    def index_from_uuid(self, uuid: str, parent=QModelIndex()) -> QModelIndex:
        for i in range(self.rowCount(parent)):
            index = self.index(i, 0, parent)
            if self.data(index, UUIDDataRole) == uuid:
                return index
            if self.rowCount(index) > 0:
                result = self.index_from_uuid(uuid, index)
                if result != QModelIndex():
                    return result
        return QModelIndex()

    def index(self, row: int, column: int, parent: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        if self.hasIndex(row, column, parent):
            if not parent.isValid():
                parent_item: Node = self._root
            else:
                parent_item: Node = parent.internalPointer()  # type: ignore
            child_item: Node = parent_item.children[row]
            if child_item is not None:
                return self.createIndex(row, column, child_item)
        return QModelIndex()

    def parent(self, index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        child_item: Node = index.internalPointer()
        parent_item: Node = child_item.parent
        if parent_item is not None:
            return self.createIndex(parent_item.row, 0, parent_item)
        return QModelIndex()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex) -> int:
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

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex) -> int:
        return 1

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.DisplayRole) -> Any:
        if index.isValid():
            item: Node = index.internalPointer()
            if role == Qt.DisplayRole:
                return item.name
            if role == UUIDDataRole:
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
