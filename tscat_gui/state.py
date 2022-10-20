from PySide6 import QtWidgets, QtGui
from PySide6 import QtCore

import tscat

from typing import Union, Type
import dataclasses

from .logger import log


@dataclasses.dataclass
class SelectState:
    active: str
    type: Union[Type[tscat._Catalogue], Type[tscat._Event]]
    active_catalogue: str


class AppState(QtCore.QObject):
    state_changed = QtCore.Signal(str, type, str)

    undo_stack_clean_changed = QtCore.Signal(bool)

    def __init__(self):
        super().__init__()
        self.active: str = None
        self.active_type = tscat._Catalogue
        self.active_catalogue: str = None

        self._undo_stack = QtGui.QUndoStack()
        self._undo_stack.cleanChanged.connect(lambda x: self.undo_stack_clean_changed.emit(x))

    def push_undo_command(self, cls, *args) -> None:
        self._undo_stack.push(cls(self, *args))

    def set_undo_stack_clean(self):
        self._undo_stack.setClean()

    def create_undo_redo_action(self):
        return self._undo_stack.createUndoAction(self), self._undo_stack.createRedoAction(self)

    def select_state(self) -> SelectState:
        return SelectState(self.active, self.active_type, self.active_catalogue)

    def updated(self, action: str, type: Union[Type[tscat._Catalogue], Type[tscat._Event]], uuid: str) -> None:
        if action == 'active_select':
            if uuid != self.active:
                self.active = uuid
                self.active_type = type

                if self.active_type == tscat._Catalogue:
                    self.active_catalogue = uuid
            else:
                log.debug(f'already active "{uuid}"')

        log.debug(f'app-state-updated action:{action}, type:{type}, uuid:{uuid}')
        self.state_changed.emit(action, type, uuid)
