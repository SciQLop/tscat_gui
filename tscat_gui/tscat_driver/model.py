from typing import Union, Sequence, List

from PySide6.QtCore import QObject, QAbstractItemModel, Signal, Qt
from tscat import _Event, _Catalogue

from .actions import Action
from .tscat_root_model import TscatRootModel


class _Model(QObject):
    action_done = Signal(Action)

    def __init__(self):
        super().__init__(None)

        self._tscat_root = TscatRootModel()

        from .driver import tscat_driver
        tscat_driver.action_done.connect(self._action_done, Qt.QueuedConnection)

    def _action_done(self, action: Action) -> None:
        self.action_done.emit(action)
        if action.user_callback:
            action.user_callback(action)

    def catalog(self, uid: str) -> QAbstractItemModel:
        return self._tscat_root.catalog(uid)

    def tscat_root(self) -> TscatRootModel:
        return self._tscat_root

    @staticmethod
    def do(action: Action) -> None:
        from .driver import tscat_driver
        return tscat_driver.do(action)

    @staticmethod
    def entities_from_uuids(uuids: Sequence[str]) -> List[Union[_Catalogue, _Event]]:
        from .driver import tscat_driver
        return list(map(tscat_driver.entity_from_uuid, uuids))


tscat_model = _Model()
