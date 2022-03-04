from PySide2 import QtWidgets

from .utils.helper import get_entity_from_uuid_safe

import tscat


class _UndoStack(QtWidgets.QUndoStack):
    def __init__(self):
        super().__init__(None)
        self.main_widget = None

    def setup(self, main_widget):
        self.main_widget = main_widget


stack = _UndoStack()


class _EntityBased(QtWidgets.QUndoCommand):
    def __init__(self, entity_uuid: str, catalogue_uuid: str, parent=None):
        super().__init__(parent)

        self.entity_uuid = entity_uuid
        self.catalogue_uuid = catalogue_uuid

    def redo(self) -> None:
        self._redo()
        stack.main_widget.select(self.entity_uuid, self.catalogue_uuid)

    def undo(self) -> None:
        self._undo()
        stack.main_widget.select(self.entity_uuid, self.catalogue_uuid)


class NewAttribute(_EntityBased):
    def __init__(self, entity_uuid: str, name: str, value,
                 catalogue_uuid: str = None, parent=None):
        super().__init__(entity_uuid, catalogue_uuid, parent)

        entity = get_entity_from_uuid_safe(entity_uuid)

        self.setText(f'Create attribute {name} in {entity.name}')

        self.name = name
        self.value = value

    def _redo(self) -> None:
        entity = get_entity_from_uuid_safe(self.entity_uuid)
        entity.__setattr__(self.name, self.value)

    def _undo(self) -> None:
        entity = get_entity_from_uuid_safe(self.entity_uuid)
        entity.__delattr__(self.name)


class RenameAttribute(_EntityBased):
    def __init__(self, entity_uuid: str, old_name: str, new_name: str,
                 catalogue_uuid: str = None, parent=None):
        super().__init__(entity_uuid, catalogue_uuid, parent)

        entity = get_entity_from_uuid_safe(entity_uuid)
        self.setText(f'Rename attribute from {old_name} to {new_name} in {entity.name}')

        self.new_name = new_name
        self.old_name = old_name

    def _redo(self) -> None:
        entity = get_entity_from_uuid_safe(self.entity_uuid)
        value = entity.__dict__[self.old_name]
        entity.__delattr__(self.old_name)
        entity.__setattr__(self.new_name, value)

    def _undo(self) -> None:
        entity = get_entity_from_uuid_safe(self.entity_uuid)
        value = entity.__dict__[self.new_name]
        entity.__delattr__(self.new_name)
        entity.__setattr__(self.old_name, value)


class DeleteAttribute(_EntityBased):
    def __init__(self, entity_uuid: str, name: str,
                 catalogue_uuid: str = None, parent=None):
        super().__init__(entity_uuid, catalogue_uuid, parent)

        entity = get_entity_from_uuid_safe(self.entity_uuid)
        self.setText(f'Delete attribute {name} from {entity.name}')

        self.name = name
        self.value = entity.__dict__[name]

    def _redo(self) -> None:
        entity = get_entity_from_uuid_safe(self.entity_uuid)
        entity.__delattr__(self.name)

    def _undo(self) -> None:
        entity = get_entity_from_uuid_safe(self.entity_uuid)
        entity.__setattr__(self.name, self.value)


class SetAttributeValue(_EntityBased):
    def __init__(self, entity_uuid: str, name: str, value,
                 catalogue_uuid: str = None, parent=None):
        super().__init__(entity_uuid, catalogue_uuid, parent)

        entity = get_entity_from_uuid_safe(self.entity_uuid)
        self.setText(f'Change {name} to {value} in {entity.name}')

        self.name = name
        self.previous_value = entity.__dict__[name]
        self.value = value

    def _redo(self) -> None:
        entity = get_entity_from_uuid_safe(self.entity_uuid)
        entity.__setattr__(self.name, self.value)

    def _undo(self) -> None:
        entity = get_entity_from_uuid_safe(self.entity_uuid)
        entity.__setattr__(self.name, self.previous_value)


class NewCatalogue(_EntityBased):
    def __init__(self, parent=None):
        super().__init__(None, None, parent)

        self.setText('Create new Catalogue')

        self.uuid = None

    def _redo(self):
        # the first time called it will create a new UUID
        catalogue = tscat.Catalogue("New Catalogue", author="Author", uuid=self.uuid)
        self.entity_uuid = self.uuid = catalogue.uuid

    def _undo(self):
        catalogue = get_entity_from_uuid_safe(self.uuid)
        catalogue.remove(permanently=True)
        self.entity_uuid = None
