# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

PySide6-based GUI for managing time-series catalogues (scientific/space physics data). Built on the `tscat` library for catalogue/event persistence. Part of the SciQLop ecosystem.

## Commands

```bash
uv sync                         # Install deps
uv sync --extra test            # Install with test deps
uv run pytest                   # Run tests
uv run ruff check               # Lint
```

## Architecture

The app follows a layered, signal-driven architecture:

**UI Layer** (`__init__.py` / `app.py`) — `TSCatGUI` is the main widget: left panel has a catalogue tree, right panel has an events table and entity edit form. Can be used standalone or embedded as a widget.

**State** (`state.py`) — `AppState` holds selection state (`SelectState` dataclass) and a `QUndoStack`. All mutations go through undo commands.

**Undo System** (`undo.py`) — Every data mutation is a `QUndoCommand` subclass (e.g. `NewCatalogue`, `SetAttributeValue`, `MoveEntityToTrash`). Commands call driver actions in `_redo()`/`_undo()`.

**Driver** (`tscat_driver/`) — `TscatDriver` runs a worker thread (`QThread`) that executes `Action` dataclasses against the `tscat` backend. Maintains an entity cache (UUID → Entity). Emits `action_done` signals back to the UI thread.

**Models** (`tscat_driver/catalog_model.py`, `tscat_root_model.py`) — Qt item models. `TscatRootModel` is a tree model (catalogues/folders/trash). `CatalogModel` is a table model (events in a catalogue). Both use a `Node` hierarchy (`nodes.py`).

**Key patterns:**
- `programmatic_select` flag prevents selection feedback loops
- Actions use optional `user_callback` for post-completion logic (e.g. capturing UUIDs for undo)
- Custom Qt data roles: `UUIDDataRole`, `EntityRole` in `model_base/constants.py`
- Drag-and-drop uses custom MIME types (`mime.py`)
- Import/export supports JSON and VOTable formats (`utils/import_export.py`)
