from abc import ABC
from typing import Sequence, Optional

from tscat import _Event, _Catalogue


class Node:
    def __init__(self, children: Sequence['Node']) -> None:
        self._parent = None
        self.children = children

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

    @children.setter
    def children(self, children) -> None:
        self._children = children
        for child in children:
            child.parent = self

    @property
    def row(self):
        if self._parent is not None:
            return self._parent.children.index(self)
        return 0


class NamedNode(Node, ABC):
    def __init__(self, children: Sequence['Node']):
        Node.__init__(self,children)

    @property
    def name(self) -> str:
        ...


class EventNode(Node):
    def __init__(self, event: _Event):
        super().__init__([])
        self._entity = event

    @property
    def uuid(self):
        return self._entity.uuid

    @property
    def node(self):
        return self._entity

    @node.setter
    def node(self, entity) -> None:
        self._entity = entity


class CatalogNode(NamedNode):
    def __init__(self, catalog: _Catalogue):
        super().__init__([])
        self._entity = catalog

    @property
    def uuid(self):
        return self._entity.uuid

    @property
    def node(self):
        return self._entity

    @node.setter
    def node(self, entity) -> None:
        self._entity = entity

    @property
    def name(self) -> str:
        return self._entity.name
