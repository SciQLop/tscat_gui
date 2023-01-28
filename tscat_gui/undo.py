import abc
from dataclasses import dataclass
from copy import deepcopy
import datetime as dt
import os
from uuid import UUID
from typing import Union, Optional, Type, List, Sequence, Dict

from PySide6 import QtGui

import tscat
from .utils.helper import get_entity_from_uuid_safe
from .state import AppState


class _EntityBased(QtGui.QUndoCommand):
    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)

        self.state = state
        self._select_state = state.select_state()

    def _selected_entities(self) -> Sequence[str]:
        assert self._select_state.selected
        return self._select_state.selected

    def _mapped_selected_entities(self) -> List[Union[tscat._Catalogue, tscat._Event]]:
        for entity in map(get_entity_from_uuid_safe, self._selected_entities()):
            yield entity

    def _select(self, uuids: Sequence[str],
                type: Optional[Union[Type[tscat._Catalogue], Type[tscat._Event]]] = None):
        if type is None:
            type = self._select_state.type

        if type == tscat._Event:
            self.state.updated('passive_select', tscat._Catalogue, self._select_state.selected_catalogues)
        self.state.updated('active_select', type, uuids)

    def redo(self) -> None:
        self._redo()

    def undo(self) -> None:
        self._undo()

    @abc.abstractmethod
    def _redo(self) -> None:
        pass

    @abc.abstractmethod
    def _undo(self) -> None:
        pass


class NewAttribute(_EntityBased):
    def __init__(self, state: AppState, name: str, value, parent=None):
        super().__init__(state, parent)

        self.setText(f'Create attribute {name} in {self._select_state.type}')

        self.name = name
        self.value = value

    def _redo(self) -> None:
        for entity in self._mapped_selected_entities():
            entity.__setattr__(self.name, self.value)

        self._select(self._selected_entities())
        self.state.updated('changed', type(entity), self._selected_entities())

    def _undo(self) -> None:
        for entity in self._mapped_selected_entities():
            entity.__delattr__(self.name)

        self._select(self._selected_entities())
        self.state.updated('changed', type(entity), self._selected_entities())


class RenameAttribute(_EntityBased):
    def __init__(self, state: AppState, old_name: str, new_name: str,
                 parent=None):
        super().__init__(state, parent)

        self.setText(f'Rename attribute from {old_name} to {new_name} in {self._select_state.type}')

        self.new_name = new_name
        self.old_name = old_name

    def _redo(self) -> None:
        for entity in self._mapped_selected_entities():
            value = entity.__dict__[self.old_name]
            entity.__delattr__(self.old_name)
            entity.__setattr__(self.new_name, value)

        self._select(self._selected_entities())
        self.state.updated('changed', type(entity), self._selected_entities())

    def _undo(self) -> None:
        for entity in self._mapped_selected_entities():
            value = entity.__dict__[self.new_name]
            entity.__delattr__(self.new_name)
            entity.__setattr__(self.old_name, value)

        self._select(self._selected_entities())
        self.state.updated('changed', type(entity), self._selected_entities())


class DeleteAttribute(_EntityBased):
    def __init__(self, state: AppState, name: str,
                 parent=None):
        super().__init__(state, parent)

        self.setText(f'Delete attribute {name} from {self._select_state.type}')

        self.name = name
        self.values = [entity.__dict__[name] for entity in self._mapped_selected_entities()]

    def _redo(self) -> None:
        for entity in self._mapped_selected_entities():
            entity.__delattr__(self.name)

        self._select(self._selected_entities())
        entity.is_removed()
        self.state.updated('changed', type(entity), self._selected_entities())

    def _undo(self) -> None:
        for entity, value in zip(self._mapped_selected_entities(), self.values):
            entity.__setattr__(self.name, value)

        self._select(self._selected_entities())
        self.state.updated('changed', type(entity), self._selected_entities())


class SetAttributeValue(_EntityBased):
    def __init__(self, state: AppState, name: str, value,
                 parent=None):
        super().__init__(state, parent)

        self.setText(f'Change {name} to {value} in {self._select_state.type}')

        self.name = name
        self.previous_values = [entity.__dict__[name] for entity in self._mapped_selected_entities()]
        self.new_value = value

    def _redo(self) -> None:
        for entity in self._mapped_selected_entities():
            entity.__setattr__(self.name, self.new_value)

        self._select(self._selected_entities())
        self.state.updated('changed', type(entity), self._selected_entities())

    def _undo(self) -> None:
        for entity, value in zip(self._mapped_selected_entities(), self.previous_values):
            entity.__setattr__(self.name, value)

        self._select(self._selected_entities())
        self.state.updated('changed', type(entity), self._selected_entities())


class NewCatalogue(_EntityBased):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

        self.setText('Create new Catalogue')

        self.uuid = None

    def _redo(self):
        # the first time called it will create a new UUID
        catalogue = tscat.create_catalogue("New Catalogue", author=os.getlogin(), uuid=self.uuid)
        self.uuid = catalogue.uuid

        self.state.updated("inserted", tscat._Catalogue, [catalogue.uuid])
        self._select([catalogue.uuid], tscat._Catalogue)

    def _undo(self):
        catalogue = get_entity_from_uuid_safe(self.uuid)
        catalogue.remove(permanently=True)

        self.state.updated("deleted", tscat._Catalogue, [catalogue.uuid])
        self._select(self._selected_entities())


class NewEvent(_EntityBased):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

        self.setText('Create new Event')

        self.uuid = None

    def _redo(self):
        event = tscat.create_event(dt.datetime.now(), dt.datetime.now(), author=os.getlogin(), uuid=self.uuid)
        self.uuid = event.uuid

        assert len(self._select_state.selected_catalogues) == 1

        catalogue = get_entity_from_uuid_safe(self._select_state.active_catalogues[0])
        tscat.add_events_to_catalogue(catalogue, event)

        self.state.updated("inserted", tscat._Event, event.uuid)
        self._select([event.uuid], tscat._Event)

    def _undo(self):
        event = get_entity_from_uuid_safe(self.uuid)
        event.remove(permanently=True)

        self.state.updated("deleted", tscat._Event, [event.uuid])
        self._select(self._selected_entities())


class MoveRestoreTrashedEntity(_EntityBased):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

    def remove(self):
        for entity in self._mapped_selected_entities():
            entity.remove()

        self.state.updated("moved", type(entity), self._selected_entities())
        self._select(self._selected_entities())

    def restore(self):
        for entity in self._mapped_selected_entities():
            entity.restore()

        self.state.updated("moved", type(entity), self._selected_entities())
        self._select(self._selected_entities())


class MoveEntityToTrash(MoveRestoreTrashedEntity):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

        self.setText(f'Move {self._select_state.type} to Trash')

    def _redo(self):
        self.remove()

    def _undo(self):
        self.restore()


class RestoreEntityFromTrash(MoveRestoreTrashedEntity):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

        self.setText(f'Restore {self._select_state.type} from Trash')

    def _redo(self):
        self.restore()

    def _undo(self):
        self.remove()

@dataclass
class _DeletedEntity:
    type: Union[Type[tscat._Catalogue], Type[tscat._Event]]
    in_trash: bool
    data: Dict
    linked_uuids: List[str]

class DeletePermanently(_EntityBased):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

        self.setText(f'Delete {self._select_state.type} permanently')

        self.deleted_entities: List[_DeletedEntity] = []

    def _redo(self):
        for entity in self._mapped_selected_entities():
            if type(entity) == tscat._Catalogue:
                linked_uuids = [e.uuid for e in tscat.get_events(entity, assigned_only=True)]
            else:
                linked_uuids = [e.uuid for e in tscat.get_catalogues(entity)]

            deleted_entity = _DeletedEntity(
                type(entity),
                entity.is_removed(),
                entity.dump(),
                linked_uuids)
            self.deleted_entities.append(deleted_entity)

            entity.remove(permanently=True)

        self._select([])
        self.state.updated("deleted", type(entity), self._selected_entities())

    def _undo(self):
        restored_uuids = []
        for e in self.deleted_entities:
            if e.type == tscat._Catalogue:
                entity = tscat.create_catalogue(**e.data)
            else:
                entity = tscat.create_event(**e.data)

            if e.in_trash:
                entity.remove()

            linked_entities = [get_entity_from_uuid_safe(uuid) for uuid in e.linked_uuids]
            if isinstance(entity, tscat._Catalogue):
                tscat.add_events_to_catalogue(entity, linked_entities)
            else:
                for c in linked_entities:
                    assert isinstance(c, tscat._Catalogue)
                    tscat.add_events_to_catalogue(c, entity)

            restored_uuids += [entity.uuid]

        self.state.updated("inserted", type(entity), restored_uuids)
        self._select(restored_uuids)


class Import(_EntityBased):
    def __init__(self, state: AppState, filename: str, canonicalized_import_dict: dict, parent=None):
        super().__init__(state, parent)

        self.setText(f"Importing catalogues and events from {filename}.")

        self.import_dict = canonicalized_import_dict

    def _redo(self):
        tscat.import_canonicalized_dict(deepcopy(self.import_dict))

        # select one catalogue from the import to refresh the view
        uuids = [c['uuid'] for c in self.import_dict["catalogues"]]
        self.state.updated("inserted", tscat._Catalogue, uuids)
        self._select(uuids, tscat._Catalogue)

    def _undo(self):
        for event in self.import_dict["events"]:
            ev = get_entity_from_uuid_safe(event["uuid"])
            ev.remove(permanently=True)

        for catalogue in self.import_dict["catalogues"]:
            cat = get_entity_from_uuid_safe(catalogue["uuid"])
            cat.remove(permanently=True)

        uuids = [c['uuid'] for c in self.import_dict["catalogues"]]
        self.state.updated("deleted", tscat._Catalogue, uuids)
        self._select(self._selected_entities())
