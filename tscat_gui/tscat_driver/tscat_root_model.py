import datetime as dt
import os
import pickle
import tempfile
from typing import Dict, Any, Union, cast, List, Sequence

from PySide6.QtCore import QModelIndex, QAbstractItemModel, QPersistentModelIndex, Qt, QMimeData, Signal, QUrl
from tscat import _Catalogue

from .actions import Action, GetCataloguesAction, GetCatalogueAction, CreateEntityAction, RemoveEntitiesAction, \
    SetAttributeAction, DeleteAttributeAction, MoveToTrashAction, RestoreFromTrashAction, ImportCanonicalizedDictAction, \
    DeletePermanentlyAction, RestorePermanentlyDeletedAction
from .catalog_model import CatalogModel
from .driver import tscat_driver
from .nodes import Node, CatalogNode, TrashNode, RootNode, NamedNode
from ..model_base.constants import UUIDDataRole, EntityRole
from ..utils.export import export_to_json


class TscatRootModel(QAbstractItemModel):
    events_dropped_on_catalogue = Signal(str, list)

    def __init__(self) -> None:
        super().__init__()
        self._root = RootNode()
        self._trash = TrashNode()

        self._root.append_child(self._trash)

        self._catalogues: Dict[str, CatalogModel] = {}

        tscat_driver.action_done_prioritised.connect(self._driver_action_done)

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

        elif isinstance(action, (RemoveEntitiesAction, DeletePermanentlyAction)):
            for row, c in reversed(list(enumerate(self._root.children))):
                if c.uuid in action.uuids:
                    self.beginRemoveRows(QModelIndex(), row, row)
                    self._root.remove_child(c)
                    self.endRemoveRows()

            for row, c in reversed(list(enumerate(self._trash.children))):
                if c.uuid in action.uuids:
                    self.beginRemoveRows(self._trash_index(), row, row)
                    self._trash.remove_child(c)
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

        elif isinstance(action, RestoreFromTrashAction):
            for row, c in reversed(list(enumerate(self._trash.children))):
                if c.uuid in action.uuids:
                    self.beginRemoveRows(self._trash_index(), row, row)
                    self._trash.remove_child(c)
                    self.endRemoveRows()

                    self.beginInsertRows(QModelIndex(), len(self._root.children), len(self._root.children))
                    self._root.append_child(c)
                    self.endInsertRows()

        elif isinstance(action, RestorePermanentlyDeletedAction):
            for e in action.deleted_entities:
                if isinstance(e.restored_entity, _Catalogue):
                    node = CatalogNode(e.restored_entity)
                    if e.restored_entity.is_removed():
                        self.beginInsertRows(self._trash_index(), len(self._trash.children), len(self._trash.children))
                        self._trash.append_child(node)
                        self.endInsertRows()
                    else:
                        self.beginInsertRows(QModelIndex(), len(self._root.children), len(self._root.children))
                        self._root.append_child(node)
                        self.endInsertRows()

        elif isinstance(action, (SetAttributeAction, DeleteAttributeAction)):
            for c in filter(lambda x: isinstance(x, _Catalogue), action.entities):
                assert isinstance(c, _Catalogue)
                for row, child in enumerate(self._root.children):
                    if isinstance(child, CatalogNode) and child.uuid == c.uuid:
                        child.node = c
                        index = self.index(row, 0, QModelIndex())
                        self.dataChanged.emit(index, index)

                for row, child in enumerate(self._trash.children):
                    if isinstance(child, CatalogNode) and child.uuid == c.uuid:
                        child.node = c
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

            assert isinstance(child, CatalogNode)
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

    def index(self, row: int, column: int,
              parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> QModelIndex:
        if self.hasIndex(row, column, parent):
            if not parent.isValid():
                parent_item: Node = self._root
            else:
                parent_item: Node = parent.internalPointer()  # type: ignore

            child_item: Node = parent_item.children[row]
            if child_item is not None:
                return self.createIndex(row, column, child_item)
        return QModelIndex()

    def parent(self, index: Union[QModelIndex, QPersistentModelIndex]) -> QModelIndex:  # type: ignore
        if not index.isValid():
            return QModelIndex()
        assert isinstance(index.internalPointer(), Node)
        child_item = cast(Node, index.internalPointer())
        assert isinstance(child_item.parent, Node)
        parent_item: Node = child_item.parent
        if parent_item not in (None, self._root):
            return self.createIndex(parent_item.row, 0, parent_item)
        return QModelIndex()

    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> int:  # type: ignore
        if parent.column() > 0:
            return 0
        parent_node: Node
        if not parent.isValid():
            parent_node = self._root
        else:
            parent_node = cast(Node, parent.internalPointer())

        if isinstance(parent_node, CatalogNode):
            return 0
        else:
            return len(parent_node.children)

    def columnCount(self, parent: Union[QModelIndex, QPersistentModelIndex]) -> int:  # type: ignore
        return 1

    def data(self, index: Union[QModelIndex, QPersistentModelIndex],
             role: Qt.ItemDataRole = Qt.DisplayRole) -> Any:  # type: ignore
        if index.isValid():
            item = cast(NamedNode, index.internalPointer())
            if role == Qt.ItemDataRole.DisplayRole:
                return item.name
            elif role == UUIDDataRole:
                if isinstance(item, CatalogNode):
                    return item.uuid
            elif role == EntityRole:
                if isinstance(item, CatalogNode):
                    return item.node

    def flags(self, index: Union[QModelIndex, QPersistentModelIndex]) -> Qt.ItemFlag:
        if index.isValid():
            item = cast(Node, index.internalPointer())
            return item.flags()
        return Qt.ItemFlag.NoItemFlags

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
                                              pickle.loads(
                                                  data.data('application/x-tscat-event-uuid-list')))  # type: ignore

        return True

    def mimeTypes(self) -> List[str]:
        return super().mimeTypes() + ['text/uri-list']

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        mime_data = super().mimeData(indexes)

        urls: List[QUrl] = []
        for index in indexes:
            now = dt.datetime.now().isoformat()
            catalogue = self.data(index, EntityRole)

            path = os.path.join(tempfile.gettempdir(), 'tscat_gui', f'{catalogue.name}-{now}-export.json')
            os.makedirs(os.path.dirname(path), exist_ok=True)

            print('exporting', catalogue, path)
            result = export_to_json(path, [catalogue.uuid])

            if result is None:
                path_url = QUrl.fromLocalFile(path)
                urls.append(path_url)

        mime_data.setUrls(urls)

        print('dragging')

        return mime_data
