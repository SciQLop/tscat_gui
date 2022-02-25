from PySide2 import QtWidgets

from typing import Union

import tscat


class _UndoStack(QtWidgets.QUndoStack):
    def __init__(self):
        super().__init__(None)
        self.main_widget = None

    def setup(self, main_widget):
        self.main_widget = main_widget


stack = _UndoStack()

class _EntityBased(QtWidgets.QUndoCommand):
    def __init__(self, entity: Union[tscat.Catalogue, tscat.Event], catalogue: tscat.Catalogue, parent=None):
        super().__init__(parent)

        self.entity = entity
        self.catalogue = catalogue

    def redo(self) -> None:
        self._redo()
        stack.main_widget.select(self.entity, self.catalogue)

    def undo(self) -> None:
        self._undo()
        stack.main_widget.select(self.entity, self.catalogue)


class NewAttribute(_EntityBased):
    def __init__(self, entity: Union[tscat.Catalogue, tscat.Event], name: str, value,
                 catalogue: tscat.Catalogue = None, parent=None):
        super().__init__(entity, catalogue, parent)

        self.setText(f'Create attribute {name} in {entity.name}')

        self.name = name
        self.value = value

    def _redo(self) -> None:
        self.entity.__setattr__(self.name, self.value)

    def _undo(self) -> None:
        self.entity.__delattr__(self.name)


class RenameAttribute(_EntityBased):
    def __init__(self, entity: Union[tscat.Catalogue, tscat.Event], old_name: str, new_name: str,
                 catalogue: tscat.Catalogue = None, parent=None):
        super().__init__(entity, catalogue, parent)

        self.setText(f'Rename attribute from {old_name} to {new_name} in {entity.name}')

        self.new_name = new_name
        self.old_name = old_name

    def _redo(self) -> None:
        value = self.entity.__dict__[self.old_name]
        self.entity.__delattr__(self.old_name)
        self.entity.__setattr__(self.new_name, value)

    def _undo(self) -> None:
        value = self.entity.__dict__[self.new_name]
        self.entity.__delattr__(self.new_name)
        self.entity.__setattr__(self.old_name, value)


class DeleteAttribute(_EntityBased):
    def __init__(self, entity: Union[tscat.Catalogue, tscat.Event], name: str,
                 catalogue: tscat.Catalogue = None, parent=None):
        super().__init__(entity, catalogue, parent)

        self.setText(f'Delete attribute {name} from {entity.name}')

        self.name = name
        self.value = self.entity.__dict__[name]

    def _redo(self) -> None:
        self.entity.__delattr__(self.name)

    def _undo(self) -> None:
        self.entity.__setattr__(self.name, self.value)


class SetAttributeValue(_EntityBased):
    def __init__(self, entity: Union[tscat.Catalogue, tscat.Event], name: str, value,
                 catalogue: tscat.Catalogue = None, parent=None):
        super().__init__(entity, catalogue, parent)

        self.setText(f'Change {name} to {value} in {entity.name}')

        self.name = name
        self.previous_value = self.entity.__dict__[name]
        self.value = value

    def _redo(self) -> None:
        self.entity.__setattr__(self.name, self.value)

    def _undo(self) -> None:
        self.entity.__setattr__(self.name, self.previous_value)
