import pickle
from typing import Optional, Union, List, Sequence, Any

from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex, QPersistentModelIndex, QMimeData
from tscat import _Event

from .actions import GetCatalogueAction, Action, SetAttributeAction, DeleteAttributeAction, AddEventsToCatalogueAction, RemoveEntityAction, RemoveEventsFromCatalogueAction
from .driver import tscat_driver
from .nodes import CatalogNode, EventNode
from ..model_base.constants import UUIDDataRole, EntityRole


class CatalogModel(QAbstractTableModel):
    _columns = ['start', 'stop', 'author', 'tags', 'products']

    def __init__(self, root: CatalogNode):
        super().__init__()
        self._root = root
        tscat_driver.action_done.connect(self._driver_action_done)

    def _driver_action_done(self, action: Action) -> None:
        if isinstance(action, GetCatalogueAction):
            if action.uuid == self._root.uuid:
                self.beginResetModel()
                self._root.children = list(map(EventNode, action.events))
                self.endResetModel()

        elif isinstance(action, (SetAttributeAction, DeleteAttributeAction)):
            for e in filter(lambda x: isinstance(x, _Event), action.entities):
                for row, child in enumerate(self._root.children):
                    if child.uuid == e.uuid:
                        child.node = e
                        index_left = self.index(row, 0, QModelIndex())
                        index_right = self.index(row, self.columnCount(), QModelIndex())
                        self.dataChanged.emit(index_left, index_right)

        elif isinstance(action, AddEventsToCatalogueAction):
            if action.catalogue_uuid == self._root.uuid:
                self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount() + len(action.uuids) - 1)
                self._root.children += list(map(EventNode, map(tscat_driver.entity_from_uuid, action.uuids)))
                self.endInsertRows()

        elif isinstance(action, RemoveEventsFromCatalogueAction):
            if action.catalogue_uuid == self._root.uuid:
                for row, c in enumerate(self._root.children[::-1]):
                    for e in action.uuids:
                        if c.uuid == e:
                            self.beginRemoveRows(QModelIndex(), row, row)
                            self._root.children.remove(c)
                            self.endRemoveRows()

        elif isinstance(action, RemoveEntityAction):
            for row, c in enumerate(self._root.children[::-1]):
                if c.uuid == action.uuid:
                    self.beginRemoveRows(QModelIndex(), row, row)
                    self._root.children.remove(c)
                    self.endRemoveRows()


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
            return super().flags(index) | Qt.ItemIsDragEnabled  # type: ignore
        return Qt.NoItemFlags  # type: ignore

    def data(self, index: Union[QModelIndex, QPersistentModelIndex],
             role: int = Qt.DisplayRole):  # type: ignore
        if role == Qt.DisplayRole:  # type: ignore
            if index.column() < len(self._columns):
                key = self._columns[index.column()]
                return str(self._root.children[index.row()].node.__dict__[key])
            else:
                return str(self._root.children[index.row()].node.variable_attributes())
        elif role == UUIDDataRole:
            return self._root.children[index.row()].uuid
        elif role == EntityRole:
            return self._root.children[index.row()].node

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
