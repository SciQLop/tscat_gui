import abc

from PySide6 import QtCore

import tscat
from typing import Any, List, Optional, cast, Union

from .utils.helper import get_entity_from_uuid_safe
from .state import AppState

UUIDRole = QtCore.Qt.UserRole + 1  # type: ignore


class _Item:
    def __init__(self, parent, items: Optional[List]):
        self._parent = parent
        self._items = items if items else []

    def flags(self):
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable  # type: ignore

    def child(self, row: int):
        return self._items[row]

    def child_count(self) -> int:
        return len(self._items)

    def index_of(self, item):
        return self._items.index(item)

    def row(self):
        return self._parent.index_of(self)

    def parent(self):
        return self._parent

    @abc.abstractmethod
    def text(self) -> str:
        pass


class _AllEvents(_Item):
    def __init__(self, parent):
        super().__init__(parent)

    def text(self):
        return "All Events"


class _Separator(_Item):
    def __init__(self, parent):
        super().__init__(parent)

    def text(self):
        return '---'


class _Catalogue(_Item):
    def __init__(self, parent, uuid: str):
        super().__init__(parent, [])

        self._uuid = uuid

    def text(self):
        return get_entity_from_uuid_safe(self._uuid).name

    def uuid(self):
        return self._uuid


def _get_catalogues(parent, removed_items: bool) -> list[_Catalogue]:
    return [_Catalogue(parent, c.uuid)
            for c in tscat.get_catalogues(removed_items=removed_items)]


class _AllRemovedEvent(_Item):
    def __init__(self, parent):
        super().__init__(parent)

    def text(self):
        return "All Removed Events"


class _Trash(_Item):
    def __init__(self, parent):
        super().__init__(parent,
                         [
                             # _AllRemovedEvent(self),
                             *_get_catalogues(self, removed_items=True)
                         ])

    def text(self):
        return "Trash"

    def flags(self):
        return QtCore.Qt.ItemIsEnabled


class _Root(_Item):
    def __init__(self):
        super().__init__(None,
                         [
                             *_get_catalogues(self, removed_items=False),
                             _Trash(self),
                         ])

    def trash_node(self):
        return self._items[-1]

    # def item_from_uuid(self, uuid: str):
    #     for item in self.items + self.items[-1].items:
    #         if type(item) is _Catalogue and item.uuid() == uuid:
    #             return item
    #     return None


class CatalogueModel(QtCore.QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._root = _Root()

    def reset(self):
        self.beginResetModel()
        self._root = _Root()
        self.endResetModel()

    def index(self, row, column, parent):  # type: ignore
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            item = self._root
        else:
            item = parent.internalPointer()

        child = item.child(row)
        return self.createIndex(row, column, child)

    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:  # type: ignore
        if not index.isValid():
            return QtCore.QModelIndex()

        item = cast(_Item, index.internalPointer())
        parent = item.parent()
        if parent == self._root:
            return QtCore.QModelIndex()

        return self.createIndex(parent.row(), 0, parent)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:  # type: ignore
        return 1

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:  # type: ignore
        if not parent.isValid():  # root
            return self._root.child_count()
        else:
            return cast(_Item, parent.internalPointer()).child_count()

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlags:  # type: ignore
        if index.isValid():
            return cast(_Item, index.internalPointer()).flags()
        return QtCore.Qt.NoItemFlags  # type: ignore

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole) -> Any:  # type: ignore
        if index.isValid():
            item = cast(_Item, index.internalPointer())
        else:
            item = self._root

        if role == QtCore.Qt.DisplayRole:  # type: ignore
            return item.text()
        elif role == UUIDRole:
            if isinstance(index.internalPointer(), _Catalogue):
                return cast(_Catalogue, index.internalPointer()).uuid()

        return None

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation,
                   role: int = QtCore.Qt.DisplayRole) -> Any:  # type: ignore
        if role == QtCore.Qt.DisplayRole:  # type: ignore
            return "Catalogues"
        return None

    def index_from_uuid(self, uuid: str, parent=QtCore.QModelIndex()) -> QtCore.QModelIndex:
        for i in range(self.rowCount(parent)):
            index = self.index(i, 0, parent)
            if self.data(index, UUIDRole) == uuid:
                return index
            if self.rowCount(index) > 0:
                result = self.index_from_uuid(uuid, index)
                if result != QtCore.QModelIndex():
                    return result
        return QtCore.QModelIndex()


class EventModel(QtCore.QAbstractTableModel):
    _columns = ['start', 'stop', 'author', 'tags', 'products']

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)

        self.catalogue_uuid = None
        self.events: List[tscat._Event] = []

        state.state_changed.connect(self.set_catalogue)

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation,
                   role: int = QtCore.Qt.DisplayRole) -> Any:  # type: ignore
        if orientation == QtCore.Qt.Orientation.Horizontal:
            if role == QtCore.Qt.DisplayRole:  # type: ignore
                if section < len(self._columns):
                    return self._columns[section].title()
                else:
                    return "Attributes"
        return None

    def columnCount(self, parent: Union[QtCore.QModelIndex, QtCore.QPersistentModelIndex] = None) -> int:
        return len(self._columns) + 1

    def rowCount(self, parent: Union[QtCore.QModelIndex, QtCore.QPersistentModelIndex] = None) -> int:
        return len(self.events)

    def data(self, index: Union[QtCore.QModelIndex, QtCore.QPersistentModelIndex], role: int = QtCore.Qt.DisplayRole):  # type: ignore
        if role == QtCore.Qt.DisplayRole:  # type: ignore
            if index.column() < len(self._columns):
                key = self._columns[index.column()]
                return str(self.events[index.row()].__dict__[key])
            else:
                return str(self.events[index.row()].variable_attributes())
        elif role == UUIDRole:
            return self.events[index.row()].uuid

        return None

    def reset(self):
        self.beginResetModel()
        self.events = []
        if self.catalogue_uuid:
            catalogue = get_entity_from_uuid_safe(self.catalogue_uuid)
            if catalogue:
                self.events = tscat.get_events(catalogue)
        self.endResetModel()

    def set_catalogue(self, command, type, uuid):
        if command in ['active_select', 'passive_select'] and type == tscat._Catalogue:
            self.catalogue_uuid = uuid
            self.reset()

    def index_from_uuid(self, uuid: str, parent=QtCore.QModelIndex()) -> QtCore.QModelIndex:
        for row, event in enumerate(self.events):
            if event.uuid == uuid:
                return self.index(row, 0)
        return QtCore.QModelIndex()
