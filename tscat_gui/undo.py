from PySide2 import QtWidgets

from .utils.helper import get_entity_from_uuid_safe

import tscat


class _EntityBased(QtWidgets.QUndoCommand):
    def __init__(self, entity_uuid: str, catalogue_uuid: str, parent=None):
        super().__init__(parent)

        self.stack = None
        self.entity_uuid = entity_uuid
        self.catalogue_uuid = catalogue_uuid

    def redo(self) -> None:
        self._redo()
        self.stack.main_widget.select(self.entity_uuid, self.catalogue_uuid)

    def undo(self) -> None:
        self._undo()
        self.stack.main_widget.select(self.entity_uuid, self.catalogue_uuid)

    def set_stack(self, stack: QtWidgets.QUndoStack) -> None:
        self.stack = stack


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


class MoveRestoreTrashedEntity(_EntityBased):
    def __init__(self, entity_uuid: str, catalogue_uuid: str = None, parent=None):
        super().__init__(entity_uuid, catalogue_uuid, parent)

    def remove(self):
        entity = get_entity_from_uuid_safe(self.entity_uuid)
        entity.remove()

    def restore(self):
        entity = get_entity_from_uuid_safe(self.entity_uuid)
        entity.restore()


class MoveEntityToTrash(MoveRestoreTrashedEntity):
    def __init__(self, entity_uuid: str, catalogue_uuid: str = None, parent=None):
        super().__init__(entity_uuid, catalogue_uuid, parent)

        entity = get_entity_from_uuid_safe(self.entity_uuid)
        self.setText(f'Move {entity.name} to Trash')

    def _redo(self):
        self.remove()

    def _undo(self):
        self.restore()


class RestoreEntityFromTrash(MoveRestoreTrashedEntity):
    def __init__(self, entity_uuid: str, catalogue_uuid: str = None, parent=None):
        super().__init__(entity_uuid, catalogue_uuid, parent)

        entity = get_entity_from_uuid_safe(self.entity_uuid)
        self.setText(f'Restore {entity.name} from Trash')

    def _redo(self):
        self.restore()

    def _undo(self):
        self.remove()


class DeletePermanently(_EntityBased):
    def __init__(self, entity_uuid: str, in_trash: bool, catalogue_uuid: str = None, parent=None):
        super().__init__(entity_uuid, catalogue_uuid, parent)
        self.deleted_entity_data = None
        self.entity_type = None
        self.entity_in_trash = in_trash

    def _redo(self):
        entity = get_entity_from_uuid_safe(self.entity_uuid)

        self.entity_type = type(entity)
        self.deleted_entity_data = {
            k: entity.__dict__[k] for k in list(entity.fixed_attributes().keys()) +
                                           list(entity.variable_attributes().keys())
        }

        entity.remove(permanently=True)
        self.entity_uuid = None

    def _undo(self):
        e = self.entity_type(**self.deleted_entity_data)
        self.entity_uuid = e.uuid
        if self.entity_in_trash:
            e.remove()
