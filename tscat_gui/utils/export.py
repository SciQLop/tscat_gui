from typing import List

from PySide6 import QtCore

from ..tscat_driver.actions import CanonicalizeImportAction, ExportJSONAction


def export_to_json(filename: str, uuids: List[str]) -> bool:
    event_loop = QtCore.QEventLoop()

    result = None

    def export_done(action: CanonicalizeImportAction) -> None:
        nonlocal result
        result = action.result

        event_loop.quit()

    from ..tscat_driver.model import tscat_model
    tscat_model.do(ExportJSONAction(export_done, filename, uuids))

    event_loop.exec()

    return result
