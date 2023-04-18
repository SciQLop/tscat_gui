from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Union, Type, Any

from tscat import _Catalogue, _Event, get_catalogues, get_events, create_catalogue, add_events_to_catalogue, \
    create_event, remove_events_from_catalogue, save
from tscat.filtering import UUID


@dataclass
class Action(ABC):
    user_callback: Callable[[object], None] or None
    completed: bool = field(init=False)

    def __post_init__(self):
        self.completed = False

    @staticmethod
    def _entity(uuid: str) -> Union[_Catalogue or _Event]:
        entities = get_catalogues(UUID(uuid))
        if len(entities) == 0:
            entities = get_catalogues(UUID(uuid), removed_items=True)
            if len(entities) == 0:
                entities = get_events(UUID(uuid))
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
    removed_items: bool = False,
    events: list[_Event] = field(default_factory=list)

    def action(self) -> None:
        catalogue = get_catalogues(UUID(self.uuid))[0]
        self.events = get_events(catalogue, removed_items=self.removed_items)


@dataclass
class CreateEntityAction(Action):
    cls: Type[_Catalogue or _Event]
    args: dict

    entity: _Catalogue or _Event or None = None

    def action(self) -> None:
        if self.cls == _Catalogue:
            self.entity = create_catalogue(**self.args)
        elif self.cls == _Event:
            self.entity = create_event(**self.args)


@dataclass
class RemoveEntityAction(Action):
    uuid: str
    permanently: bool

    def action(self) -> None:
        entity = self._entity(self.uuid)
        entity.remove(permanently=self.permanently)


@dataclass
class AddEventsToCatalogueAction(Action):
    uuids: list[str]
    catalogue_uuid: str

    def action(self) -> None:
        catalogue = self._entity(self.catalogue_uuid)
        # clean uuids of already existing events (assigned, not filtered)
        existing_events_uuids = set(event.uuid for event in get_events(catalogue, assigned_only=True))
        self.uuids = list(set(self.uuids) - existing_events_uuids)
        add_events_to_catalogue(catalogue, list(map(self._entity, self.uuids)))


@dataclass
class RemoveEventsFromCatalogueAction(Action):
    uuids: list[str]
    catalogue_uuid: str

    def action(self) -> None:
        catalogue = self._entity(self.catalogue_uuid)
        remove_events_from_catalogue(catalogue, list(map(self._entity, self.uuids)))


@dataclass
class RemoveEventsFromCatalogueAction(Action):
    uuids: list[str]
    catalogue_uuid: str

    def action(self) -> None:
        catalogue = self._entity(self.catalogue_uuid)
        remove_events_from_catalogue(catalogue, list(map(self._entity, self.uuids)))


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
