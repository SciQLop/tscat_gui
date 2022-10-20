from PySide6 import QtGui, QtWidgets, QtCore

import re
from typing import Union, cast
import datetime as dt

import tscat


# this function should go to tscat - this is a kludge to work-around missing functions or wrong concepts
# get an entity from a UUID (catalogue or event)
# get an entity from a UUID independently whether it is removed (in trash) or not
def get_entity_from_uuid_safe(uuid: str) -> Union[tscat._Catalogue, tscat._Event]:
    catalogues = tscat.get_catalogues(tscat.filtering.UUID(uuid))
    if len(catalogues) == 1:
        return catalogues[0]
    elif len(catalogues) == 0:
        catalogues = tscat.get_catalogues(tscat.filtering.UUID(uuid), removed_items=True)
        if len(catalogues) == 1:
            return catalogues[0]
        elif len(catalogues) == 0:
            events = tscat.get_events(tscat.filtering.UUID(uuid))
            if len(events) == 1:
                return events[0]
            elif len(events) == 0:
                events = tscat.get_events(tscat.filtering.UUID(uuid), removed_items=True)
                if len(events) == 1:
                    return events[0]

    raise ValueError(f"No entity (catalogue or event) found for this UUID {uuid}")


_valid_attribute_name_re = re.compile(r'^[A-Za-z][A-Za-z_0-9]*$')


class AttributeNameValidator(QtGui.QValidator):
    def __init__(self, invalid_words: list[str] = [], parent=None):
        super().__init__(parent)
        self.invalid_words = invalid_words

    def validate(self, word: str, pos: int) -> QtGui.QValidator.State:
        if len(word) == 0:
            return QtGui.QValidator.Intermediate  # type: ignore

        if word in self.invalid_words:
            return QtGui.QValidator.Intermediate  # type: ignore

        if not _valid_attribute_name_re.match(word):
            return QtGui.QValidator.Intermediate  # type: ignore

        return QtGui.QValidator.Acceptable  # type: ignore


class IntDelegate(QtWidgets.QSpinBox):
    def __init__(self, value: Union[int, None] = None, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.setRange(-2 ** 31, 2 ** 31 - 1)
        if value is None:
            value = 0
        self.setValue(0 if value is None else value)

    def set_value(self, value: int):
        self.setValue(value)


class FloatDelegate(QtWidgets.QLineEdit):
    def __init__(self, value: Union[float, None] = None, parent: QtWidgets.QWidget = None):
        super().__init__(parent)

        validator = QtGui.QDoubleValidator(self)
        validator.setNotation(QtGui.QDoubleValidator.Notation.ScientificNotation)
        self.setValidator(validator)

        if value is None:
            value = 0
        self.setText(str(value))

    def value(self) -> float:
        return float(self.text())

    def set_value(self, value: float):
        self.setText(str(value))


class BoolDelegate(QtWidgets.QCheckBox):
    editingFinished = QtCore.Signal()

    def __init__(self, value: Union[bool, None] = None, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.setChecked(False if value is None else value)
        self.stateChanged.connect(lambda: self.editingFinished.emit())  # type: ignore

    def value(self) -> bool:
        return self.isChecked()

    def set_value(self, value: bool):
        self.setChecked(value)


class StrDelegate(QtWidgets.QLineEdit):
    def __init__(self, value: Union[str, None] = None, parent: QtWidgets.QWidget = None):
        super().__init__("" if value is None else value, parent)

    def value(self) -> str:
        return self.text()

    def set_value(self, value: str):
        self.setText(value)


class DateTimeDelegate(QtWidgets.QDateTimeEdit):
    def __init__(self, value: Union[dt.datetime, None] = None, parent: QtWidgets.QWidget = None):
        super().__init__(dt.datetime.now() if value is None else value, parent)  # type: ignore

    def value(self) -> dt.datetime:
        return cast(dt.datetime, self.dateTime().toPython())

    def set_value(self, value: dt.datetime):
        self.setDateTime(value)  # type: ignore
