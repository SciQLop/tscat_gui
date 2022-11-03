import abc

from PySide6 import QtGui

from .utils.helper import get_entity_from_uuid_safe
from .state import AppState

import os
import tscat
from copy import deepcopy

import datetime as dt
from typing import Union, Optional, Type, List
from uuid import UUID




class _EntityBased(QtGui.QUndoCommand):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)

        self.state = state
        self.select_state = state.select_state()

    def _select(self, uuid: str, type: Optional[Union[Type[tscat._Catalogue], Type[tscat._Event]]] = None):
        if type is None:
            type = self.select_state.type

        if type == tscat._Event:
            self.state.updated('passive_select', tscat._Catalogue, self.select_state.active_catalogue)
        self.state.updated('active_select', type, uuid)

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

        self.setText(f'Create attribute {name} in {self.select_state.type}')

        self.name = name
        self.value = value

    def _redo(self) -> None:
        entity = get_entity_from_uuid_safe(self.select_state.active)
        entity.__setattr__(self.name, self.value)

        self._select(self.select_state.active)
        self.state.updated('changed', type(entity), self.select_state.active)

    def _undo(self) -> None:
        entity = get_entity_from_uuid_safe(self.select_state.active)
        entity.__delattr__(self.name)

        self._select(self.select_state.active)
        self.state.updated('changed', type(entity), self.select_state.active)


class RenameAttribute(_EntityBased):
    def __init__(self, state: AppState, old_name: str, new_name: str,
                 parent=None):
        super().__init__(state, parent)

        self.setText(f'Rename attribute from {old_name} to {new_name} in {self.select_state.type}')

        self.new_name = new_name
        self.old_name = old_name

    def _redo(self) -> None:
        entity = get_entity_from_uuid_safe(self.select_state.active)
        value = entity.__dict__[self.old_name]
        entity.__delattr__(self.old_name)
        entity.__setattr__(self.new_name, value)

        self._select(self.select_state.active)
        self.state.updated('changed', type(entity), self.select_state.active)

    def _undo(self) -> None:
        entity = get_entity_from_uuid_safe(self.select_state.active)
        value = entity.__dict__[self.new_name]
        entity.__delattr__(self.new_name)
        entity.__setattr__(self.old_name, value)

        self._select(self.select_state.active)
        self.state.updated('changed', type(entity), self.select_state.active)


class DeleteAttribute(_EntityBased):
    def __init__(self, state: AppState, name: str,
                 parent=None):
        super().__init__(state, parent)

        self.setText(f'Delete attribute {name} from {self.select_state.type}')

        self.name = name
        entity = get_entity_from_uuid_safe(self.select_state.active)
        self.value = entity.__dict__[name]

    def _redo(self) -> None:
        entity = get_entity_from_uuid_safe(self.select_state.active)
        entity.__delattr__(self.name)

        self._select(self.select_state.active)
        self.state.updated('changed', type(entity), self.select_state.active)

    def _undo(self) -> None:
        entity = get_entity_from_uuid_safe(self.select_state.active)
        entity.__setattr__(self.name, self.value)

        self._select(self.select_state.active)
        self.state.updated('changed', type(entity), self.select_state.active)


class SetAttributeValue(_EntityBased):
    def __init__(self, state: AppState, name: str, value,
                 parent=None):
        super().__init__(state, parent)

        entity = get_entity_from_uuid_safe(self.select_state.active)
        self.setText(f'Change {name} to {value} in {type(entity)}')

        self.name = name
        self.previous_value = None
        self.value = value

    def _redo(self) -> None:
        entity = get_entity_from_uuid_safe(self.select_state.active)
        self.previous_value = entity.__dict__[self.name]
        entity.__setattr__(self.name, self.value)

        self._select(self.select_state.active)
        self.state.updated('changed', type(entity), self.select_state.active)

    def _undo(self) -> None:
        entity = get_entity_from_uuid_safe(self.select_state.active)
        entity.__setattr__(self.name, self.previous_value)

        self._select(self.select_state.active)
        self.state.updated('changed', type(entity), self.select_state.active)


class NewCatalogue(_EntityBased):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

        self.setText('Create new Catalogue')

        self.uuid = None

    def _redo(self):
        # the first time called it will create a new UUID
        catalogue = tscat.create_catalogue("New Catalogue", author=os.getlogin(), uuid=self.uuid)
        self.uuid = catalogue.uuid

        self.state.updated("inserted", tscat._Catalogue, catalogue.uuid)
        self._select(catalogue.uuid, tscat._Catalogue)

    def _undo(self):
        catalogue = get_entity_from_uuid_safe(self.uuid)
        catalogue.remove(permanently=True)

        self.state.updated("deleted", tscat._Catalogue, catalogue.uuid)
        self._select(self.select_state.active)


class NewEvent(_EntityBased):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

        self.setText('Create new Event')

        self.uuid = None

    def _redo(self):
        event = tscat.create_event(dt.datetime.now(), dt.datetime.now(), author=os.getlogin(), uuid=self.uuid)
        self.uuid = event.uuid

        catalogue = get_entity_from_uuid_safe(self.select_state.active_catalogue)
        tscat.add_events_to_catalogue(catalogue, event)

        self.state.updated("inserted", tscat._Event, event.uuid)
        self._select(event.uuid, tscat._Event)

    def _undo(self):
        event = get_entity_from_uuid_safe(self.uuid)
        event.remove(permanently=True)

        self.state.updated("deleted", tscat._Event, event.uuid)
        self._select(self.select_state.active)


class MoveRestoreTrashedEntity(_EntityBased):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

    def remove(self):
        entity = get_entity_from_uuid_safe(self.select_state.active)
        entity.remove()

        self.state.updated("moved", type(entity), self.select_state.active)
        self._select(self.select_state.active)

    def restore(self):
        entity = get_entity_from_uuid_safe(self.select_state.active)
        entity.restore()

        self.state.updated("moved", type(entity), self.select_state.active)
        self._select(self.select_state.active)


class MoveEntityToTrash(MoveRestoreTrashedEntity):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

        self.setText(f'Move {self.select_state.type} to Trash')

    def _redo(self):
        self.remove()

    def _undo(self):
        self.restore()


class RestoreEntityFromTrash(MoveRestoreTrashedEntity):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

        self.setText(f'Restore {self.select_state.type} from Trash')

    def _redo(self):
        self.restore()

    def _undo(self):
        self.remove()


class DeletePermanently(_EntityBased):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

        self.setText(f'Delete {self.select_state.type} permanently')

        self.entity_type = None
        self.deleted_entity_data = None
        self.entity_in_trash = None
        self.linked_uuids: List[UUID] = []

    def _redo(self):
        entity = get_entity_from_uuid_safe(self.select_state.active)
        self.entity_type = type(entity)
        self.entity_in_trash = entity.is_removed()

        if self.entity_type == tscat._Catalogue:
            self.linked_uuids = [e.uuid for e in tscat.get_events(entity)]
        else:
            self.linked_uuids = [e.uuid for e in tscat.get_catalogues(entity)]

        self.deleted_entity_data = {
            k: entity.__dict__[k] for k in list(entity.fixed_attributes().keys()) +
                                           list(entity.variable_attributes().keys())
        }

        entity.remove(permanently=True)

        self._select(None)
        self.state.updated("deleted", self.entity_type, entity.uuid)

    def _undo(self):
        entity = self.entity_type(**self.deleted_entity_data)
        if self.entity_in_trash:
            entity.remove()

        linked_entities = [get_entity_from_uuid_safe(uuid) for uuid in self.linked_uuids]
        if isinstance(entity, tscat._Catalogue):
            tscat.add_events_to_catalogue(entity, linked_entities)
        else:
            for c in linked_entities:
                assert isinstance(c, tscat._Catalogue)
                tscat.add_events_to_catalogue(c, entity)

        self.state.updated("inserted", type(entity), entity.uuid)
        self._select(entity.uuid)


class Import(_EntityBased):
    def __init__(self, state: AppState, filename: str, canonicalized_import_dict: dict, parent=None):
        super().__init__(state, parent)

        self.setText(f"Importing catalogues and events from {filename}.")

        self.import_dict = canonicalized_import_dict

    def _redo(self):
        tscat.import_canonicalized_dict(deepcopy(self.import_dict))

        # select one catalogue from the import to refresh the view
        if len(self.import_dict["catalogues"]) > 0:
            uuid = self.import_dict["catalogues"][-1]["uuid"]
            self.state.updated("inserted", tscat._Catalogue, uuid)
            self._select(uuid, tscat._Catalogue)

    def _undo(self):
        for event in self.import_dict["events"]:
            ev = get_entity_from_uuid_safe(event["uuid"])
            ev.remove(permanently=True)

        for catalogue in self.import_dict["catalogues"]:
            cat = get_entity_from_uuid_safe(catalogue["uuid"])
            cat.remove(permanently=True)

        if len(self.import_dict["catalogues"]) > 0:
            uuid = self.import_dict["catalogues"][-1]["uuid"]
            self.state.updated("deleted", tscat._Catalogue, uuid)
            self._select(self.select_state.active)
