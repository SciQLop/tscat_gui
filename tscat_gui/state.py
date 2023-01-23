from PySide6 import QtGui
from PySide6 import QtCore

import copy
import dataclasses
from typing import Union, Type, Optional, Sequence

import tscat

from .logger import log


@dataclasses.dataclass
class SelectState:
    selected: Sequence[str]
    type: Union[Type[tscat._Catalogue], Type[tscat._Event]]
    selected_catalogues: Sequence[str]


class AppState(QtCore.QObject):
    state_changed = QtCore.Signal(str, type, list)

    undo_stack_clean_changed = QtCore.Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._select_state = SelectState([], tscat._Catalogue, [])

        self._undo_stack = QtGui.QUndoStack()
        self._undo_stack.cleanChanged.connect(lambda x: self.undo_stack_clean_changed.emit(x))  # type: ignore

    def push_undo_command(self, cls, *args) -> None:
        self._undo_stack.push(cls(self, *args))

    def set_undo_stack_clean(self):
        self._undo_stack.setClean()

    def create_undo_redo_action(self):
        return self._undo_stack.createUndoAction(self), self._undo_stack.createRedoAction(self)

    def select_state(self) -> SelectState:
        return copy.deepcopy(self._select_state)

    def updated(self, action: str, ty: Union[Type[tscat._Catalogue], Type[tscat._Event]],
                uuids: Optional[Sequence[str]]) -> None:
        if action == 'active_select':
            if uuids != self._select_state.selected:
                self._select_state.selected = uuids[:]
                self._select_state.type = ty

                if self._select_state.type == tscat._Catalogue:
                    self._select_state.selected_catalogues = uuids[:]
            else:
                log.debug(f'already active "{uuids}"')

        log.debug(f'app-state-updated action:{action}, type:{ty}, uuids:{uuids}')
        self.state_changed.emit(action, ty, uuids)
