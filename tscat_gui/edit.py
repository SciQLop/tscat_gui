import datetime as dt
from typing import Union, Dict, Optional, List, Type, cast, Any

from PySide6 import QtCore, QtWidgets

import tscat

from .utils.keyword_list import EditableKeywordListWidget
from .utils.editable_label import EditableLabel
from .utils.helper import get_entity_from_uuid_safe, AttributeNameValidator, IntDelegate, FloatDelegate, \
    DateTimeDelegate, StrDelegate, BoolDelegate

from .undo import NewAttribute, RenameAttribute, DeleteAttribute, SetAttributeValue
from .state import AppState

from .predicate import SimplePredicateEditDialog


class _UuidLabelDelegate(QtWidgets.QLabel):
    editingFinished = QtCore.Signal()  # never emitted

    def __init__(self, value: str, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(value, parent)
        self.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)  # type: ignore


class _PredicateDelegate(QtWidgets.QWidget):
    editingFinished = QtCore.Signal()

    def __init__(self, value: Optional[tscat.Predicate], parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self.predicate = value

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        value_str = str(value)
        if len(value_str) > 50:
            value_str = value_str[:50] + '...'
        self.label = QtWidgets.QLabel(value_str)
        layout.addWidget(self.label)

        button = QtWidgets.QPushButton("Edit")
        button.clicked.connect(self.edit_predicate)  # type: ignore
        layout.addWidget(button)

        button = QtWidgets.QPushButton("Clear")
        button.clicked.connect(self.clear_predicate)  # type: ignore
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


class _MultipleDifferentValues(list):
    def __init__(self, attribute: str, *args: List) -> None:
        super().__init__(*args)
        self.attribute = attribute


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


class _MultipleDifferentValuesDelegate(QtWidgets.QPushButton):
    editingFinished = QtCore.Signal()

    def __init__(self,
                 values: _MultipleDifferentValues,
                 parent: Optional[QtWidgets.QWidget] = None):
        super().__init__('<multiple-values-click-to-reset>', parent)
        assert len(values) > 0
        self.reset_value = values[0]

        self.clicked.connect(lambda x: self.editingFinished.emit())  # type: ignore

    def value(self) -> Any:
        return self.reset_value


_type_name = {
    'Boolean': bool,
    'DateTime': dt.datetime,
    'Float': float,
    'Integer': int,
    'String': str,
    'Word List': List[str],
}

_type_name_initial_value = {
    'DateTime': lambda: dt.datetime.now()
}


class AttributesGroupBox(QtWidgets.QGroupBox):
    valuesChanged = QtCore.Signal()

    def create_label(self, text: str) -> QtWidgets.QLabel:  # type: ignore
        return QtWidgets.QLabel(text.title())

    def __init__(self, title: str,
                 uuids: List[str],
                 state: AppState,
                 parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title, parent)

        self.uuids = uuids
        self.attribute_name_labels: Dict[str, QtWidgets.QLabel] = {}
        self.state = state
        self.values: Dict = {}

        self._layout = QtWidgets.QGridLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)

    def setup(self, values: Dict):
        # clear layout, destroy all widgets
        while True:
            item = self._layout.takeAt(0)
            if item:
                item.widget().deleteLater()
            else:
                break

        self.values = values
        self.attribute_name_labels = {}
        for row, attr in enumerate(values.keys()):
            label = self.create_label(attr)
            self._layout.addWidget(label, row, 0)

            self.attribute_name_labels[attr] = label

            value = values[attr]

            cls: Type[Union[_MultipleDifferentValuesDelegate, _UuidLabelDelegate, _PredicateDelegate,
                       IntDelegate, StrDelegate, FloatDelegate,
                       EditableKeywordListWidget, BoolDelegate, DateTimeDelegate]]
            if isinstance(value, _MultipleDifferentValues):
                cls = _MultipleDifferentValuesDelegate
            elif attr in _delegate_widget_class_factory:
                cls = _delegate_widget_class_factory[attr]
            else:
                cls = _delegate_widget_class_factory.get(type(value), QtWidgets.QLabel)

            widget = cls(value)
            # the editingFinished-signal is not seen by mypy coming from PySide6
            widget.editingFinished.connect(lambda w=widget, a=attr: self._editing_finished(a, w.value()))  # type: ignore

            self._layout.addWidget(widget, row, 1)

    def _editing_finished(self, attr, value):
        if value != self.values[attr]:
            self.state.push_undo_command(SetAttributeValue, attr, value)
            self.valuesChanged.emit()
            self.values[attr] = value


class FixedAttributesGroupBox(AttributesGroupBox):
    def __init__(self,
                 uuids: List[str],
                 state: AppState,
                 parent: Optional[QtWidgets.QWidget] = None):
        super().__init__("Global", uuids, state, parent)

        self.setup()

    def setup(self):
        values = {}
        for entity in map(get_entity_from_uuid_safe, self.uuids):
            for attr in entity.fixed_attributes().keys():
                value = entity.__dict__[attr]
                if attr in values:
                    if isinstance(values[attr], _MultipleDifferentValues):
                        values[attr].append(value)
                    elif values[attr] != value:
                        values[attr] = _MultipleDifferentValues(attr, [values[attr], value])
                else:
                    values[attr] = value

        super().setup(values)


class CustomAttributesGroupBox(AttributesGroupBox):

    def create_label(self, text: str) -> EditableLabel:  # type: ignore
        attrs = self.all_attribute_names[:]
        attrs.remove(text)

        name = EditableLabel(text, AttributeNameValidator(attrs))
        name.editing_finished.connect(lambda x, _text=text: self._attribute_name_changed(_text, x))
        name.text_changed.connect(lambda x, _text=text: self._attribute_name_is_changing(_text, x))

        return name

    def __init__(self, uuids: List[str],
                 state: AppState,
                 parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("Custom", uuids, state, parent)

        self.all_attribute_names: List[str] = []
        self.setup()

    def setup(self) -> None:  # type: ignore
        if len(self.uuids) != 1:
            return

        entity = get_entity_from_uuid_safe(self.uuids[0])
        self.all_attribute_names = list(entity.variable_attributes().keys()) + \
                                   list(entity.fixed_attributes().keys())

        attributes = sorted(entity.variable_attributes().keys())
        values = {}
        for attr in attributes:
            values[attr] = entity.__dict__[attr]

        super().setup(values)

        layout = cast(QtWidgets.QGridLayout, self.layout())

        # add a delete-button to each row
        for row, attr in enumerate(attributes):
            but = QtWidgets.QToolButton()
            but.setText('✖')
            but.clicked.connect(lambda a=attr, x=False: self._delete(a))  # type: ignore
            layout.addWidget(but, row, 2)

        # add the new-attribute-button
        new_section_layout = QtWidgets.QHBoxLayout()
        new_section_layout.setContentsMargins(0, 0, 0, 0)

        self.type_combobox = QtWidgets.QComboBox()
        self.type_combobox.addItems(list(_type_name.keys()))
        new_section_layout.addWidget(self.type_combobox)

        button = QtWidgets.QToolButton()
        button.setText('➕')
        button.clicked.connect(self._new)  # type: ignore
        new_section_layout.addWidget(button)

        new_section_layout.addStretch()

        widget = QtWidgets.QWidget()
        widget.setLayout(new_section_layout)

        row = layout.rowCount()
        layout.addWidget(QtWidgets.QLabel('New'), row, 0)
        layout.addWidget(widget, row, 1)

    def _delete(self, attr) -> None:
        self.state.push_undo_command(DeleteAttribute, attr)

    def _new(self) -> None:
        name = 'attribute{}'

        i = 1
        while name.format(i) in self.values.keys():
            i += 1

        name = name.format(i)

        type_name = self.type_combobox.itemText(self.type_combobox.currentIndex())
        default = _type_name_initial_value.get(type_name, _type_name[type_name])()

        self.state.push_undo_command(NewAttribute, name, default)

    def _attribute_name_changed(self, previous: str, text: str) -> None:
        self.state.push_undo_command(RenameAttribute, previous, text)

    def _attribute_name_is_changing(self, previous: str, text: str) -> None:
        # highlight the existing attribute which is using the same text as name
        for label in self.attribute_name_labels.values():
            label.setStyleSheet('background-color: none')

        if text in self.attribute_name_labels and previous != text:
            self.attribute_name_labels[text].setStyleSheet('color: red')


class _EntityEditWidget(QtWidgets.QWidget):
    def __init__(self, uuids: List[str], state: AppState, parent=None) -> None:
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        if len(uuids) >= 1:
            self.fixed_attributes = FixedAttributesGroupBox(uuids, state)
            layout.addWidget(self.fixed_attributes)

            self.attributes: Optional[CustomAttributesGroupBox]
            if len(uuids) == 1:
                self.attributes = CustomAttributesGroupBox(uuids, state)
                layout.addWidget(self.attributes)
            else:
                self.attributes = None

        layout.addStretch()

        self.setLayout(layout)

    def setup(self) -> None:
        if self.attributes:
            self.attributes.setup()
        self.fixed_attributes.setup()


class EntityEditView(QtWidgets.QScrollArea):

    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)

        self.edit: Optional[_EntityEditWidget] = None
        self.state = state
        self.current_uuids: List[str] = []

        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)  # type: ignore
        self.setWidgetResizable(True)

        self.state.state_changed.connect(self.state_changed)

    def state_changed(self, action: str,
                      _: Union[Type[tscat._Catalogue], Type[tscat._Event]],
                      uuids: List[str]) -> None:
        if action == 'active_select':
            if self.current_uuids != uuids:
                if self.edit:
                    self.edit.deleteLater()
                    self.edit = None

                self.edit = _EntityEditWidget(uuids, self.state)
                self.setWidget(self.edit)

                self.current_uuids = uuids

        elif any(uuid in self.current_uuids for uuid in uuids):
            if action == 'deleted':
                for uuid in uuids:
                    self.current_uuids.remove(uuid)  # remove uuid from current-list
                if self.edit:
                    if len(self.current_uuids) > 0:  # if there are still uuids present, just update - like in changed
                        self.edit.setup()
                    else:  # otherwise clear
                        self.edit.deleteLater()
                        self.edit = None
                self.current_uuids = []
            elif action == 'changed':
                if self.edit:
                    self.edit.setup()
