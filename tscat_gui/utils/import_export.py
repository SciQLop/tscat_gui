from typing import List, Optional

from PySide6 import QtCore

from tscat_gui.tscat_driver.actions import ExportJSONAction, ExportVotableAction, ExportAction, \
    CanonicalizeImportAction, \
    CanonicalizeVOTableImportAction, CanonicalizeJSONImportAction
from tscat_gui.undo import Import


def _export(filename: str, uuids: List[str], exporter) -> Optional[Exception]:
    event_loop = QtCore.QEventLoop()

    result = None

    def export_done(action: ExportAction) -> None:
        nonlocal result
        result = action.result

        event_loop.quit()

    from tscat_gui.tscat_driver.model import tscat_model
    tscat_model.do(exporter(export_done, filename, uuids))

    event_loop.exec()

    return result


def export_to_json(filename: str, uuids: List[str]) -> Optional[Exception]:
    return _export(filename, uuids, ExportJSONAction)


def export_to_votable(filename: str, uuids: List[str]) -> Optional[Exception]:
    return _export(filename, uuids, ExportVotableAction)


def _import(filename: str, importer, app_state) -> Optional[Exception]:
    event_loop = QtCore.QEventLoop()

    result = None

    def canonicalization_done(action: CanonicalizeImportAction) -> None:
        nonlocal result
        result = action.result

        if result is None:
            app_state.push_undo_command(Import, filename, action.import_dict)

        event_loop.quit()

    from tscat_gui.tscat_driver.model import tscat_model
    tscat_model.do(importer(canonicalization_done, filename))

    event_loop.exec()

    return result


def import_json(filename: str, app_state) -> Optional[Exception]:
    return _import(filename, CanonicalizeJSONImportAction, app_state)


def import_votable(filename: str, app_state) -> Optional[Exception]:
    return _import(filename, CanonicalizeVOTableImportAction, app_state)
