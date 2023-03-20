from typing import Union, Sequence, List, Any, Type

from PySide6.QtCore import QObject, QAbstractItemModel, Signal
from tscat import _Catalogue, _Event

from .actions import Action, CreateEntityAction, RemoveEntityAction
from .nodes import CatalogNode, EventNode
from .tscat_root_model import TscatRootModel


class _Model(QObject):
    action_done = Signal(Action)

    def __init__(self):
        super().__init__(None)

        self._tscat_root = TscatRootModel()

        from .driver import tscat_driver
        tscat_driver.action_done.connect(self._action_done)

    def _action_done(self, action: Action) -> None:
        if action.user_callback:
            action.user_callback(action)
        self.action_done.emit(action)

    def catalog(self, uid: str) -> QAbstractItemModel:
        return self._tscat_root.catalog(uid)

    def tscat_root(self) -> QAbstractItemModel:
        return self._tscat_root

    @staticmethod
    def do(action: Action) -> None:
        from .driver import tscat_driver
        return tscat_driver.do(action)

    @staticmethod
    def entities_from_uuids(uuids: Sequence[str]) -> List[Union[CatalogNode, EventNode]]:
        from .driver import tscat_driver
        return list(map(tscat_driver.entity_from_uuid, uuids))

tscat_model = _Model()
