from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Union, Type, Any, Sequence, Optional, List

from tscat import _Catalogue, _Event, get_catalogues, get_events, create_catalogue, add_events_to_catalogue, \
    create_event, remove_events_from_catalogue, save, canonicalize_json_import, import_canonicalized_dict, export_json
from tscat.filtering import UUID


@dataclass
class Action(ABC):
    user_callback: Union[Callable[[object], None], None]
    completed: bool = field(init=False)

    def __post_init__(self):
        self.completed = False

    @staticmethod
    def _entity(uuid: str) -> Union[_Catalogue, _Event]:
        entities: Sequence[Union[_Event, _Catalogue]] = get_catalogues(UUID(uuid))
        if len(entities) == 0:
            entities = get_catalogues(UUID(uuid), removed_items=True)
            if len(entities) == 0:
                entities = get_events(UUID(uuid))
                if len(entities) == 0:
                    entities = get_events(UUID(uuid), removed_items=True)

        assert len(entities) == 1

        return entities[0]

    @staticmethod
    def _event(uuid: str) -> _Event:
        entities: Sequence[_Event] = get_events(UUID(uuid))
        if len(entities) == 0:
            entities = get_events(UUID(uuid), removed_items=True)

        assert len(entities) == 1

        return entities[0]

    @abstractmethod
    def action(self):
        ...


@dataclass
class GetCataloguesAction(Action):
    removed_items: bool = False
    catalogues: list[_Catalogue] = field(default_factory=list)

    def action(self) -> None:
        self.catalogues = get_catalogues(removed_items=self.removed_items)


@dataclass
class GetCatalogueAction(Action):
    uuid: str
    removed_items: bool = False
    events: list[_Event] = field(default_factory=list)

    def action(self) -> None:
        catalogue = get_catalogues(UUID(self.uuid))[0]
        self.events = get_events(catalogue, removed_items=self.removed_items)


@dataclass
class CreateEntityAction(Action):
    cls: Type[Union[_Catalogue, _Event]]
    args: dict

    entity: Optional[Union[_Catalogue, _Event]] = None

    def action(self) -> None:
        if self.cls == _Catalogue:
            self.entity = create_catalogue(**self.args)
        elif self.cls == _Event:
            self.entity = create_event(**self.args)


@dataclass
class RemoveEntitiesAction(Action):
    uuids: list[str]
    permanently: bool

    def action(self) -> None:
        for entity in map(self._entity, self.uuids):
            entity.remove(permanently=self.permanently)


@dataclass
class AddEventsToCatalogueAction(Action):
    uuids: list[str]
    catalogue_uuid: str

    def action(self) -> None:
        catalogue = self._entity(self.catalogue_uuid)
        assert isinstance(catalogue, _Catalogue)

        # clean uuids of already existing events (assigned, not filtered)
        existing_events_uuids = set(event.uuid for event in get_events(catalogue, assigned_only=True))
        self.uuids = list(set(self.uuids) - existing_events_uuids)
        add_events_to_catalogue(catalogue, list(map(self._event, self.uuids)))


@dataclass
class RemoveEventsFromCatalogueAction(Action):
    uuids: list[str]
    catalogue_uuid: str

    def action(self) -> None:
        catalogue = self._entity(self.catalogue_uuid)
        assert isinstance(catalogue, _Catalogue)
        remove_events_from_catalogue(catalogue, list(map(self._event, self.uuids)))


class EntityChangeAction(Action):
    pass


@dataclass
class SetAttributeAction(EntityChangeAction):
    uuids: list[str]
    name: str
    values: list[Any]

    entities: list = field(default_factory=list)

    def action(self) -> None:
        for uuid, value in zip(self.uuids, self.values):
            entity = self._entity(uuid)
            entity.__setattr__(self.name, value)
            self.entities += [entity]


@dataclass
class DeleteAttributeAction(EntityChangeAction):
    uuids: list[str]
    name: str

    entities: list = field(default_factory=list)

    def action(self) -> None:
        for entity in map(self._entity, self.uuids):
            entity.__delattr__(self.name)
            self.entities += [entity]


@dataclass
class SaveAction(Action):
    def action(self) -> None:
        save()


@dataclass
class MoveToTrashAction(Action):
    uuids: list[str]

    entities: list = field(default_factory=list)

    def action(self) -> None:
        for entity in map(self._entity, self.uuids):
            entity.remove()
            self.entities += [entity]


@dataclass
class RestoreFromTrashAction(Action):
    uuids: list[str]

    entities: list = field(default_factory=list)

    def action(self) -> None:
        for entity in map(self._entity, self.uuids):
            entity.restore()
            self.entities += [entity]


@dataclass
class CanonicalizeImportAction(Action):
    filename: str

    import_dict: Any = None
    result: Optional[Exception] = None

    def action(self) -> None:
        try:
            with open(self.filename) as f:
                data = f.read()
                self.import_dict = canonicalize_json_import(data)
        except Exception as e:
            self.result = e


@dataclass
class ImportCanonicalizedDictAction(Action):
    import_dict: Any

    catalogues: list = field(default_factory=list)

    def action(self) -> None:
        self.catalogues = import_canonicalized_dict(self.import_dict)


@dataclass
class ExportJSONAction(Action):
    filename: str
    catalogue_uuids: list[str]

    result: Optional[Exception] = None

    def action(self) -> None:
        try:
            with open(self.filename, 'w+') as f:
                catalogues = list(map(self._entity, self.catalogue_uuids))
                json = export_json(catalogues)  # type: ignore
                f.write(json)
        except Exception as e:
            self.result = e


@dataclass
class _DeletedEntity:
    type: Union[Type[_Catalogue], Type[_Event]]
    in_trash: bool
    data: dict
    linked_uuids: list[str]
    restored_entity: Optional[Union[_Catalogue, _Event]] = None


@dataclass
class DeletePermanentlyAction(Action):
    uuids: list[str]

    deleted_entities: List[_DeletedEntity] = field(default_factory=list)

    def action(self) -> None:
        for entity in map(self._entity, self.uuids):
            if type(entity) == _Catalogue:
                linked_uuids = [e.uuid for e in get_events(entity, assigned_only=True)]
            else:
                linked_uuids = [e.uuid for e in get_catalogues(entity)]

            deleted_entity = _DeletedEntity(
                type(entity),
                entity.is_removed(),
                entity.dump(),
                linked_uuids)
            self.deleted_entities.append(deleted_entity)

            entity.remove(permanently=True)


@dataclass
class RestorePermanentlyDeletedAction(Action):
    deleted_entities: List[_DeletedEntity]

    def action(self) -> None:
        for e in self.deleted_entities:
            if e.type == _Catalogue:
                entity = create_catalogue(**e.data)
            else:
                entity = create_event(**e.data)

            e.restored_entity = entity

            if e.in_trash:
                print('entity is trashed', entity)
                entity.remove()

            linked_entities = list(map(self._entity, e.linked_uuids))
            if isinstance(entity, _Catalogue):
                add_events_to_catalogue(entity, linked_entities)
            else:
                for c in linked_entities:
                    assert isinstance(c, _Catalogue)
                    add_events_to_catalogue(c, entity)
