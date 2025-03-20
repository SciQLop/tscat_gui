import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Sequence, Type, Union

from tscat import EventQueryInformation, _Catalogue, _Event, add_events_to_catalogue, canonicalize_json_import, \
    canonicalize_votable_import, create_catalogue, create_event, export_json, export_votable, get_catalogues, \
    get_events, import_canonicalized_dict, remove_events_from_catalogue, save
from tscat.filtering import UUID


@dataclass
class Action(ABC):
    user_callback: Optional[Callable[[Any], None]]
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
    catalogues: List[_Catalogue] = field(default_factory=list)

    def action(self) -> None:
        self.catalogues = get_catalogues(removed_items=self.removed_items)


@dataclass
class GetCatalogueAction(Action):
    uuid: str
    removed_items: bool = False
    events: List[_Event] = field(default_factory=list)
    query_info: List[EventQueryInformation] = field(default_factory=list)

    def action(self) -> None:
        catalogues = get_catalogues(UUID(self.uuid))
        if len(catalogues) == 0:
            catalogues = get_catalogues(UUID(self.uuid), removed_items=True)
        self.events, self.query_info = get_events(catalogues[0], removed_items=self.removed_items)


@dataclass
class CreateEntityAction(Action):
    cls: Type[Union[_Catalogue, _Event]]
    args: dict

    entity: Union[_Catalogue, _Event] = field(init=False)

    def action(self) -> None:
        if self.cls == _Catalogue:
            self.entity = create_catalogue(**self.args)
        elif self.cls == _Event:
            self.entity = create_event(**self.args)


@dataclass
class RemoveEntitiesAction(Action):
    uuids: List[str]
    permanently: bool

    def action(self) -> None:
        for entity in map(self._entity, self.uuids):
            entity.remove(permanently=self.permanently)


@dataclass
class AddEventsToCatalogueAction(Action):
    uuids: List[str]
    catalogue_uuid: str

    def action(self) -> None:
        catalogue = self._entity(self.catalogue_uuid)
        assert isinstance(catalogue, _Catalogue)

        # clean uuids of already existing events (assigned, not filtered)
        existing_events_uuids = set(event.uuid for event in get_events(catalogue, assigned_only=True)[0])
        self.uuids = list(set(self.uuids) - existing_events_uuids)
        add_events_to_catalogue(catalogue, list(map(self._event, self.uuids)))


@dataclass
class RemoveEventsFromCatalogueAction(Action):
    uuids: List[str]
    catalogue_uuid: str

    def action(self) -> None:
        catalogue = self._entity(self.catalogue_uuid)
        assert isinstance(catalogue, _Catalogue)
        remove_events_from_catalogue(catalogue, list(map(self._event, self.uuids)))


class EntityChangeAction(Action):
    pass


@dataclass
class SetAttributeAction(EntityChangeAction):
    uuids: List[str]
    name: str
    values: List[Any]

    entities: List = field(default_factory=list)

    def action(self) -> None:
        for uuid, value in zip(self.uuids, self.values):
            entity = self._entity(uuid)
            entity.__setattr__(self.name, value)
            self.entities += [entity]


@dataclass
class DeleteAttributeAction(EntityChangeAction):
    uuids: List[str]
    name: str

    entities: List = field(default_factory=list)

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
    uuids: List[str]

    entities: List = field(default_factory=list)

    def action(self) -> None:
        for entity in map(self._entity, self.uuids):
            entity.remove()
            self.entities += [entity]


@dataclass
class RestoreFromTrashAction(Action):
    uuids: List[str]

    entities: List = field(default_factory=list)

    def action(self) -> None:
        for entity in map(self._entity, self.uuids):
            entity.restore()
            self.entities += [entity]


@dataclass
class CanonicalizeImportAction(Action):
    filename: str
    importer: Callable[[str], object] = lambda x: {}

    import_dict: Any = None
    result: Optional[Exception] = None

    def action(self) -> None:
        try:
            self.import_dict = self.importer(self.filename)
        except Exception as e:
            self.result = e


def CanonicalizeJSONImportAction(*args, **kwargs) -> CanonicalizeImportAction:
    return CanonicalizeImportAction(*args, **kwargs,
                                    importer=lambda filename: canonicalize_json_import(open(filename).read()))


def CanonicalizeVOTableImportAction(*args, **kwargs) -> CanonicalizeImportAction:
    from astropy.io.votable import parse
    return CanonicalizeImportAction(*args, **kwargs,
                                    importer=lambda fname: canonicalize_votable_import(
                                        parse(fname),
                                        table_name=os.path.basename(fname).split('.')[0]))


@dataclass
class ImportCanonicalizedDictAction(Action):
    import_dict: Any

    catalogues: List = field(default_factory=list)

    def action(self) -> None:
        self.catalogues = import_canonicalized_dict(self.import_dict)


@dataclass
class ExportAction(Action):
    filename: str
    catalogue_uuids: List[str]
    exporter: Callable[[str, List[_Catalogue]], Optional[Exception]]

    result: Optional[Exception] = None

    def action(self) -> None:
        try:
            catalogues: List[_Catalogue] = list(map(self._entity, self.catalogue_uuids))  # type: ignore
            self.result = self.exporter(self.filename, catalogues)
        except Exception as e:
            self.result = e


def _export_to_json(filename: str, catalogues: List[_Catalogue]) -> Optional[Exception]:
    try:
        with open(filename, 'w+') as f:
            f.write(export_json(catalogues))
            return None
    except Exception as e:
        return e


def ExportJSONAction(*args, **kwargs):
    return ExportAction(*args, **kwargs, exporter=_export_to_json)


def _export_to_votable(filename: str, catalogues: List[_Catalogue]) -> Optional[Exception]:
    try:
        with open(filename, 'w+') as f:
            export_votable(catalogues).to_xml(f)
            return None
    except Exception as e:
        return e


def ExportVotableAction(*args, **kwargs):
    return ExportAction(*args, **kwargs, exporter=_export_to_votable)


@dataclass
class _DeletedEntity:
    type: Union[Type[_Catalogue], Type[_Event]]
    in_trash: bool
    data: dict
    linked_uuids: List[str]
    restored_entity: Optional[Union[_Catalogue, _Event]] = None


@dataclass
class DeletePermanentlyAction(Action):
    uuids: List[str]

    deleted_entities: List[_DeletedEntity] = field(default_factory=list)

    def action(self) -> None:
        for entity in map(self._entity, self.uuids):
            if isinstance(entity, _Catalogue):
                linked_uuids = [e.uuid for e in get_events(entity, assigned_only=True)[0]]
            elif isinstance(entity, _Event):
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
            entity: Union[_Catalogue, _Event]
            if e.type == _Catalogue:
                entity = create_catalogue(**e.data)
            else:
                entity = create_event(**e.data)

            e.restored_entity = entity

            if e.in_trash:
                entity.remove()

            if e.type == _Catalogue:
                linked_entities = list(map(self._event, e.linked_uuids))
            else:
                linked_entities = list(map(self._entity, e.linked_uuids))

            if isinstance(entity, _Catalogue):
                assert all(lambda x=x: isinstance(x, _Event) for x in linked_entities)
                add_events_to_catalogue(entity, linked_entities)  # type: ignore
            elif isinstance(entity, _Event):
                for c in linked_entities:
                    assert isinstance(c, _Catalogue)
                    add_events_to_catalogue(c, entity)
