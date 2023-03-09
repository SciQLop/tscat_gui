from PySide6.QtCore import QAbstractTableModel

from .nodes import CatalogNode


class CatalogModel(QAbstractTableModel):
    def __init__(self, root: CatalogNode):
        super().__init__()
        self._root = root

    def update(self, root: CatalogNode):
        self.beginResetModel()
        self._root = root
        self.endResetModel()
