from PySide6.QtCore import QAbstractItemModel

from .tscat_root_model import TscatRootModel


class Model:

    def __init__(self):
        self._tscat_root = TscatRootModel()

    def catalog(self, uid: str) -> QAbstractItemModel:
        return self._tscat_root.catalog(uid)

    def tscat_root(self) -> QAbstractItemModel:
        return self._tscat_root
