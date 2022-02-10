from PySide2 import QtCore, QtWidgets

from .utils.keyword_list import EditableKeywordListWidget

import tscat
import datetime as dt


class _IntDelegate(QtWidgets.QSpinBox):
    def __init__(self, value: int, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.setRange(-2 ** 31, 2 ** 31 - 1)
        self.setValue(value)


class _FloatDelegate(QtWidgets.QDoubleSpinBox):
    def __init__(self, value: float, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.setValue(value)
        self.setRange(float('-inf'), float('inf'))


class _BoolDelegate(QtWidgets.QCheckBox):
    def __init__(self, value: float, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.setChecked(value)


_delegate_widget_class_factory = {
    'uuid': QtWidgets.QLabel,

    int: _IntDelegate,
    str: QtWidgets.QLineEdit,
    float: _FloatDelegate,
    list: EditableKeywordListWidget,
    bool: _BoolDelegate,
    dt.datetime: QtWidgets.QDateTimeEdit,
}


class AttributeGroupBox(QtWidgets.QGroupBox):
    def __init__(self,
                 title: str,
                 attributes: list[str],
                 catalogue: tscat.Catalogue,
                 parent: QtWidgets.QWidget = None):
        super().__init__(title, parent)

        self.catalogue = catalogue

        layout = QtWidgets.QGridLayout()
        layout.setMargin(0)

        for row, attr in enumerate(attributes):
            layout.addWidget(QtWidgets.QLabel(attr.title()), row, 0)
            value = catalogue.__dict__[attr]

            if attr in _delegate_widget_class_factory:
                cls = _delegate_widget_class_factory[attr]
            else:
                cls = _delegate_widget_class_factory.get(type(value), QtWidgets.QLabel)
            layout.addWidget(cls(value), row, 1)

        self.setLayout(layout)


class CatalogueEditWidget(QtWidgets.QScrollArea):
    def __init__(self, index: QtCore.QModelIndex, parent=None):
        super().__init__(parent)
        self.catalogue: tscat.Catalogue = index.internalPointer()

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.addWidget(AttributeGroupBox("Main", ['name', 'author', 'uuid', 'tags'],
                                           self.catalogue, ))
        layout.addWidget(AttributeGroupBox("Other", sorted(self.catalogue.variable_attributes_as_dict().keys()),
                                           self.catalogue))

        layout.addStretch()

        widget = QtWidgets.QWidget()
        widget.setLayout(layout)

        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.setWidgetResizable(True)
        self.setWidget(widget)
