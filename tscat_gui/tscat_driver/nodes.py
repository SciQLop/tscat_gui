from typing import Sequence, Union, Optional

from tscat import _Event, _Catalogue


class Node:
    def __init__(self, name: str, children: Sequence[Union['Node', 'CatalogNode']], parent: Optional['Node'] = None):
        self._name = name
        self.children = children
        self._parent = parent

    def set_parent(self, parent):
        self._parent = parent

    @property
    def name(self) -> str:
        return self._name

    @property
    def parent(self) -> Optional['Node']:
        return self._parent

    @property
    def children(self) -> Sequence['Node']:
        return self._children

    @children.setter
    def children(self, children):
        self._children = children
        list(map(lambda child: child.set_parent(self), children))

    @property
    def row(self):
        if self._parent is not None:
            return self._parent.children.index(self)
        return 0


class EventNode:
    def __init__(self, event: _Event):
        self._node = event

    @property
    def uuid(self):
        return self._node.uuid


class CatalogNode(Node):
    def __init__(self, catalog: _Catalogue, events: Sequence[EventNode]):
        super().__init__(name=catalog.name, children=events)
        self._node = catalog

    @property
    def uuid(self):
        return self._node.uuid
