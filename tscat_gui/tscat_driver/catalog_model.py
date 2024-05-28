import pickle
from typing import Any, List, Optional, Sequence, Union

from PySide6.QtCore import QAbstractTableModel, QMimeData, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QColor

from tscat import _Event, _Catalogue
from .actions import Action, AddEventsToCatalogueAction, DeleteAttributeAction, DeletePermanentlyAction, \
    GetCatalogueAction, MoveToTrashAction, RemoveEntitiesAction, RemoveEventsFromCatalogueAction, \
    RestoreFromTrashAction, RestorePermanentlyDeletedAction, SetAttributeAction
from .driver import tscat_driver
from .nodes import CatalogNode, EventNode, TrashNode
from ..model_base.constants import EntityRole, UUIDDataRole


class CatalogModel(QAbstractTableModel):
    _columns = ['start', 'stop', 'author', 'tags', 'products', 'rating']

    def __init__(self, root: CatalogNode):
        super().__init__()
        self._root = root
        self._trash = TrashNode()
        tscat_driver.action_done_prioritised.connect(self._driver_action_done, Qt.QueuedConnection)

    def _driver_action_done(self, action: Action) -> None:
        if isinstance(action, GetCatalogueAction):
            if action.uuid == self._root.uuid:
                children = [EventNode(e, i.assigned) for e, i in zip(action.events, action.query_info)]
                if action.removed_items:
                    # unused for now
                    self._trash.set_children(children)
                else:
                    self.beginResetModel()
                    self._root.set_children(children)
                    self.endResetModel()

        elif isinstance(action, (SetAttributeAction, DeleteAttributeAction)):
            for e in filter(lambda x: isinstance(x, _Event), action.entities):
                for node in (self._root, self._trash):
                    for row, child in enumerate(node.children):
                        if isinstance(child, EventNode) and child.uuid == e.uuid:
                            child.node = e

                            if node == self._root:  # update model only for visible nodes
                                index_left = self.index(row, 0, QModelIndex())
                                index_right = self.index(row, self.columnCount() - 1, QModelIndex())
                                self.dataChanged.emit(index_left, index_right)  # type: ignore

            if action.name == 'predicate':
                for c in filter(lambda x: isinstance(x, _Catalogue), action.entities):
                    if c.uuid == self._root.uuid:
                        self.refresh()

        elif isinstance(action, AddEventsToCatalogueAction):
            if action.catalogue_uuid == self._root.uuid:
                nodes = list(map(lambda x: EventNode(x, True), map(tscat_driver.event_from_uuid, action.uuids)))

                removed_nodes = list(filter(lambda x: x.node.is_removed(), nodes))
                nodes = list(filter(lambda x: not x.node.is_removed(), nodes))

                self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount() + len(nodes) - 1)
                self._root.append_children(nodes)
                self.endInsertRows()

                self._trash.append_children(removed_nodes)

        elif isinstance(action, RestorePermanentlyDeletedAction):
            removed_nodes: List[EventNode] = []  # type: ignore
            nodes: List[EventNode] = []  # type: ignore
            for e in action.deleted_entities:
                if e.type == _Event:
                    event_node = EventNode(e.restored_entity, True)
                    if e.restored_entity.is_removed():
                        removed_nodes.append(event_node)
                    else:
                        nodes.append(event_node)

            self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount() + len(nodes) - 1)
            self._root.append_children(nodes)
            self.endInsertRows()

            self._trash.append_children(removed_nodes)

        elif isinstance(action, RemoveEventsFromCatalogueAction):
            if action.catalogue_uuid == self._root.uuid:
                for row, c in reversed(list(enumerate(self._root.children))):
                    for e in action.uuids:
                        if c.uuid == e:
                            self.beginRemoveRows(QModelIndex(), row, row)
                            self._root.remove_child(c)
                            self.endRemoveRows()
                for c in self._trash.children[:]:
                    for e in action.uuids:
                        if c.uuid == e:
                            self._trash.remove_child(c)

        elif isinstance(action, (RemoveEntitiesAction, DeletePermanentlyAction)):
            for row, c in reversed(list(enumerate(self._root.children))):
                if c.uuid in action.uuids:
                    self.beginRemoveRows(QModelIndex(), row, row)
                    self._root.remove_child(c)
                    self.endRemoveRows()

            for c in self._trash.children[:]:
                if c.uuid in action.uuids:
                    self._trash.remove_child(c)

        elif isinstance(action, MoveToTrashAction):
            for row, c in reversed(list(enumerate(self._root.children))):
                if c.uuid in action.uuids:
                    self.beginRemoveRows(QModelIndex(), row, row)
                    self._root.remove_child(c)
                    self.endRemoveRows()
                    self._trash.append_child(c)

        elif isinstance(action, RestoreFromTrashAction):
            nodes = []  # type: ignore
            for c in self._trash.children[:]:
                if c.uuid in action.uuids:
                    self._trash.remove_child(c)
                    nodes.append(c)  # type: ignore

            if nodes:
                self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount() + len(nodes) - 1)
                self._root.append_children(nodes)
                self.endInsertRows()

    def refresh(self):
        tscat_driver.do(GetCatalogueAction(None, self._root.uuid))

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.DisplayRole) -> Any:  # type: ignore
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.DisplayRole:  # type: ignore
                if section < len(self._columns):
                    return self._columns[section].title()
                else:
                    return "Attributes"
        return None

    def columnCount(self, parent: Optional[Union[QModelIndex, QPersistentModelIndex]] = None) -> int:
        return len(self._columns) + 1

    def rowCount(self, parent: Optional[Union[QModelIndex, QPersistentModelIndex]] = None) -> int:
        return len(self._root.children)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:  # type: ignore
        if index.isValid():
            node = self._root.children[index.row()]
            return node.flags()

        return Qt.NoItemFlags  # type: ignore

    def data(self, index: Union[QModelIndex, QPersistentModelIndex],
             role: int = Qt.DisplayRole):  # type: ignore
        if not index.isValid():
            return None

        child = self._root.children[index.row()]
        assert isinstance(child, EventNode)

        if role == Qt.DisplayRole:  # type: ignore
            if index.column() < len(self._columns):
                key = self._columns[index.column()]
                return str(child.node.__dict__[key])
            else:
                return str(child.node.variable_attributes())
        elif role == Qt.BackgroundRole:  # type: ignore
            if not child.is_assigned():
                return QColor(Qt.lightGray)  # type: ignore
        elif role == UUIDDataRole:
            return child.uuid
        elif role == EntityRole:
            return child.node

        return None

    def index_from_uuid(self, uuid: str, parent=QModelIndex()) -> QModelIndex:
        for row, event in enumerate(self._root.children):
            if event.uuid == uuid:
                return self.index(row, 0)
        return QModelIndex()

    def mimeTypes(self) -> List[str]:
        return super().mimeTypes() + ['application/x-tscat-event-uuid-list']

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        mime_data = super().mimeData(indexes)
        mime_data.setData('application/x-tscat-event-uuid-list',
                          pickle.dumps([index.data(UUIDDataRole) for index in indexes if index.column() == 0]))
        return mime_data
