from PySide6 import QtCore, QtWidgets, QtGui

from .utils.keyword_list import EditableKeywordListWidget
from .utils.editable_label import EditableLabel
from .utils.helper import get_entity_from_uuid_safe, AttributeNameValidator, IntDelegate, FloatDelegate, \
    DateTimeDelegate, StrDelegate, BoolDelegate

from .undo import NewAttribute, RenameAttribute, DeleteAttribute, SetAttributeValue
from .state import AppState

from .predicate import SimplePredicateEditDialog

from typing import Union

import tscat

import datetime as dt


class _UuidLabelDelegate(QtWidgets.QLabel):
    editingFinished = QtCore.Signal()  # never emitted

    def __init__(self, value: str, parent: QtWidgets.QWidget = None):
        super().__init__(value, parent)
        self.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)


class _PredicateDelegate(QtWidgets.QWidget):
    editingFinished = QtCore.Signal()

    def __init__(self, value: Union[tscat.Predicate, None], parent: QtWidgets.QWidget = None):
        super().__init__(parent)

        self.predicate = value

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        value = str(value)
        if len(value) > 50:
            value = value[:50] + '...'
        self.label = QtWidgets.QLabel(value)
        layout.addWidget(self.label)

        button = QtWidgets.QPushButton("Edit")
        button.clicked.connect(self.edit_predicate)
        layout.addWidget(button)

        button = QtWidgets.QPushButton("Clear")
        button.clicked.connect(self.clear_predicate)
        layout.addWidget(button)
        layout.addStretch()

        self.setLayout(layout)

    def edit_predicate(self):
        dialog = SimplePredicateEditDialog(self.predicate, self)
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            self.predicate = dialog.predicate
            self.editingFinished.emit()

    def clear_predicate(self):
        self.predicate = None
        self.editingFinished.emit()

    def value(self) -> Union[tscat.Predicate, None]:
        return self.predicate


_delegate_widget_class_factory = {
    'uuid': _UuidLabelDelegate,
    'predicate': _PredicateDelegate,

    int: IntDelegate,
    str: StrDelegate,
    float: FloatDelegate,
    list: EditableKeywordListWidget,
    bool: BoolDelegate,
    dt.datetime: DateTimeDelegate,
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

    def __init__(self, title: str, uuid: str, state: AppState, parent: QtWidgets.QWidget = None):
        super().__init__(title, parent)

        self.uuid = uuid
        self.entity = None
        self.attribute_name_labels = {}
        self.state = state

        layout = QtWidgets.QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def setup(self, attributes: list[str], entity: Union[tscat.Catalogue, tscat.Event]):
        self.entity = entity

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
            self.state.push_undo_command(SetAttributeValue, attr, value)
            self.valuesChanged.emit()
            self.entity = get_entity_from_uuid_safe(self.uuid)


class FixedAttributesGroupBox(AttributesGroupBox):
    def __init__(self, uuid: str, state: AppState, parent: QtWidgets.QWidget = None):
        super().__init__("Global", uuid, state, parent)

        self.setup()

    def setup(self):
        entity = get_entity_from_uuid_safe(self.uuid)
        fixed_attributes = list(entity.fixed_attributes().keys())

        super().setup(fixed_attributes, entity)


class CustomAttributesGroupBox(AttributesGroupBox):

    def create_label(self, text: str):
        attrs = list(self.entity.variable_attributes().keys()) + \
                list(self.entity.fixed_attributes().keys())
        attrs.remove(text)

        name = EditableLabel(text, AttributeNameValidator(list(attrs)))
        name.editing_finished.connect(lambda x, _text=text: self._attribute_name_changed(_text, x))
        name.text_changed.connect(lambda x, _text=text: self._attribute_name_is_changing(_text, x))

        return name

    def __init__(self, uuid: str, state: AppState, parent: QtWidgets.QWidget = None):
        super().__init__("Custom", uuid, state, parent)

        self.setup()

    def setup(self):
        entity = get_entity_from_uuid_safe(self.uuid)

        attributes = sorted(entity.variable_attributes().keys())

        super().setup(attributes, entity)

        layout = self.layout()

        for row, attr in enumerate(attributes):
            but = QtWidgets.QToolButton()
            but.setText('✖')
            but.clicked.connect(lambda a=attr, x=False: self._delete(a))
            layout.addWidget(but, row, 2)

        new_section_layout = QtWidgets.QHBoxLayout()
        new_section_layout.setContentsMargins(0, 0, 0, 0)

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
        self.state.push_undo_command(DeleteAttribute, attr)

    def _new(self):
        name = 'attribute{}'

        i = 1
        while name.format(i) in self.entity.__dict__.keys():
            i += 1

        name = name.format(i)

        type_name = self.type_combobox.itemText(self.type_combobox.currentIndex())
        default = _type_name_initial_value.get(type_name, _type_name[type_name])()

        self.state.push_undo_command(NewAttribute, name, default)

    def _attribute_name_changed(self, previous: str, text: str):
        self.state.push_undo_command(RenameAttribute, previous, text)

    def _attribute_name_is_changing(self, previous: str, text: str):
        # highlight the existing attribute which is using the same text as name
        for label in self.attribute_name_labels.values():
            label.setStyleSheet('background-color: none')

        label = self.attribute_name_labels.get(text)
        if label and previous != text:
            self.attribute_name_labels[text].setStyleSheet('color: red')


class _EntityEditWidget(QtWidgets.QWidget):
    def __init__(self, uuid: str, state: AppState, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        self.fixed_attributes = FixedAttributesGroupBox(uuid, state)
        layout.addWidget(self.fixed_attributes)

        self.attributes = CustomAttributesGroupBox(uuid, state)
        layout.addWidget(self.attributes)

        layout.addStretch()

        self.setLayout(layout)

    def setup(self):
        self.attributes.setup()
        self.fixed_attributes.setup()


class EntityEditView(QtWidgets.QScrollArea):

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)

        self.edit = None
        self.state = state
        self.current = None

        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.setWidgetResizable(True)

        self.state.state_changed.connect(self.state_changed)

    def state_changed(self, action: str, type, uuid: str):
        if action == 'active_select':
            if self.current != uuid:
                if self.edit:
                    self.edit.deleteLater()
                    self.edit = None

                if uuid:
                    self.edit = _EntityEditWidget(uuid, self.state)
                    self.setWidget(self.edit)
                self.current = uuid
        elif action == 'deleted' and self.current == uuid:
            if self.edit:
                self.edit.deleteLater()
                self.edit = None
            self.current = None
        elif action == 'changed' and self.current == uuid:
            self.edit.setup()
