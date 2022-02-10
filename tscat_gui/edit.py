from PySide2 import QtCore, QtWidgets, QtGui

from .utils.keyword_list import EditableKeywordListWidget
from .utils.editable_label import EditableLabel

from typing import Union

import tscat

import datetime as dt
import re


class _IntDelegate(QtWidgets.QSpinBox):
    def __init__(self, value: int, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.setRange(-2 ** 31, 2 ** 31 - 1)
        self.setValue(value)


class _FloatDelegate(QtWidgets.QDoubleSpinBox):
    def __init__(self, value: float, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.setRange(float('-inf'), float('inf'))
        self.setValue(value)


class _BoolDelegate(QtWidgets.QCheckBox):
    valueChanged = QtCore.Signal(bool)

    def __init__(self, value: float, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.setChecked(value)
        self.stateChanged.connect(lambda x: self.valueChanged.emit(x))


class _UuidLabelDelegate(QtWidgets.QLabel):
    valueChanged = QtCore.Signal(str)  # never emitted

    def __init__(self, value: str, parent: QtWidgets.QWidget = None):
        super().__init__(value, parent)
        self.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)


class _StrDelegate(QtWidgets.QLineEdit):
    valueChanged = QtCore.Signal(str)

    def __init__(self, value: str, parent: QtWidgets.QWidget = None):
        super().__init__(value, parent)
        self.textChanged.connect(lambda x: self.valueChanged.emit(x))


class _DateTimeDelegate(QtWidgets.QDateTimeEdit):
    valueChanged = QtCore.Signal(dt.datetime)

    def __init__(self, value: str, parent: QtWidgets.QWidget = None):
        super().__init__(value, parent)
        self.dateTimeChanged.connect(lambda x: self.valueChanged.emit(x.toPython()))


_delegate_widget_class_factory = {
    'uuid': _UuidLabelDelegate,

    int: _IntDelegate,
    str: _StrDelegate,
    float: _FloatDelegate,
    list: EditableKeywordListWidget,
    bool: _BoolDelegate,
    dt.datetime: _DateTimeDelegate,
}

_type_name = {
    'Boolean': bool,
    'DateTime': dt.datetime,
    'Float': float,
    'Integer': int,
    'String': str,
    'Word List': list[str],
}


class AttributesGroupBox(QtWidgets.QGroupBox):
    valuesChanged = QtCore.Signal()

    def create_label(self, text: str):
        return QtWidgets.QLabel(text.title())

    def __init__(self, title: str, entity: Union[tscat.Catalogue, tscat.Event], parent: QtWidgets.QWidget = None):
        super().__init__(title, parent)

        self.entity = entity
        self.attribute_name_labels = {}

        layout = QtWidgets.QGridLayout()
        layout.setMargin(0)
        self.setLayout(layout)

    def setup(self, attributes: list[str]):

        layout = self.layout()
        if layout:
            while True:
                item = layout.takeAt(0)
                if item:
                    item.widget().deleteLater()
                else:
                    break

        self.attribute_name_labels = {}
        for row, attr in enumerate(attributes):
            label = self.create_label(attr)
            layout.addWidget(label, row, 0)

            self.attribute_name_labels[attr] = label

            value = self.entity.__dict__[attr]

            if attr in _delegate_widget_class_factory:
                cls = _delegate_widget_class_factory[attr]
            else:
                cls = _delegate_widget_class_factory.get(type(value), QtWidgets.QLabel)

            widget = cls(value)
            widget.valueChanged.connect(lambda x, attr=attr: self._value_changed(attr, x))

            layout.addWidget(widget, row, 1)

    def _value_changed(self, attr, value):
        self.entity.__setattr__(attr, value)
        self.valuesChanged.emit()


class FixedAttributesGroupBox(AttributesGroupBox):
    def __init__(self, entity: Union[tscat.Catalogue, tscat.Event], parent: QtWidgets.QWidget = None):
        super().__init__("Global", entity, parent)

        fixed_attributes = self.entity._fixed_keys[:]
        if 'predicate' in fixed_attributes:
            fixed_attributes.remove('predicate')

        self.setup(fixed_attributes)


_valid_attribute_name_re = re.compile(r'^[A-Za-z][A-Za-z_0-9]*$')


class _AttributeNameValidator(QtGui.QValidator):
    def __init__(self, invalid_words: list[str], parent=None):
        super().__init__(parent)
        self.invalid_words = invalid_words

    def validate(self, word: str, pos: int) -> QtGui.QValidator.State:
        if len(word) == 0:
            return QtGui.QValidator.Intermediate

        if word in self.invalid_words:
            return QtGui.QValidator.Intermediate

        if not _valid_attribute_name_re.match(word):
            return QtGui.QValidator.Intermediate

        return QtGui.QValidator.Acceptable


class CustomAttributesGroupBox(AttributesGroupBox):

    def create_label(self, text: str):
        attrs = list(self.entity.variable_attributes_as_dict().keys())
        attrs.remove(text)

        name = EditableLabel(text, _AttributeNameValidator(list(attrs)))
        name.editing_finished.connect(lambda x, _text=text: self._attribute_name_changed(_text, x))
        name.text_changed.connect(lambda x, _text=text: self._attribute_name_is_changing(_text, x))

        return name

    def __init__(self, entity: Union[tscat.Catalogue, tscat.Event], parent: QtWidgets.QWidget = None):
        super().__init__("Custom", entity, parent)

        self.setup()

    def setup(self):
        attributes = sorted(self.entity.variable_attributes_as_dict().keys())

        super().setup(attributes)

        layout = self.layout()

        for row, attr in enumerate(attributes):
            but = QtWidgets.QToolButton()
            but.setText('✖')
            but.clicked.connect(lambda attr=attr, x=False: self._delete(attr))
            layout.addWidget(but, row, 2)

        # self.regex_validator = QtGui.QRegularExpressionValidator(_tag_validation_regex)

        new_section_layout = QtWidgets.QHBoxLayout()
        new_section_layout.setMargin(0)

        self.type_combobox = QtWidgets.QComboBox()
        self.type_combobox.addItems(list(_type_name.keys()))
        new_section_layout.addWidget(self.type_combobox)

        button = QtWidgets.QToolButton()
        button.setText('➕')
        button.clicked.connect(self._new)
        new_section_layout.addWidget(button)

        new_section_layout.addStretch()

        widget = QtWidgets.QWidget()
        widget.setLayout(new_section_layout)

        row = layout.rowCount()
        layout.addWidget(QtWidgets.QLabel('New'), row, 0)
        layout.addWidget(widget, row, 1)

    def _delete(self, attr):
        self.entity.__delattr__(attr)
        self.setup()

    def _new(self):
        name = 'attribute{}'

        i = 1
        while name.format(i) in self.entity.__dict__.keys():
            i += 1

        name = name.format(i)

        self.entity.__setattr__(name.format(i),
                                _type_name[self.type_combobox.itemText(self.type_combobox.currentIndex())]())

        self.setup()

    def _attribute_name_is_changing(self, previous: str, text: str):
        # highlight the existing attribute which is using the same text as name
        for label in self.attribute_name_labels.values():
            label.setStyleSheet('background-color: none')

        label = self.attribute_name_labels.get(text)
        if label and previous != text:
            self.attribute_name_labels[text].setStyleSheet('color: red')

    def _attribute_name_changed(self, previous: str, text: str):
        value = self.entity.__dict__[previous]
        self.entity.__delattr__(previous)
        self.entity.__setattr__(text, value)

        self.setup()


class CatalogueEditWidget(QtWidgets.QScrollArea):
    valuesChanged = QtCore.Signal(tscat.Catalogue)

    def __init__(self, catalogue: tscat.Catalogue, parent=None):
        super().__init__(parent)

        self.catalogue = catalogue

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        attributes = FixedAttributesGroupBox(self.catalogue)
        attributes.valuesChanged.connect(lambda: self.valuesChanged.emit(self.catalogue))
        layout.addWidget(attributes)

        attributes = CustomAttributesGroupBox(self.catalogue)
        attributes.valuesChanged.connect(lambda: self.valuesChanged.emit(self.catalogue))
        layout.addWidget(attributes)

        layout.addStretch()

        widget = QtWidgets.QWidget()
        widget.setLayout(layout)

        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.setWidgetResizable(True)
        self.setWidget(widget)
