import abc
from abc import ABC
from typing import Optional, Sequence, List

from PySide6 import QtCore
from tscat import _Event, _Catalogue


class Node(ABC):
    def __init__(self) -> None:
        self._parent: Optional['Node'] = None
        self._children: List['Node'] = []

    @property
    def parent(self) -> Optional['Node']:
        return self._parent

    @parent.setter
    def parent(self, parent: 'Node') -> None:
        if self._parent is not None and self._parent != parent:  # reparenting forbidden
            print('reparenting', self, self._parent, parent)
        self._parent = parent

    @property
    def children(self) -> Sequence['Node']:
        return self._children

    def set_children(self, children: Sequence['Node']) -> None:
        self._children = []
        self.append_children(children)

    def append_children(self, children: Sequence['Node']) -> None:
        self._children += children
        for child in children:
            child.parent = self

    def append_child(self, child) -> None:
        self._children.append(child)
        child.parent = self

    def remove_child(self, child) -> None:
        self._children.remove(child)
        child.parent = None

    @property
    def row(self):
        if self._parent is not None:
            return self._parent.children.index(self)
        return 0

    def flags(self):
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable  # type: ignore

    @property
    @abc.abstractmethod
    def uuid(self) -> str:
        pass


class RootNode(Node):
    def __init__(self):
        super().__init__()

    @property
    def uuid(self) -> str:
        return '00000000-0000-0000-0000-000000000000'

    def flags(self):
        return QtCore.Qt.NoItemFlags


class NamedNode(Node, ABC):
    def __init__(self):
        super().__init__()

    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass


class TrashNode(NamedNode):
    def __init__(self):
        super().__init__()

    @property
    def uuid(self) -> str:
        return '00000000-0000-0000-0000-000000000000'

    @property
    def name(self) -> str:
        return "Trash"

    def flags(self):
        return QtCore.Qt.ItemIsEnabled


class EventNode(Node):
    def __init__(self, event: _Event):
        super().__init__()
        self._entity = event

    @property
    def uuid(self) -> str:
        return self._entity.uuid

    @property
    def node(self) -> _Event:
        return self._entity

    @node.setter
    def node(self, entity: _Event) -> None:
        self._entity = entity

    def flags(self):
        return super().flags() | QtCore.Qt.ItemIsDragEnabled  # type: ignore


class CatalogNode(NamedNode):
    def __init__(self, catalog: _Catalogue):
        super().__init__()
        self._entity = catalog

    @property
    def uuid(self) -> str:
        return self._entity.uuid

    @property
    def node(self) -> _Catalogue:
        return self._entity

    @node.setter
    def node(self, entity: _Catalogue) -> None:
        self._entity = entity

    @property
    def name(self) -> str:
        return self._entity.name

    def flags(self):
        return super().flags() | QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled  # type: ignore
