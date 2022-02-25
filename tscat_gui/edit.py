from PySide2 import QtCore, QtWidgets, QtGui

from .utils.keyword_list import EditableKeywordListWidget
from .utils.editable_label import EditableLabel

from .undo import stack, NewAttribute, RenameAttribute, DeleteAttribute, SetAttributeValue

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
    editingFinished = QtCore.Signal()

    def __init__(self, value: float, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.setChecked(value)
        self.stateChanged.connect(lambda: self.editingFinished.emit())

    def value(self) -> bool:
        return self.isChecked()


class _UuidLabelDelegate(QtWidgets.QLabel):
    editingFinished = QtCore.Signal()  # never emitted

    def __init__(self, value: str, parent: QtWidgets.QWidget = None):
        super().__init__(value, parent)
        self.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)


class _StrDelegate(QtWidgets.QLineEdit):
    def __init__(self, value: str, parent: QtWidgets.QWidget = None):
        super().__init__(value, parent)

    def value(self) -> str:
        return self.text()


class _DateTimeDelegate(QtWidgets.QDateTimeEdit):
    def __init__(self, value: str, parent: QtWidgets.QWidget = None):
        super().__init__(value, parent)

    def value(self) -> dt.datetime:
        return self.dateTime().toPython()


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

_type_name_initial_value = {
    'DateTime': lambda: dt.datetime.now()
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

        # clear layout, destroy all widgets
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
            widget.editingFinished.connect(lambda w=widget, a=attr: self._editing_finished(a, w.value()))

            layout.addWidget(widget, row, 1)

    def _editing_finished(self, attr, value):
        if value != self.entity.__dict__[attr]:
            print(f'{attr} {value}')
            stack.push(SetAttributeValue(self.entity, attr, value))

            self.valuesChanged.emit()


class FixedAttributesGroupBox(AttributesGroupBox):
    def __init__(self, entity: Union[tscat.Catalogue, tscat.Event], parent: QtWidgets.QWidget = None):
        super().__init__("Global", entity, parent)

        self.setup()

    def setup(self):
        fixed_attributes = self.entity._fixed_keys[:]

        if 'predicate' in fixed_attributes:
            fixed_attributes.remove('predicate')

        super().setup(fixed_attributes)


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
        attrs = list(self.entity.variable_attributes_as_dict().keys()) + self.entity._fixed_keys
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
        stack.push(DeleteAttribute(self.entity, attr))

    def _new(self):
        name = 'attribute{}'

        i = 1
        while name.format(i) in self.entity.__dict__.keys():
            i += 1

        name = name.format(i)

        type_name = self.type_combobox.itemText(self.type_combobox.currentIndex())
        default = _type_name_initial_value.get(type_name, _type_name[type_name])()

        stack.push(NewAttribute(self.entity, name, default))

    def _attribute_name_changed(self, previous: str, text: str):
        stack.push(RenameAttribute(self.entity, previous, text))

    def _attribute_name_is_changing(self, previous: str, text: str):
        # highlight the existing attribute which is using the same text as name
        for label in self.attribute_name_labels.values():
            label.setStyleSheet('background-color: none')

        label = self.attribute_name_labels.get(text)
        if label and previous != text:
            self.attribute_name_labels[text].setStyleSheet('color: red')


class CatalogueEditWidget(QtWidgets.QScrollArea):
    valuesChanged = QtCore.Signal(tscat.Catalogue)

    def __init__(self, catalogue: tscat.Catalogue, parent=None):
        super().__init__(parent)

        self.catalogue = catalogue

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        self.fixed_attributes = FixedAttributesGroupBox(self.catalogue)
        self.fixed_attributes.valuesChanged.connect(lambda: self.valuesChanged.emit(self.catalogue))
        layout.addWidget(self.fixed_attributes)

        self.attributes = CustomAttributesGroupBox(self.catalogue)
        self.attributes.valuesChanged.connect(lambda: self.valuesChanged.emit(self.catalogue))
        layout.addWidget(self.attributes)

        layout.addStretch()

        widget = QtWidgets.QWidget()
        widget.setLayout(layout)

        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.setWidgetResizable(True)
        self.setWidget(widget)

    def setup(self):
        self.attributes.setup()
        self.fixed_attributes.setup()
