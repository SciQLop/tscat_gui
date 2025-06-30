import copy
import dataclasses
from typing import List, Type, Union

from PySide6 import QtCore, QtGui

import tscat
from .logger import log


@dataclasses.dataclass
class SelectState:
    selected: List[str]
    type: Union[Type[tscat._Catalogue], Type[tscat._Event]]
    selected_catalogues: List[str]
    catalogue_path: List[str]


class AppState(QtCore.QObject):
    state_changed = QtCore.Signal(str, type, list)

    undo_stack_clean_changed = QtCore.Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._select_state = SelectState([], tscat._Catalogue, [], [])

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

    def undo_stack(self) -> QtGui.QUndoStack:
        return self._undo_stack

    def updated(self, action: str, ty: Union[Type[tscat._Catalogue], Type[tscat._Event]],
                uuids: List[str]) -> None:
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

    def set_catalogue_path(self, path: List[str]) -> None:
        self._select_state.catalogue_path = path

    def current_catalogue_path(self) -> List[str]:
        return self._select_state.catalogue_path
