import abc
import datetime as dt
import os
from copy import deepcopy
from typing import Dict, List, Optional, Tuple, Type, Union

from PySide6 import QtGui

import tscat
from .model_base.constants import PathAttributeName
from .state import AppState
from .tscat_driver.actions import AddEventsToCatalogueAction, CreateEntityAction, DeleteAttributeAction, \
    DeletePermanentlyAction, ImportCanonicalizedDictAction, MoveToTrashAction, RemoveEntitiesAction, \
    RemoveEventsFromCatalogueAction, RestoreFromTrashAction, RestorePermanentlyDeletedAction, SetAttributeAction, \
    _DeletedEntity


class _EntityBased(QtGui.QUndoCommand):
    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)

        self.state = state
        self._select_state = state.select_state()

    def _selected_entities(self) -> List[str]:
        return self._select_state.selected

    def _mapped_selected_entities(self) -> List[Union[tscat._Catalogue, tscat._Event]]:
        from .tscat_driver.model import tscat_model
        return tscat_model.entities_from_uuids(self._selected_entities())

    def _select(self, uuids: List[str],
                type: Optional[Union[Type[tscat._Catalogue], Type[tscat._Event]]] = None):
        if type is None:
            type = self._select_state.type

        if type == tscat._Event:
            self.state.updated('passive_select', tscat._Catalogue, self._select_state.selected_catalogues)
        self.state.updated('active_select', type, uuids)
        self.state.set_catalogue_path(self._select_state.catalogue_path)

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
        from .tscat_driver.model import tscat_model
        tscat_model.do(SetAttributeAction(None, self._selected_entities(),
                                          self.name, [self.value] * len(self._selected_entities())))

        self._select(self._selected_entities())

    def _undo(self) -> None:
        from .tscat_driver.model import tscat_model
        tscat_model.do(DeleteAttributeAction(None, self._selected_entities(), self.name))

        self._select(self._selected_entities())


class RenameAttribute(_EntityBased):
    def __init__(self, state: AppState, old_name: str, new_name: str,
                 parent=None):
        super().__init__(state, parent)

        self.setText(f'Rename attribute from {old_name} to {new_name} in {self._select_state.type}')

        self.new_name = new_name
        self.old_name = old_name

    def _redo(self) -> None:
        values = [entity.__dict__[self.old_name] for entity in self._mapped_selected_entities()]
        from .tscat_driver.model import tscat_model
        tscat_model.do(DeleteAttributeAction(None, self._selected_entities(), self.old_name))
        tscat_model.do(SetAttributeAction(None, self._selected_entities(), self.new_name, values))

        self._select(self._selected_entities())

    def _undo(self) -> None:
        values = [entity.__dict__[self.new_name] for entity in self._mapped_selected_entities()]
        from .tscat_driver.model import tscat_model
        tscat_model.do(DeleteAttributeAction(None, self._selected_entities(), self.new_name))
        tscat_model.do(SetAttributeAction(None, self._selected_entities(), self.old_name, values))

        self._select(self._selected_entities())


class DeleteAttribute(_EntityBased):
    def __init__(self, state: AppState, name: str,
                 parent=None):
        super().__init__(state, parent)

        self.setText(f'Delete attribute {name} from {self._select_state.type}')

        self.name = name
        self.values = [entity.__dict__[name] for entity in self._mapped_selected_entities()]

    def _redo(self) -> None:
        from .tscat_driver.model import tscat_model
        tscat_model.do(DeleteAttributeAction(None, self._selected_entities(), self.name))
        self._select(self._selected_entities())

    def _undo(self) -> None:
        from .tscat_driver.model import tscat_model
        tscat_model.do(SetAttributeAction(None, self._selected_entities(), self.name, self.values))
        self._select(self._selected_entities())


class SetAttributeValue(_EntityBased):
    def __init__(self, state: AppState, name: str, value,
                 parent=None):
        super().__init__(state, parent)

        self.setText(f'Change {name} to {value} in {self._select_state.type}')

        self.name = name
        self.previous_values = [entity.__dict__[name] for entity in self._mapped_selected_entities()]
        self.new_value = value

    def _redo(self) -> None:
        from .tscat_driver.model import tscat_model
        tscat_model.do(SetAttributeAction(None, self._selected_entities(), self.name,
                                          [self.new_value] * len(self._selected_entities())))

        self._select(self._selected_entities())

    def _undo(self) -> None:
        from .tscat_driver.model import tscat_model
        tscat_model.do(SetAttributeAction(None, self._selected_entities(), self.name, self.previous_values))

        self._select(self._selected_entities())


class NewCatalogue(_EntityBased):
    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(state, parent)

        self.setText('Create new Catalogue')

        self.uuid: Optional[str] = None

    def _redo(self) -> None:
        def creation_callback(action: CreateEntityAction) -> None:
            print("New Catalogue created", action.entity)
            assert action.entity is not None
            self.uuid = action.entity.uuid
            assert self.uuid is not None
            self._select([self.uuid], tscat._Catalogue)

        from .tscat_driver.model import tscat_model
        tscat_model.do(CreateEntityAction(creation_callback, tscat._Catalogue,
                                          {
                                              'name': "New Catalogue",
                                              'author': os.getlogin(),
                                              'uuid': self.uuid,
                                              PathAttributeName: self.state.current_catalogue_path()
                                          }))

    def _undo(self) -> None:
        def remove_callback(_: RemoveEntitiesAction) -> None:
            self._select(self._selected_entities())

        from .tscat_driver.model import tscat_model
        assert self.uuid is not None
        tscat_model.do(RemoveEntitiesAction(remove_callback, [self.uuid], True))


class NewEvent(_EntityBased):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

        self.setText('Create new Event')

        self.uuid: Optional[str] = None

    def _redo(self):
        from .tscat_driver.model import tscat_model

        def add_to_catalogue_callback(action: AddEventsToCatalogueAction) -> None:
            assert self.uuid is not None
            self._select([self.uuid], tscat._Event)

        def creation_callback(action: CreateEntityAction) -> None:
            self.uuid = action.entity.uuid
            assert self.uuid is not None  # satisfy mypy
            tscat_model.do(AddEventsToCatalogueAction(add_to_catalogue_callback,
                                                      [self.uuid], self._select_state.selected_catalogues[0]))

        tscat_model.do(CreateEntityAction(creation_callback, tscat._Event,
                                          {
                                              'start': dt.datetime.now(),
                                              'stop': dt.datetime.now(),
                                              'author': os.getlogin(),
                                              'uuid': self.uuid
                                          }))

    def _undo(self):
        def remove_callback(_: RemoveEntitiesAction) -> None:
            self._select(self._selected_entities())

        from .tscat_driver.model import tscat_model
        tscat_model.do(RemoveEntitiesAction(remove_callback, [self.uuid], True))


class MoveRestoreTrashedEntity(_EntityBased):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

    def remove(self):
        from .tscat_driver.model import tscat_model
        tscat_model.do(MoveToTrashAction(None, self._selected_entities()))

        self._select(self._selected_entities())

    def restore(self):
        from .tscat_driver.model import tscat_model
        tscat_model.do(RestoreFromTrashAction(None, self._selected_entities()))
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


class DeletePermanently(_EntityBased):
    def __init__(self, state: AppState, parent=None):
        super().__init__(state, parent)

        # keep the action and its data to use it in case of undo
        self._deleted_entities: List[_DeletedEntity] = []

        self.setText(f'Delete {self._select_state.type} permanently')

    def _redo(self):
        def action_callback(action: DeletePermanentlyAction) -> None:
            self._deleted_entities = action.deleted_entities
            self._select([])

        from .tscat_driver.model import tscat_model
        tscat_model.do(DeletePermanentlyAction(action_callback, self._selected_entities()))

    def _undo(self):
        def action_callback(action: RestorePermanentlyDeletedAction) -> None:
            restored_uuids = [e.data['uuid'] for e in action.deleted_entities]
            self._select(restored_uuids)

        from .tscat_driver.model import tscat_model
        tscat_model.do(RestorePermanentlyDeletedAction(action_callback, self._deleted_entities))


class Import(_EntityBased):
    def __init__(self, state: AppState, filename: str, canonicalized_import_dict: dict, parent=None):
        super().__init__(state, parent)

        self.setText(f"Importing catalogues and events from {filename}.")

        self.import_dict = canonicalized_import_dict

    def _redo(self):
        from .tscat_driver.model import tscat_model
        tscat_model.do(ImportCanonicalizedDictAction(None, deepcopy(self.import_dict)))

    def _undo(self):
        from .tscat_driver.model import tscat_model

        event_uuids = [uuid for uuid in self.import_dict.events.keys()]
        tscat_model.do(RemoveEntitiesAction(None, event_uuids, True))

        catalogue_uuids = [cat["uuid"] for cat in self.import_dict.catalogues]
        tscat_model.do(RemoveEntitiesAction(None, catalogue_uuids, True))


class AddEventsToCatalogue(_EntityBased):
    def __init__(self, state: AppState,
                 catalogue_uuid: str, event_uuids: List[str],
                 parent=None):
        super().__init__(state, parent)

        self.setText(f'Add events to catalogue')
        self.catalogue_uuid = catalogue_uuid

        # when adding events to a catalogue events might already be present or indirectly selected by the predicate
        # so in the first redo-call we add all events, the driver will check whether events are already present and
        # return which ones have really been added
        self.event_uuids = event_uuids

    def _redo(self):
        def update_added_events(action: AddEventsToCatalogueAction):
            self.event_uuids = action.uuids
            self._select_state.selected_catalogues = [self.catalogue_uuid]
            self._select(self.event_uuids, type=tscat._Event)

        from .tscat_driver.model import tscat_model
        tscat_model.do(AddEventsToCatalogueAction(update_added_events, self.event_uuids, self.catalogue_uuid))

    def _undo(self):
        from .tscat_driver.model import tscat_model
        tscat_model.do(RemoveEventsFromCatalogueAction(None, self.event_uuids, self.catalogue_uuid))

        self._select([self.catalogue_uuid], type=tscat._Catalogue)


class CreateOrSetCataloguePath(_EntityBased):
    def __init__(self, state: AppState,
                 catalogues_paths: Dict[str, Tuple[List[str]]], parent=None):
        super().__init__(state, parent)

        self._select_state.selected_catalogues = list(catalogues_paths.keys())
        self.setText('Move catalogues to new paths')
        self.paths = catalogues_paths

    def _redo(self) -> None:
        def action_callback(_: SetAttributeAction) -> None:
            self._select(self._selected_entities())

        from .tscat_driver.model import tscat_model
        uuids, paths = [], []
        for u, p in self.paths.items():
            uuids.append(u)
            paths.append(p[1])
        tscat_model.do(SetAttributeAction(action_callback, uuids, PathAttributeName, paths))

    def _undo(self) -> None:
        def action_callback(_: SetAttributeAction) -> None:
            self._select(self._selected_entities())

        from .tscat_driver.model import tscat_model
        uuids, paths = [], []
        for u, p in self.paths.items():
            uuids.append(u)
            paths.append(p[0])
        tscat_model.do(SetAttributeAction(action_callback, uuids, PathAttributeName, paths))
