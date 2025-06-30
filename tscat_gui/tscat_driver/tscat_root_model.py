import datetime as dt
import os
import pickle
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Set, Union, cast

from PySide6.QtCore import QAbstractItemModel, QMimeData, QModelIndex, QPersistentModelIndex, QUrl, Qt, Signal
from PySide6.QtWidgets import QApplication, QStyle

from tscat import _Catalogue
from .actions import Action, CreateEntityAction, DeleteAttributeAction, DeletePermanentlyAction, GetCatalogueAction, \
    GetCataloguesAction, ImportCanonicalizedDictAction, MoveToTrashAction, RemoveEntitiesAction, \
    RestoreFromTrashAction, RestorePermanentlyDeletedAction, SetAttributeAction
from .catalog_model import CatalogModel
from .driver import tscat_driver
from .nodes import CatalogNode, FolderNode, NamedNode, Node, RootNode, TrashNode
from ..model_base.constants import EntityRole, PathAttributeName, UUIDDataRole
from ..utils.import_export import export_to_json


class TscatRootModel(QAbstractItemModel):
    events_dropped_on_catalogue = Signal(str, list)
    catalogues_dropped_on_folder = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._root = RootNode()
        self._trash = TrashNode()

        self._root.append_child(self._trash)

        self._catalogues: Dict[str, CatalogModel] = {}

        self.expanded_indexes: Set[QModelIndex] = set()

        tscat_driver.action_done_prioritised.connect(self._driver_action_done, Qt.QueuedConnection)

        tscat_driver.do(GetCataloguesAction(None, False))
        tscat_driver.do(GetCataloguesAction(None, True))

    def collapsed(self, index: QModelIndex) -> None:
        self.expanded_indexes.remove(index)
        self.dataChanged.emit(index, Qt.DecorationRole)  # type: ignore

    def expanded(self, index: QModelIndex) -> None:
        self.expanded_indexes.add(index)
        self.dataChanged.emit(index, Qt.DecorationRole)  # type: ignore

    def _trash_index(self) -> QModelIndex:
        return self.index(0, 0, QModelIndex())

    def node_from_path(self, path: List[str], create_index_for_new_folders: bool) -> Node:
        parent = self._root
        for folder in path:
            for child in parent.children:
                if isinstance(child, FolderNode) and child.name == folder:
                    parent = child
                    break
            else:
                if create_index_for_new_folders:
                    parent_index = self._index_from_node(parent)
                    self.beginInsertRows(parent_index, len(parent.children), len(parent.children))

                new_folder = FolderNode(folder)
                parent.append_child(new_folder)
                parent = new_folder

                if create_index_for_new_folders:
                    self.endInsertRows()

        return parent

    def _node_from_catalogue_path(self, c: _Catalogue, create_index_for_new_folders: bool = False) -> Node:
        parent = self._root
        if hasattr(c, PathAttributeName) and isinstance(getattr(c, PathAttributeName), list) and \
            all(isinstance(x, str) for x in getattr(c, PathAttributeName)):
            parent = self.node_from_path(getattr(c, PathAttributeName), create_index_for_new_folders)

        return parent

    def _node_from_uuid(self, uuid: str) -> Optional[CatalogNode]:
        stack = [self._root]

        while stack:
            node = stack.pop()
            if isinstance(node, (CatalogNode, FolderNode)) and node.uuid == uuid:
                return node

            # we do not want to search in Catalogue's children, they are events
            if not isinstance(node, CatalogNode):
                stack.extend(node.children)

        return None

    def _index_from_node(self, node: Node) -> QModelIndex:
        if node.parent is None:
            return QModelIndex()

        return self.index(node.row, 0, self._index_from_node(node.parent))

    def _get_node_from_uuid_and_remove_from_tree(self, uuid: str) -> Optional[CatalogNode]:
        node = self._node_from_uuid(uuid)
        if node is None:
            return None

        index = self._index_from_node(node)

        self.beginRemoveRows(index.parent(), index.row(), index.row())
        node.parent.remove_child(node)
        self.endRemoveRows()

        return node

    def _insert_catalogue_node_at_node_path_or_trash(self, node: CatalogNode) -> None:
        if node.node.is_removed():  # undelete to Trash
            parent_node = self._trash
        else:
            parent_node = self._node_from_catalogue_path(node.node, create_index_for_new_folders=True)
        parent_index = self._index_from_node(parent_node)

        self.beginInsertRows(parent_index, len(parent_node.children), len(parent_node.children))
        parent_node.append_child(node)
        self.endInsertRows()

    def index_from_uuid(self, uuid: str) -> QModelIndex:
        node = self._node_from_uuid(uuid)
        if node is None:
            return QModelIndex()
        return self._index_from_node(node)

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

                for c in action.catalogues:
                    parent_node = self._node_from_catalogue_path(c)
                    parent_node.append_child(CatalogNode(c))
                self.endResetModel()

        elif isinstance(action, GetCatalogueAction):
            # also search in Trash :D
            index = self.index_from_uuid(action.uuid)
            if index.isValid():
                self.dataChanged.emit(index, index)  # type: ignore

        elif isinstance(action, CreateEntityAction):
            if isinstance(action.entity, _Catalogue):
                node = CatalogNode(action.entity)
                self._insert_catalogue_node_at_node_path_or_trash(node)

        elif isinstance(action, (RemoveEntitiesAction, DeletePermanentlyAction)):
            for uuid in action.uuids:
                node = self._get_node_from_uuid_and_remove_from_tree(uuid)
                if node is None:
                    continue

                # in case a catalogueModel was created for this catalogue, remove it
                if uuid in self._catalogues:
                    self._catalogues[uuid].deleteLater()
                    del self._catalogues[uuid]

        elif isinstance(action, (MoveToTrashAction, RestoreFromTrashAction)):  # Move to Trash exists only for Catalogs
            for uuid, entity in zip(action.uuids, action.entities):
                node = self._get_node_from_uuid_and_remove_from_tree(uuid)
                if node is None:
                    continue

                node.node = entity  # update the node's entity to the new one with the removed flag set

                self._insert_catalogue_node_at_node_path_or_trash(node)

        elif isinstance(action, RestorePermanentlyDeletedAction):
            for e in action.deleted_entities:
                if isinstance(e.restored_entity, _Catalogue):
                    node = CatalogNode(e.restored_entity)
                    self._insert_catalogue_node_at_node_path_or_trash(node)

        elif isinstance(action, (SetAttributeAction, DeleteAttributeAction)):
            for c in filter(lambda x: isinstance(x, _Catalogue), action.entities):
                node = self._node_from_uuid(c.uuid)
                if node is not None:
                    node.node = c

                    if action.name == PathAttributeName:
                        node = self._get_node_from_uuid_and_remove_from_tree(c.uuid)
                        self._insert_catalogue_node_at_node_path_or_trash(node)

                    index = self._index_from_node(node)
                    self.dataChanged.emit(index, index)  # type: ignore

        elif isinstance(action, ImportCanonicalizedDictAction):
            for node in list(map(CatalogNode, action.catalogues)):
                self._insert_catalogue_node_at_node_path_or_trash(node)

    def catalog(self, uuid: str) -> CatalogModel:
        if uuid not in self._catalogues:
            # DFS search for the CatalogNode with the given uuid
            stack = [self._root]

            while stack:
                node = stack.pop()
                if isinstance(node, CatalogNode) and node.uuid == uuid:
                    catalogue_model = CatalogModel(node)
                    self._catalogues[uuid] = catalogue_model
                    tscat_driver.do(GetCatalogueAction(None, removed_items=False, uuid=uuid))
                    break

                if not isinstance(node, CatalogNode):  # we do not want to search in Catalogue's children
                    stack.extend(node.children)

        return self._catalogues[uuid]

    def current_path(self, index: QModelIndex) -> List[str]:
        if not index.isValid():
            return []

        # get the path starting with the parent if the index is a catalogue else starting with the index
        if index.data(EntityRole) is not None:
            index = index.parent()

        path = []

        while index.isValid():
            path.append(index.data())
            index = index.parent()
        return path[::-1]

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

    def columnCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = None) -> int:  # type: ignore
        return 1

    def data(self, index: Union[QModelIndex, QPersistentModelIndex],
             role: Qt.ItemDataRole = Qt.DisplayRole) -> Any:  # type: ignore
        if index.isValid():
            item = cast(NamedNode, index.internalPointer())
            if role == Qt.ItemDataRole.DisplayRole:
                return item.name
            elif role == Qt.DecorationRole:
                if isinstance(item, CatalogNode):
                    return QApplication.style().standardIcon(QStyle.SP_FileIcon)
                elif isinstance(item, FolderNode):
                    if index in self.expanded_indexes:
                        return QApplication.style().standardIcon(QStyle.SP_DirOpenIcon)
                    else:
                        return QApplication.style().standardIcon(QStyle.SP_DirClosedIcon)
                elif isinstance(item, TrashNode):
                    return QApplication.style().standardIcon(QStyle.SP_TrashIcon)

            elif role == UUIDDataRole:
                if isinstance(item, (CatalogNode, FolderNode)):
                    return item.uuid
            elif role == EntityRole:
                if isinstance(item, CatalogNode):
                    return item.node
        return None

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
        # on Catalogues, we can drop events or catalogues (convenient for moving catalogues next to each other)
        if isinstance(parent.data(EntityRole), _Catalogue):
            if data.hasFormat('application/x-tscat-event-uuid-list') or data.hasFormat('application/x-tscat-catalogue-uuid-list'):
                return True
        # on everything else except Trash we can drop catalogues - because it is a FolderNode or Trash
        else:
            if parent != self._trash_index() and data.hasFormat('application/x-tscat-catalogue-uuid-list'):
                return True
        return False

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction,
                     row: int, column: int,
                     parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        if not self.canDropMimeData(data, action, row, column, parent):
            return False

        if action == Qt.DropAction.IgnoreAction:
            return True

        if data.hasFormat('application/x-tscat-event-uuid-list'):
            self.events_dropped_on_catalogue.emit(parent.data(UUIDDataRole),
                                                  pickle.loads(
                                                      data.data('application/x-tscat-event-uuid-list')))  # type: ignore
        elif data.hasFormat('application/x-tscat-catalogue-uuid-list'):  # per canDropMimeData, parent is a FolderNode
            uuids = pickle.loads(data.data('application/x-tscat-catalogue-uuid-list'))
            parent_path = self.current_path(parent)

            # dict keeping the old and new paths of the catalogues in a tuple, keyed by uuid
            catalogues_paths = {}
            for uuid in uuids:
                index = self.index_from_uuid(uuid)

                assert index.isValid()

                all_parents = [parent]
                i = parent
                while i.parent().isValid():
                    all_parents.append(i.parent())
                    i = i.parent()

                # do not allow dropping of path to itself or any of its children
                if index in all_parents:
                    continue

                if index.parent() == parent:  # if the parent is the same, no need to change the path
                    continue

                node = index.internalPointer()
                if isinstance(node, CatalogNode):  # for catalogues the new path is the parent's path
                    catalogues_paths[uuid] = (self.current_path(self._index_from_node(node)), parent_path)
                elif isinstance(node, FolderNode):
                    # for folders the new path for all catalogues below, is the
                    # parent's path + relative path starting at the dragged folder
                    catalogues = self._catalogue_nodes(node)
                    if not catalogues:  # folder with no catalogues in it
                        pass
                    else:
                        for c in catalogues:
                            folder_path = node.full_path()
                            catalogue_path = self.current_path(self._index_from_node(c))
                            catalogues_paths[c.uuid] = (catalogue_path,
                                                        parent_path + catalogue_path[len(folder_path) - 1:])
            # print(json.dumps(catalogues_new_path, indent=4))
            if catalogues_paths:
                self.catalogues_dropped_on_folder.emit(catalogues_paths)

        return True

    def mimeTypes(self) -> List[str]:
        return super().mimeTypes() + ['text/uri-list']

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        mime_data = super().mimeData(indexes)

        # urls: List[QUrl] = []
        # for index in indexes:
        #     now = dt.datetime.now().isoformat()
        #     if index.data(EntityRole) is None:  # for catalogues only, ignore folders
        #         continue

        #     catalogue = self.data(index, EntityRole)

        #     path = os.path.join(tempfile.gettempdir(), 'tscat_gui', f'{catalogue.name}-{now}-export.json')
        #     os.makedirs(os.path.dirname(path), exist_ok=True)

        #     print('exporting', catalogue, path)
        #     result = export_to_json(path, [catalogue.uuid])

        #     if result is None:
        #         path_url = QUrl.fromLocalFile(path)
        #         urls.append(path_url)
        # mime_data.setUrls(urls)

        mime_data.setData('application/x-tscat-catalogue-uuid-list', pickle.dumps([self.data(index, UUIDDataRole)
                                                                                   for index in indexes]))
        return mime_data

    @staticmethod
    def _catalogue_nodes(parent_node: Node) -> List[CatalogNode]:
        stack = list(parent_node.children[:])

        catalogues: List[CatalogNode] = []

        while stack:
            node = stack.pop()
            if isinstance(node, CatalogNode):
                catalogues.append(node)

            if not isinstance(node, (CatalogNode, TrashNode)):  # we do not want to search in Catalogue's children
                stack.extend(node.children)

        return catalogues

    def catalogue_nodes(self, in_trash: bool) -> Sequence[CatalogNode]:
        if in_trash:
            return self._catalogue_nodes(self._trash)
        else:
            return self._catalogue_nodes(self._root)
