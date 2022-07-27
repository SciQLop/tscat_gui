from PySide6 import QtCore, QtWidgets, QtGui

from .utils.helper import AttributeNameValidator, IntDelegate, FloatDelegate, DateTimeDelegate, BoolDelegate, \
    StrDelegate
from .utils.editable_label import EditableLabel

from typing import Union, Type

from tscat.filtering import Comparison, Field, Attribute, Any, All, Not, In, InCatalogue, Has, Predicate, Match
import tscat.filtering
import datetime as dt


class _PredicateWidget(QtWidgets.QWidget):
    changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        if parent:
            self.changed.connect(lambda p=parent: p.changed.emit())

    def delete_child(self, child):
        pass

    def predicate(self):
        pass


class _Root(_PredicateWidget):
    def __init__(self, predicate: Predicate):
        super().__init__(None)

        if predicate is None:
            predicate = Any()  # default and limit to LogicalCombination when creating a new one

        self._first = predicate_to_widget_factory(predicate, None)
        if self._first:
            c = QtWidgets.QHBoxLayout()
            c.setContentsMargins(0, 0, 0, 0)
            c.addWidget(self._first)
            self.setLayout(c)

            self._first.changed.connect(lambda: self.changed.emit())

    def delete_child(self, child):
        if self._first:
            self._first.deleteLater()
            self._first = None
            self.changed.emit()

    def predicate(self):
        return self._first.predicate() if self._first else None


class _Comparison(_PredicateWidget):
    OP_LT = 0
    OP_LE = 1
    OP_EQ = 2
    OP_GT = 3
    OP_GE = 4
    OP_NE = 5
    OP_MATCH = 6
    OP_NOT_MATCH = 7

    OP_LABELS = ['<', '<=', '==', '>', '>=', '!=', '=~', '!~']
    OP_LABELS_NEGATED = ['>=', '>', '!=', '<=', '<', '==', '!~', '=~']

    event_fixed_keys_types = {
        'start': dt.datetime,
        'stop': dt.datetime,
        'author': str,
        'uuid': str
    }

    possible_types = {
        'Date': dt.datetime,
        'String': str,
        'Integer': int,
        'Float': float,
        'Bool': bool,
    }

    type_widget = {
        int: IntDelegate,
        str: StrDelegate,
        float: FloatDelegate,
        bool: BoolDelegate,
        dt.datetime: DateTimeDelegate,
    }

    operator_types = {
        '=~': str,
        '!~': str,
    }

    def __init__(self, predicate: Union[Comparison, Match, None], negate: bool, parent: _PredicateWidget):
        super().__init__(parent)

        if predicate is None:
            predicate = Comparison('==', Field('author'), '')
            negate = False

        if type(predicate) == Comparison:
            if negate:
                predicate._op = _Comparison.OP_LABELS_NEGATED[_Comparison.OP_LABELS.index(predicate._op)]

        self._original_field = predicate._lhs.value
        self._original_value = predicate._rhs

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._field = EditableLabel.LineEdit(self._original_field, AttributeNameValidator())
        completer = QtWidgets.QCompleter(list(_Comparison.event_fixed_keys_types.keys()), parent=self)
        completer.setCaseSensitivity(QtCore.Qt.CaseSensitive)
        self._field.setCompleter(completer)

        self._field.finished.connect(self._field_editing_finished)
        # self._field.canceled.connect(lambda _f=self._field: _f.setText(self._original_field) and self.changed.emit())

        self._layout.addWidget(self._field)

        self._op_label = QtWidgets.QLabel()
        self._op_label.setFont(QtGui.QFont("monospace"))

        if type(predicate) == Match:
            op_text = '!~' if negate else '=~'
        else:
            op_text = predicate._op

        self._op_label.setText(op_text)
        self._layout.addWidget(self._op_label)

        self._type_cb = QtWidgets.QComboBox()
        for name, _type in _Comparison.possible_types.items():
            self._type_cb.addItem(name, _type)
        self._type_cb.currentIndexChanged.connect(self._type_index_changed)
        self._layout.addWidget(self._type_cb)

        self._current_value_widget = None
        # used to store widget which have at some point been used (to not lose last values if type is changed)
        self._value_widgets = {}
        self.setLayout(self._layout)

        # initial value of TypeComboBox depends on initial filter-value
        self._select_value_type(type(self._original_value))
        self._type_index_changed(self._type_cb.currentIndex())
        self._current_value_widget.set_value(self._original_value)

    def _select_value_type(self, selected_type: Union[Type, None] = None):
        value_type_from_field = _Comparison.event_fixed_keys_types.get(self._field.text(), None)
        value_type_from_operator = _Comparison.operator_types.get(self._op_label.text(), None)

        if value_type_from_operator is None and value_type_from_field is None:
            self._type_cb.setEnabled(True)
        else:
            selected_type = value_type_from_operator if value_type_from_operator else value_type_from_field
            self._type_cb.setEnabled(False)

        if selected_type:
            index = self._type_cb.findData(selected_type)
            self._type_cb.setCurrentIndex(index)

    def _field_editing_finished(self):
        self._select_value_type()
        self.changed.emit()

    def _type_index_changed(self, index: int):
        _type = self._type_cb.itemData(index)

        if self._current_value_widget:
            self._layout.removeWidget(self._current_value_widget)
            self._current_value_widget.hide()

        widget = self._value_widgets.get(_type, None)
        if not widget:
            widget = _Comparison.type_widget[_type]()
            widget.editingFinished.connect(lambda: self.changed.emit())
            self._value_widgets[_type] = widget
        else:
            widget.show()

        self._current_value_widget = widget
        self._layout.addWidget(widget)
        self.changed.emit()

    def predicate(self) -> Union[Comparison, Match, Not]:
        if self._field.text() in tscat.Event._fixed_keys:
            field = Field(self._field.text())
        else:
            field = Attribute(self._field.text())

        if self.operator_index() == _Comparison.OP_MATCH:
            return Match(field, self._current_value_widget.value())
        elif self.operator_index() == _Comparison.OP_NOT_MATCH:
            return Not(Match(field, self._current_value_widget.value()))
        else:
            return Comparison(self._op_label.text(), field, self._current_value_widget.value())

    def set_operator(self, op):
        self._op_label.setText(_Comparison.OP_LABELS[op])
        self._select_value_type()

    def operator_index(self):
        return _Comparison.OP_LABELS.index(self._op_label.text())


class _AttributeIsPresent(_PredicateWidget):
    OP_HAS = 0
    OP_HAS_NOT = 1

    OP_LABELS = ['is present', 'is not present']

    def __init__(self, predicate: Union[Has, None], negate: bool, parent: _PredicateWidget):
        super().__init__(parent)

        c = QtWidgets.QHBoxLayout()
        c.setContentsMargins(0, 0, 0, 0)

        c.addWidget(QtWidgets.QLabel("Attribute"))

        self.attribute = EditableLabel.LineEdit(predicate._operand.value if predicate else "", AttributeNameValidator())
        self.attribute.finished.connect(lambda: self.changed.emit())

        c.addWidget(self.attribute)

        self._op_label = QtWidgets.QLabel()
        self.set_operator(_AttributeIsPresent.OP_HAS_NOT if negate else _AttributeIsPresent.OP_HAS)
        c.addWidget(self._op_label)

        self.setLayout(c)

    def predicate(self) -> Union[Has, Not]:
        predicate = Has(Attribute(self.attribute.text()))
        if self.operator_index() == _AttributeIsPresent.OP_HAS_NOT:
            return Not(predicate)
        return predicate

    def set_operator(self, op):
        self._op_label.setText(_AttributeIsPresent.OP_LABELS[op])

    def operator_index(self):
        return _AttributeIsPresent.OP_LABELS.index(self._op_label.text())


class _StringInStringList(_PredicateWidget):
    OP_IN = 0
    OP_NOT_IN = 1

    OP_LABELS = ['is in string-list', 'is not in string-list']

    event_fixed_keys = ['tags', 'products']

    def __init__(self, predicate: Union[In, None], negate: bool, parent: _PredicateWidget):
        super().__init__(parent)

        c = QtWidgets.QHBoxLayout()
        c.setContentsMargins(0, 0, 0, 0)

        c.addWidget(QtWidgets.QLabel("String"))

        self.le = QtWidgets.QLineEdit(predicate._lhs if predicate else "")
        c.addWidget(self.le)

        self._op_label = QtWidgets.QLabel()
        self.set_operator(_StringInStringList.OP_NOT_IN if negate else _StringInStringList.OP_IN)
        c.addWidget(self._op_label)

        self.attribute = EditableLabel.LineEdit(predicate._rhs.value if predicate else "", AttributeNameValidator())
        completer = QtWidgets.QCompleter(_StringInStringList.event_fixed_keys, parent=self)
        completer.setCaseSensitivity(QtCore.Qt.CaseSensitive)
        self.attribute.setCompleter(completer)
        self.attribute.finished.connect(lambda: self.changed.emit())

        c.addWidget(self.attribute)

        self.setLayout(c)

    def predicate(self) -> Union[In, Not]:
        attr_or_field_type = Field if self.attribute.text() in _StringInStringList.event_fixed_keys else Attribute
        predicate = In(self.le.text(), attr_or_field_type(self.attribute.text()))
        if self.operator_index() == _StringInStringList.OP_NOT_IN:
            return Not(predicate)
        return predicate

    def set_operator(self, op):
        self._op_label.setText(_StringInStringList.OP_LABELS[op])

    def operator_index(self):
        return _StringInStringList.OP_LABELS.index(self._op_label.text())


class _InCatalogue(_PredicateWidget):
    OP_IN = 0
    OP_NOT_IN = 1

    OP_LABELS = ['is in catalogue', 'is not in catalogue']

    def __init__(self, predicate: Union[InCatalogue, None], negate: bool, parent: _PredicateWidget):
        super().__init__(parent)

        c = QtWidgets.QHBoxLayout()
        c.setContentsMargins(0, 0, 0, 0)

        self._op_label = QtWidgets.QLabel()
        self.set_operator(_InCatalogue.OP_NOT_IN if negate else _InCatalogue.OP_IN)
        c.addWidget(self._op_label)

        self.catalogues = QtWidgets.QComboBox()
        for cat in tscat.get_catalogues():
            self.catalogues.addItem(cat.name, cat)

        for cat in tscat.get_catalogues(removed_items=True):
            self.catalogues.addItem(cat.name + " (in trash)", cat)
        self.catalogues.currentIndexChanged.connect(lambda: self.changed.emit())

        c.addWidget(self.catalogues)

        self.setLayout(c)

    def predicate(self) -> Union[In, Not]:
        predicate = InCatalogue(self.catalogues.itemData(self.catalogues.currentIndex()))
        if self.operator_index() == _InCatalogue.OP_NOT_IN:
            return Not(predicate)
        return predicate

    def set_operator(self, op):
        self._op_label.setText(_InCatalogue.OP_LABELS[op])

    def operator_index(self):
        return _InCatalogue.OP_LABELS.index(self._op_label.text())


operators = [
    ['Equal', _Comparison, _Comparison.OP_EQ],
    ['Not Equal', _Comparison, _Comparison.OP_NE],
    ['Less Than', _Comparison, _Comparison.OP_LT],
    ['Less Or Equal Than', _Comparison, _Comparison.OP_LE],
    ['Greater Than', _Comparison, _Comparison.OP_GT],
    ['Greater Or Equal Than', _Comparison, _Comparison.OP_GE],
    ['Match Regex', _Comparison, _Comparison.OP_MATCH],
    ['Does Not Match Regex', _Comparison, _Comparison.OP_NOT_MATCH],
    ['In String List', _StringInStringList, _StringInStringList.OP_IN],
    ['Not In String List', _StringInStringList, _StringInStringList.OP_NOT_IN],
    ['In Catalogue', _InCatalogue, _InCatalogue.OP_IN],
    ['Not In Catalogue', _InCatalogue, _InCatalogue.OP_NOT_IN],
    ['Attribute Present', _AttributeIsPresent, _AttributeIsPresent.OP_HAS],
    ['Attribute Not Present', _AttributeIsPresent, _AttributeIsPresent.OP_HAS_NOT],
]


class _Condition(_PredicateWidget):
    def __init__(self, predicate: Union[Comparison, Match, In, Has, InCatalogue, None], parent: _PredicateWidget):
        super().__init__(parent)

        self._hlayout = QtWidgets.QHBoxLayout()
        self._hlayout.setContentsMargins(0, 0, 0, 0)

        self._cb = QtWidgets.QComboBox()
        for op in operators:
            self._cb.addItem(op[0], op)
        self._cb.currentIndexChanged.connect(self._condition_operator_changed)

        self._hlayout.addWidget(self._cb)

        negate = False
        while type(predicate) == Not:
            negate = not negate
            predicate = predicate._operand

        self.condition = None

        if type(predicate) in [Comparison, Match] or predicate is None:
            self.condition = _Comparison(predicate, negate, self)
        elif type(predicate) == Has:
            self.condition = _AttributeIsPresent(predicate, negate, self)
        elif type(predicate) == In:
            self.condition = _StringInStringList(predicate, negate, self)
        elif type(predicate) == InCatalogue:
            self.condition = _InCatalogue(predicate, negate, self)

        self.condition.changed.connect(lambda: self.changed.emit())

        self.conditions_seen = {type(self.condition): self.condition}

        for index, op in enumerate(operators):
            if isinstance(self.condition, op[1]) and op[2] == self.condition.operator_index():
                self._cb.setCurrentIndex(index)
                break

        self._hlayout.addWidget(self.condition)

        self._hlayout.addStretch()

        self._hlayout.addWidget(_DeletePredicateWidget(self))

        self.setLayout(self._hlayout)

    def _condition_operator_changed(self, index: int):
        data = self._cb.itemData(index)

        if not isinstance(self.condition, data[1]):
            self._hlayout.removeWidget(self.condition)
            self.condition.hide()

            if data[1] in self.conditions_seen:
                self.condition = self.conditions_seen[data[1]]
            else:
                self.condition = data[1](None, False, self)
                self.condition.set_operator(data[2])
                self.condition.changed.connect(lambda: self.changed.emit())
                self.conditions_seen[type(self.condition)] = self.condition

            self._hlayout.insertWidget(self._hlayout.count() - 2, self.condition)
            self.condition.show()
        else:
            self.condition.set_operator(data[2])

        self.changed.emit()

    def predicate(self):
        return self.condition.predicate()

    def delete_child(self, child):
        raise AssertionError('Should never be called.')


class _LogicalCombination(_PredicateWidget):
    def __init__(self, predicate: Union[All, Any, None], parent: _PredicateWidget):
        super().__init__(parent)

        if predicate is None:
            predicate = Any()

        self._children: list[_PredicateWidget] = []

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(20, 0, 0, 0)

        button_group = QtWidgets.QButtonGroup(self)

        sub_layout = QtWidgets.QHBoxLayout()
        sub_layout.setContentsMargins(0, 0, 0, 0)

        self._all = QtWidgets.QRadioButton("All Of")
        button_group.addButton(self._all)
        sub_layout.addWidget(self._all)

        self._any = QtWidgets.QRadioButton("Any Of")
        button_group.addButton(self._any)
        sub_layout.addWidget(self._any)

        sub_layout.addStretch()
        sub_layout.addWidget(_DeletePredicateWidget(self))

        button_group.buttonClicked.connect(lambda x: self.changed.emit())

        if isinstance(predicate, Any):
            self._any.setChecked(True)
        else:
            self._all.setChecked(True)

        self._layout.addLayout(sub_layout)

        for pred in predicate._predicates:
            widget = predicate_to_widget_factory(pred, self)
            self._layout.addWidget(widget)
            self.add_child_predicate(widget)

        add = _AddPredicateWidget(self)
        add.new.connect(lambda x: self.new(x.selected_type()))
        self._layout.addWidget(add)

        self.setLayout(self._layout)

    def new(self, cls: Type[_PredicateWidget]):
        t = cls(None, self)
        self._layout.insertWidget(self._layout.count() - 1, t)
        self.add_child_predicate(t)
        self.changed.emit()

    def add_child_predicate(self, widget: _PredicateWidget):
        self._children += [widget]

    def child_predicates(self):
        return self._children[:]

    def predicate(self) -> Union[All, Any]:
        child_predicates = []
        for child in self.child_predicates():
            child_predicates += [child.predicate()]

        if self._any.isChecked():
            return Any(*child_predicates)
        else:
            return All(*child_predicates)

    def delete_child(self, widget):
        widget.deleteLater()
        self._layout.removeWidget(widget)
        self._children.remove(widget)
        self.changed.emit()


def predicate_to_widget_factory(predicate: Predicate, parent: _PredicateWidget):
    if type(predicate) in [Any, All]:
        cls = _LogicalCombination
    else:
        cls = _Condition

    return cls(predicate, parent)


class _AddPredicateWidget(QtWidgets.QWidget):
    new = QtCore.Signal(QtWidgets.QWidget)

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)

        l = QtWidgets.QHBoxLayout()
        l.setContentsMargins(0, 0, 0, 0)

        self.type_combobox = QtWidgets.QComboBox()
        self.type_combobox.addItem('Condition', _Condition)
        self.type_combobox.addItem('Logical Combination', _LogicalCombination)

        l.addWidget(self.type_combobox)

        button = QtWidgets.QToolButton()
        button.setText('Add')
        button.clicked.connect(lambda: self.new.emit(self))
        l.addWidget(button)

        l.addStretch()

        self.setLayout(l)

    def selected_type(self):
        return self.type_combobox.itemData(self.type_combobox.currentIndex())


class _DeletePredicateWidget(QtWidgets.QToolButton):
    def __init__(self, widget: _PredicateWidget):
        super().__init__(widget)

        self.setText('✖')

        self.clicked.connect(lambda: widget.parent().delete_child(widget))


class SimplePredicateEditDialog(QtWidgets.QDialog):
    def __init__(self, predicate: Union[tscat.Predicate, None], parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout()

        self.predicate = predicate

        self._root = _Root(predicate)

        def predicate_changed():
            self.predicate = self._root.predicate()

        self._root.changed.connect(predicate_changed)

        layout.addWidget(self._root)

        ok = QtWidgets.QPushButton("OK")
        ok.clicked.connect(lambda: self.accept())

        cancel = QtWidgets.QPushButton("Cancel")
        cancel.clicked.connect(lambda: self.reject())

        last_line_layout = QtWidgets.QHBoxLayout()
        last_line_layout.addStretch()

        last_line_layout.addWidget(ok)
        last_line_layout.addWidget(cancel)

        layout.addStretch()
        layout.addLayout(last_line_layout)

        self.setLayout(layout)
