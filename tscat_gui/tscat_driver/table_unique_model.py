from typing import List

from PySide6.QtCore import QAbstractTableModel

from .catalog_model import CatalogModel
from ..model_base.constants import UUIDDataRole


class UniqueTableModel(QAbstractTableModel):
    def __init__(self):
        self._models: List[CatalogModel] = []

    def add_model(self, model: CatalogModel) -> None:
        self._models.append(model)

        for i in range(model.rowCount()):
            uuid = model.data(model.index(i, 0), UUIDDataRole)
            print(uuid)
