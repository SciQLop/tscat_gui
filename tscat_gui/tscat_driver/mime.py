import pickle
from typing import  List

from PySide6.QtCore import  QMimeData

from enum import Enum

class MimeType(Enum):
    CATALOGUE_UUID_LIST = 'application/x-tscat-catalogue-uuid-list'
    EVENT_UUID_LIST = 'application/x-tscat-event-uuid-list'

def is_catalogue_uuid_list(data: QMimeData) -> bool:
    """Check if the QMimeData contains a catalogue UUID list."""
    return data.hasFormat(MimeType.CATALOGUE_UUID_LIST.value)

def is_event_uuid_list(data: QMimeData) -> bool:
    """Check if the QMimeData contains an event UUID list."""
    return data.hasFormat(MimeType.EVENT_UUID_LIST.value)

def catalogue_uuid_list(data: QMimeData) -> List[str]:
    """Extract a list of catalogue UUIDs from the QMimeData."""
    return pickle.loads(data.data(MimeType.CATALOGUE_UUID_LIST.value))  # type: ignore

def event_uuid_list(data: QMimeData) -> List[str]:
    """Extract a list of event UUIDs from the QMimeData."""
    return pickle.loads(data.data(MimeType.EVENT_UUID_LIST.value))  # type: ignore
