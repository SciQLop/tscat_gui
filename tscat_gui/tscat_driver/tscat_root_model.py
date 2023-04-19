import pickle
from typing import Dict, Any, Union

from PySide6.QtCore import QModelIndex, QAbstractItemModel, QPersistentModelIndex, Qt, QMimeData, Signal
from tscat import _Catalogue

from .actions import Action, GetCataloguesAction, GetCatalogueAction, CreateEntityAction, RemoveEntitiesAction, \
    SetAttributeAction, DeleteAttributeAction, MoveToTrashAction, RestoreFromTrashAction, ImportCanonicalizedDictAction
from .catalog_model import CatalogModel
from .driver import tscat_driver
from .nodes import Node, NamedNode, CatalogNode, TrashNode
from ..model_base.constants import UUIDDataRole


class TscatRootModel(QAbstractItemModel):
    events_dropped_on_catalogue = Signal(str, list)

    def __init__(self):
        super().__init__()
        self._root = NamedNode()
        self._trash = TrashNode()

        self._root.append_child(self._trash)

        self._catalogues: Dict[str, CatalogModel] = {}

        tscat_driver.action_done.connect(self._driver_action_done)

        tscat_driver.do(GetCataloguesAction(None, False))
        tscat_driver.do(GetCataloguesAction(None, True))

    def _trash_index(self) -> QModelIndex:
        return self.index(0, 0, QModelIndex())

    def _driver_action_done(self, action: Action) -> None:
        if isinstance(action, GetCataloguesAction):
            if action.removed_items:
                self.beginRemoveRows(self._trash_index(), 0, len(self._trash.children) - 1)
                self._trash.set_children([])
                self.endRemoveRows()

                self.beginInsertRows(self._trash_index(), 0, len(action.catalogues) - 1)
                self._trash.set_children(list(map(CatalogNode, action.catalogues)))
                self.endInsertRows()
            else:
                self.beginResetModel()
                self._root.set_children([self._trash])
                self._root.append_children(list(map(CatalogNode, action.catalogues)))
                self.endResetModel()

        elif isinstance(action, GetCatalogueAction):
            for row, child in enumerate(self._root.children):
                if child.uuid == action.uuid:
                    index = self.index(row, 0, QModelIndex())
                    self.dataChanged.emit(index, index)
                    return

            for row, child in enumerate(self._trash.children):
                if child.uuid == action.uuid:
                    index = self.index(row, 0, self._trash_index())
                    self.dataChanged.emit(index, index)

        elif isinstance(action, CreateEntityAction):
            if isinstance(action.entity, _Catalogue):
                self.beginInsertRows(QModelIndex(), len(self._root.children), len(self._root.children))
                node = CatalogNode(action.entity)
                self._root.append_child(node)
                self.endInsertRows()

        elif isinstance(action, RemoveEntitiesAction):
            for row, c in reversed(list(enumerate(self._root.children))):
                if c.uuid in action.uuids:
                    self.beginRemoveRows(QModelIndex(), row, row)
                    self._root.remove_child(c)
                    self.endRemoveRows()

        elif isinstance(action, MoveToTrashAction):
            for row, c in reversed(list(enumerate(self._root.children))):
                if c.uuid in action.uuids:
                    self.beginRemoveRows(QModelIndex(), row, row)
                    self._root.remove_child(c)
                    self.endRemoveRows()

                    self.beginInsertRows(self._trash_index(), len(self._trash.children), len(self._trash.children))
                    self._trash.append_child(c)
                    self.endInsertRows()
                    print('moving to trash', c, c.uuid)

        elif isinstance(action, RestoreFromTrashAction):
            for row, c in reversed(list(enumerate(self._trash.children))):
                if c.uuid in action.uuids:
                    self.beginRemoveRows(self._trash_index(), row, row)
                    self._trash.remove_child(c)
                    self.endRemoveRows()

                    self.beginInsertRows(QModelIndex(), len(self._root.children), len(self._root.children))
                    self._root.append_child(c)
                    self.endInsertRows()

        elif isinstance(action, (SetAttributeAction, DeleteAttributeAction)):
            for e in filter(lambda x: isinstance(x, _Catalogue), action.entities):
                for row, child in enumerate(self._root.children):
                    if child.uuid == e.uuid:
                        child.node = e
                        index = self.index(row, 0, QModelIndex())
                        self.dataChanged.emit(index, index)

                for row, child in enumerate(self._trash.children):
                    if child.uuid == e.uuid:
                        child.node = e
                        index = self.index(row, 0, self._trash_index())
                        self.dataChanged.emit(index, index)

        elif isinstance(action, ImportCanonicalizedDictAction):
            self.beginInsertRows(QModelIndex(),
                                 len(self._root.children),
                                 len(self._root.children) + len(action.catalogues) - 1)
            self._root.append_children(list(map(CatalogNode, action.catalogues)))
            self.endInsertRows()

    def catalog(self, uuid: str) -> CatalogModel:
        if uuid not in self._catalogues:
            for child in self._root.children:
                if uuid == child.uuid:
                    break
            else:
                assert False

            catalogue_model = CatalogModel(child)
            self._catalogues[uuid] = catalogue_model
            tscat_driver.do(GetCatalogueAction(None, removed_items=False, uuid=uuid))

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
            item: Node = index.internalPointer()
            return item.flags()
        return Qt.NoItemFlags

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:  # type: ignore
        if role == Qt.DisplayRole:  # type: ignore
            return "Catalogues"
        return None

    def supportedDragActions(self) -> Qt.DropAction:
        return Qt.DropAction.CopyAction

    def canDropMimeData(self, data: QMimeData, action: Qt.DropAction,
                        row: int, column: int,
                        parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        if not data.hasFormat('application/x-tscat-event-uuid-list'):
            return False
        return True

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction,
                     row: int, column: int,
                     parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        if not self.canDropMimeData(data, action, row, column, parent):
            return False

        if action == Qt.DropAction.IgnoreAction:
            return True

        self.events_dropped_on_catalogue.emit(parent.data(UUIDDataRole),
                                              pickle.loads(data.data('application/x-tscat-event-uuid-list')))

        return True
