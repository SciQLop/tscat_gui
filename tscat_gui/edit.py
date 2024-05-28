import datetime as dt
import functools
from typing import Any, Callable, Dict, List, Optional, Type, Union, cast

from PySide6 import QtCore, QtWidgets

import tscat
import tscat.filtering
from .metadata import catalogue_meta_data
from .model_base.constants import PathAttributeName
from .predicate import SimplePredicateEditDialog
from .state import AppState
from .tscat_driver.actions import Action, GetCatalogueAction, SetAttributeAction
from .undo import DeleteAttribute, DeleteAttributeAction, NewAttribute, RenameAttribute, SetAttributeValue
from .utils.editable_label import EditableLabel
from .utils.helper import AttributeNameValidator, BoolDelegate, DateTimeDelegate, FloatDelegate, IntDelegate, \
    StrDelegate
from .utils.keyword_list import EditableKeywordListWidget


class _UuidLabelDelegate(QtWidgets.QWidget):
    editingFinished = QtCore.Signal()  # never emitted

    def __init__(self, value: str, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        label = QtWidgets.QLabel(value, self)
        label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)  # type: ignore
        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(label)
        layout.addStretch()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)


class _ReadOnlyString(str):
    pass


class _PredicateDelegate(QtWidgets.QWidget):
    editingFinished = QtCore.Signal()

    def __init__(self, value: Optional[tscat.filtering.Predicate], parent: Optional[QtWidgets.QWidget] = None):
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

    def value(self) -> Union[tscat.filtering.Predicate, None]:
        return self.predicate


class _MultipleDifferentValues(list):
    def __init__(self, attribute: str, *args: List) -> None:
        super().__init__(*args)
        self.attribute = attribute


class _RatingDelegate(QtWidgets.QWidget):
    editingFinished = QtCore.Signal()

    def __init__(self, value: Optional[int], parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self.label = QtWidgets.QLabel(self)
        self.slider = QtWidgets.QSlider(self)
        self.slider.setOrientation(QtCore.Qt.Horizontal)  # type: ignore
        self.slider.setRange(0, 10)
        self.slider.setTickInterval(1)
        self.slider.setTickPosition(QtWidgets.QSlider.TicksBelow)  # type: ignore
        self.slider.valueChanged.connect(self._slider_value_changed)  # type: ignore
        self.slider.sliderReleased.connect(lambda: self.editingFinished.emit())  # type: ignore

        if value:
            self.label.setText(str(value))
            self.slider.setValue(value)
        else:
            self.label.setText(" ")
            self.slider.setValue(0)

        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.slider)
        layout.addWidget(self.label)
        layout.addStretch()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def _slider_value_changed(self, value: int) -> None:
        if value == 0:
            self.label.setText(" ")
        else:
            self.label.setText(str(value))

    def value(self) -> Any:
        if self.slider.value() == 0:
            return None
        else:
            return self.slider.value()


_delegate_widget_class_factory = {
    'uuid': _UuidLabelDelegate,
    'predicate': _PredicateDelegate,
    'rating': _RatingDelegate,

    _ReadOnlyString: _UuidLabelDelegate,
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
                 reset_value_selection: Callable[[List[Any]], Any] = lambda x: x[0],
                 parent: Optional[QtWidgets.QWidget] = None):
        super().__init__('<multiple-values-click-to-reset>', parent)
        assert len(values) > 0

        self.reset_value = reset_value_selection(values)

        self.clicked.connect(lambda x: self.editingFinished.emit())  # type: ignore

    def value(self) -> Any:
        return self.reset_value


class _MultipleDifferentValuesDelegateMin(_MultipleDifferentValuesDelegate):
    def __init__(self,
                 values: _MultipleDifferentValues,
                 parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(values, min, parent)


class _MultipleDifferentValuesDelegateMax(_MultipleDifferentValuesDelegate):
    def __init__(self,
                 values: _MultipleDifferentValues,
                 parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(values, max, parent)


_type_name = {
    'Boolean': bool,
    'DateTime': dt.datetime,
    'Float': float,
    'Integer': int,
    'String': str,
    'Word List': list,
}

_type_name_initial_value = {
    'DateTime': lambda: dt.datetime.now()
}


class AttributesGroupBox(QtWidgets.QGroupBox):
    valuesChanged = QtCore.Signal()

    def create_label(self, text: str) -> QtWidgets.QLabel:  # type: ignore
        return QtWidgets.QLabel(text.title())

    def __init__(self, title: str,
                 state: AppState,
                 parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title, parent)

        self.attribute_name_labels: Dict[str, QtWidgets.QLabel] = {}
        self.state = state
        self.values: Dict = {}

        self._layout = QtWidgets.QGridLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)

    def setup_values(self, values: Dict):
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

            # special case for UUIDs - hide uuid-attribute
            if attr == 'uuid':
                continue

            label = self.create_label(attr)
            self._layout.addWidget(label, row, 0)

            self.attribute_name_labels[attr] = label

            value = values[attr]

            cls: Type[Union[_MultipleDifferentValuesDelegate, _UuidLabelDelegate, _PredicateDelegate,
            IntDelegate, StrDelegate, FloatDelegate,
            EditableKeywordListWidget, BoolDelegate, DateTimeDelegate]]

            if isinstance(value, _MultipleDifferentValues):
                if attr == 'start':
                    cls = _MultipleDifferentValuesDelegateMin
                elif attr == 'stop':
                    cls = _MultipleDifferentValuesDelegateMax
                else:
                    cls = _MultipleDifferentValuesDelegate
            elif attr in _delegate_widget_class_factory:
                cls = _delegate_widget_class_factory[attr]
            else:
                cls = _delegate_widget_class_factory.get(type(value), QtWidgets.QLabel)

            widget = cls(value, parent=self)

            # the editingFinished-signal is not seen by mypy coming from PySide6
            widget.editingFinished.connect(  # type: ignore
                functools.partial(self._edit_finished_on_widget, widget, attr))  # type: ignore
            self._layout.addWidget(widget, row, 1)

    def _edit_finished_on_widget(self, w: QtWidgets.QWidget, a: str) -> None:

        assert isinstance(w, (_MultipleDifferentValuesDelegate, _PredicateDelegate, _RatingDelegate,
                              IntDelegate, StrDelegate, FloatDelegate,
                              EditableKeywordListWidget, BoolDelegate, DateTimeDelegate))

        self._editing_finished(a, w.value())

    def _editing_finished(self, attr, value) -> None:
        if value != self.values[attr]:
            self.state.push_undo_command(SetAttributeValue, attr, value)
            self.valuesChanged.emit()
            self.values[attr] = value


class FixedAttributesGroupBox(AttributesGroupBox):
    def __init__(self,
                 state: AppState,
                 parent: Optional[QtWidgets.QWidget] = None):
        super().__init__("", state, parent)

        self.setStyleSheet("QGroupBox { font-weight: bold; }")

    def setup(self, entities: List[Union[tscat._Catalogue, tscat._Event]]) -> None:
        values: Dict[str, Any] = {}

        for entity in entities:
            for attr in entity.fixed_attributes().keys():
                value = entity.__dict__[attr]
                if attr in values:
                    if isinstance(values[attr], _MultipleDifferentValues):
                        values[attr].append(value)
                    elif values[attr] != value:
                        values[attr] = _MultipleDifferentValues(attr, [values[attr], value])
                else:
                    values[attr] = value

        super().setup_values(values)


class CustomAttributesGroupBox(AttributesGroupBox):

    def create_label(self, text: str) -> EditableLabel:  # type: ignore
        attrs = self.all_attribute_names[:]
        attrs.remove(text)

        name = EditableLabel(text, AttributeNameValidator(attrs))
        name.editing_finished.connect(lambda x, _text=text: self._attribute_name_changed(_text, x))
        name.text_changed.connect(lambda x, _text=text: self._attribute_name_is_changing(_text, x))

        return name

    def __init__(self,
                 state: AppState,
                 parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("Custom fields", state, parent)

        self.all_attribute_names: List[str] = []

        self.setStyleSheet("QGroupBox { font-weight: bold; }")

    def setup(self, entities: List[Union[tscat._Catalogue, tscat._Event]]) -> None:
        if len(entities) > 1:
            self.hide()
            return

        self.show()

        entity = entities[0]
        self.all_attribute_names = list(entity.variable_attributes().keys()) + \
                                   list(entity.fixed_attributes().keys())

        attributes = sorted(entity.variable_attributes().keys())
        if PathAttributeName in attributes:  # hide PathAttributeName from Editor
            attributes.remove(PathAttributeName)

        values = {}
        for attr in attributes:
            values[attr] = entity.__dict__[attr]

        super().setup_values(values)

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


class CatalogueMetaDataGroupBox(AttributesGroupBox):
    def __init__(self,
                 state: AppState,
                 parent: Optional[QtWidgets.QWidget] = None):
        super().__init__("Catalogue(s) information", state, parent)

        self.setStyleSheet("QGroupBox { font-weight: bold; }")

    def setup(self, entities: List[Union[tscat._Catalogue, tscat._Event]]) -> None:

        catalogues = [entity for entity in entities if isinstance(entity, tscat._Catalogue)]
        if len(catalogues) == 0:
            self.hide()
        else:
            values = {}
            self.show()

            for k, value_func in catalogue_meta_data.items():
                value = value_func(catalogues)
                values[k] = _ReadOnlyString(value)

            super().setup_values(values)


class _EntityEditWidget(QtWidgets.QWidget):
    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        self.meta_data = CatalogueMetaDataGroupBox(state)
        layout.addWidget(self.meta_data)

        self.fixed_attributes = FixedAttributesGroupBox(state)
        layout.addWidget(self.fixed_attributes)

        self.attributes: Optional[CustomAttributesGroupBox]
        self.attributes = CustomAttributesGroupBox(state)
        layout.addWidget(self.attributes)

        layout.addStretch()

        self.setLayout(layout)

    def setup(self, uuids: List[str]) -> None:

        from .tscat_driver.model import tscat_model
        entities = tscat_model.entities_from_uuids(uuids)

        if self.meta_data:
            self.meta_data.setup(entities)
        if self.attributes:
            self.attributes.setup(entities)
        self.fixed_attributes.setup(entities)


class EntityEditView(QtWidgets.QScrollArea):

    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)

        self.edit: Optional[_EntityEditWidget] = None
        self.state = state
        self.current_uuids: List[str] = []

        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)  # type: ignore
        self.setWidgetResizable(True)

        self.state.state_changed.connect(self.state_changed)

        from .tscat_driver.model import tscat_model
        tscat_model.action_done.connect(self._model_action_done)

    def state_changed(self, action: str,
                      _: Union[Type[tscat._Catalogue], Type[tscat._Event]],
                      uuids: List[str]) -> None:
        if action == 'active_select':
            if self.current_uuids != uuids:
                if self.edit:
                    self.edit.deleteLater()
                    self.edit = None

                self.current_uuids = uuids

                if len(uuids) > 0:
                    self.edit = _EntityEditWidget(self.state)
                    self.setWidget(self.edit)
                    self.edit.setup(self.current_uuids)
        elif action == 'passive_select':
            pass
        else:
            print('unsupported (old) state-changed', action)

    def _model_action_done(self, action: Action) -> None:
        if self.edit:
            if isinstance(action, GetCatalogueAction):
                if action.uuid in self.current_uuids:
                    self.edit.setup(self.current_uuids)
            elif isinstance(action, (SetAttributeAction, DeleteAttributeAction)):
                if any(entity.uuid in self.current_uuids for entity in action.entities):
                    self.edit.setup(self.current_uuids)
