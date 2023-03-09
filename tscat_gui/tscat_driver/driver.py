from typing import Protocol

import tscat
from PySide6.QtCore import QObject, QThread, Slot, Signal, Qt
from tscat import get_catalogues, get_events, _Catalogue
from tscat.filtering import UUID


class QObjectMethod(Protocol):
    __name__: str
    __self__: QObject

    def __call__(self, *args, **kwargs):
        ...


class _TscatDriverWorker(QThread):
    got_catalog = Signal(_Catalogue, list, QObjectMethod)
    got_catalogs = Signal(list, QObjectMethod)

    def __init__(self, parent: QObject or None = None):
        super().__init__(parent=parent)
        self.moveToThread(self)
        self.start()

    def run(self):
        while not self.isInterruptionRequested():
            self.exec()

    @Slot()
    def get_catalog(self, uid: str, callback: QObjectMethod):
        catalog = get_catalogues(UUID(uid))[0]
        events = get_events(catalog)
        self.got_catalog.emit(catalog, events, callback)

    @Slot()
    def get_catalogs(self, removed_items: bool, callback: QObjectMethod):
        catalogs = tscat.get_catalogues(removed_items=removed_items)
        print(catalogs)
        self.got_catalogs.emit(catalogs, callback)


class TscatDriver(QObject):
    _get_catalog = Signal(str, QObjectMethod)
    _get_catalogs = Signal(bool, QObjectMethod)

    def __init__(self, parent: QObject or None = None):
        super().__init__(parent=parent)
        self._worker = _TscatDriverWorker()

        self._get_catalog.connect(self._worker.get_catalog, Qt.QueuedConnection)
        self._worker.got_catalog.connect(self._got_catalog, Qt.QueuedConnection)

        self._get_catalogs.connect(self._worker.get_catalogs, Qt.QueuedConnection)
        self._worker.got_catalogs.connect(self._got_catalogs, Qt.QueuedConnection)

    @Slot()
    def _got_catalog(self, catalog: _Catalogue, events: list, callback: QObjectMethod):
        callback(catalog, events)

    @Slot()
    def _got_catalogs(self, catalogs: list, callback: QObjectMethod):
        callback(catalogs)

    def get_catalog(self, uid: str, callback: QObjectMethod):
        self._get_catalog.emit(uid, callback)

    def get_catalogs(self, callback: QObjectMethod):
        self._get_catalogs.emit(False, callback)

    def get_trash(self, callback: QObjectMethod):
        self._get_catalogs.emit(True, callback)


tscat_driver = TscatDriver()
