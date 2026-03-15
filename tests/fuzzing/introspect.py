from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex

from tscat_gui import TSCatGUI
from tscat_gui.tscat_driver.driver import tscat_driver
from tscat_gui.tscat_driver.nodes import CatalogNode, FolderNode, TrashNode
from tscat_gui.model_base.constants import UUIDDataRole


def _walk_tree(gui: TSCatGUI):
    """Yield all (node, is_in_trash) pairs from the root model."""
    model = gui.catalogues_view.model()
    source = model.sourceModel() if hasattr(model, 'sourceModel') else model

    def _recurse(parent_index, in_trash=False):
        for row in range(source.rowCount(parent_index)):
            index = source.index(row, 0, parent_index)
            node = index.internalPointer()
            child_in_trash = in_trash or isinstance(node, TrashNode)
            yield node, child_in_trash
            yield from _recurse(index, child_in_trash)

    yield from _recurse(QModelIndex())


def catalogue_uuids(gui: TSCatGUI) -> list[str]:
    return [n.uuid for n, in_trash in _walk_tree(gui)
            if isinstance(n, CatalogNode) and not in_trash]


def trashed_uuids(gui: TSCatGUI) -> set[str]:
    return {n.uuid for n, in_trash in _walk_tree(gui)
            if isinstance(n, CatalogNode) and in_trash}


def folder_paths(gui: TSCatGUI) -> list[str]:
    return ["/".join(n.full_path()) for n, _ in _walk_tree(gui)
            if isinstance(n, FolderNode)]


def selected_catalogue_uuids(gui: TSCatGUI) -> list[str]:
    indexes = gui.catalogues_view.selectionModel().selectedIndexes()
    result = []
    for idx in indexes:
        uuid = idx.data(UUIDDataRole)
        if uuid is not None:
            result.append(uuid)
    return result


def selected_event_uuids(gui: TSCatGUI) -> list[str]:
    indexes = gui.events_view.selectionModel().selectedIndexes()
    seen: set[str] = set()
    result: list[str] = []
    for idx in indexes:
        uuid = idx.data(UUIDDataRole)
        if uuid is not None and uuid not in seen:
            seen.add(uuid)
            result.append(uuid)
    return result


def entity_attribute(gui: TSCatGUI, uuid: str, attr_name: str) -> Any:
    entity = tscat_driver.entity_from_uuid(uuid)
    if entity is None:
        return None
    return getattr(entity, attr_name, None)


def undo_index(gui: TSCatGUI) -> int:
    return gui.state.undo_stack().index()


def visible_event_count(gui: TSCatGUI) -> int:
    return gui.event_model.rowCount()
