from PySide2 import QtCore, QtWidgets

from .utils.keyword_list import EditableKeywordListWidget

import tscat
import datetime as dt


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
            if type(value) == str:
                layout.addWidget(QtWidgets.QLineEdit(value), row, 1)
            elif type(value) == float:
                sb = QtWidgets.QDoubleSpinBox()
                sb.setValue(value)
                sb.setRange(float('-inf'), float('inf'))
                layout.addWidget(sb, row, 1)
            elif type(value) == int:
                sb = QtWidgets.QSpinBox()
                sb.setRange(-2 ** 31, 2 ** 31 - 1)
                sb.setValue(value)
                layout.addWidget(sb, row, 1)
            elif type(value) == list:
                layout.addWidget(EditableKeywordListWidget(value), row, 1)
            elif type(value) == bool:
                cb = QtWidgets.QCheckBox()
                cb.setChecked(value)
                layout.addWidget(cb, row, 1)
            elif type(value) == dt.datetime:
                layout.addWidget(QtWidgets.QDateTimeEdit(value), row, 1)
            else:
                layout.addWidget(QtWidgets.QLabel(f'TODO {type(value)} {value}'), row, 1)

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
