from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppModel:
    catalogues: list[str] = field(default_factory=list)
    events: dict[str, list[str]] = field(default_factory=dict)
    folders: list[str] = field(default_factory=list)
    trashed: set[str] = field(default_factory=set)
    custom_attributes: dict[str, dict[str, Any]] = field(default_factory=dict)
    selected_catalogues: list[str] = field(default_factory=list)
    selected_events: list[str] = field(default_factory=list)
    undo_depth: int = 0
    _snapshots: list[AppModel] = field(default_factory=list)
    _redo_stack: list[AppModel] = field(default_factory=list)

    @property
    def has_catalogues(self) -> bool:
        return len(self.catalogues) > 0

    @property
    def has_events(self) -> bool:
        return any(len(evts) > 0 for evts in self.events.values())

    @property
    def has_trashed(self) -> bool:
        return len(self.trashed) > 0

    @property
    def has_undo(self) -> bool:
        return len(self._snapshots) > 0

    @property
    def has_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def active_events(self) -> list[str]:
        result = []
        for cat in self.selected_catalogues:
            for ev in self.events.get(cat, []):
                if ev not in self.trashed:
                    result.append(ev)
        return result

    def select_catalogue(self, uuids: list[str]) -> None:
        self.selected_catalogues = uuids
        self.selected_events = []

    def _state_snapshot(self) -> AppModel:
        return AppModel(
            catalogues=list(self.catalogues),
            events={k: list(v) for k, v in self.events.items()},
            folders=list(self.folders),
            trashed=set(self.trashed),
            custom_attributes=deepcopy(self.custom_attributes),
            selected_catalogues=list(self.selected_catalogues),
            selected_events=list(self.selected_events),
            undo_depth=self.undo_depth,
        )

    def _restore_from(self, snap: AppModel) -> None:
        self.catalogues = snap.catalogues
        self.events = snap.events
        self.folders = snap.folders
        self.trashed = snap.trashed
        self.custom_attributes = snap.custom_attributes
        self.selected_catalogues = snap.selected_catalogues
        self.selected_events = snap.selected_events
        self.undo_depth = snap.undo_depth

    def push_snapshot(self) -> None:
        self._snapshots.append(self._state_snapshot())
        self._redo_stack.clear()

    def pop_snapshot(self) -> None:
        if not self._snapshots:
            raise IndexError("No snapshots to pop")
        self._redo_stack.append(self._state_snapshot())
        self._restore_from(self._snapshots.pop())

    def pop_redo(self) -> None:
        if not self._redo_stack:
            raise IndexError("No redo snapshots")
        self._snapshots.append(self._state_snapshot())
        self._restore_from(self._redo_stack.pop())

    def reset(self) -> None:
        self.catalogues.clear()
        self.events.clear()
        self.folders.clear()
        self.trashed.clear()
        self.custom_attributes.clear()
        self.selected_catalogues.clear()
        self.selected_events.clear()
        self.undo_depth = 0
        self._snapshots.clear()
        self._redo_stack.clear()
