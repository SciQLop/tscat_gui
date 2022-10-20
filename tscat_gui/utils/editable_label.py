import typing

from PySide6 import QtCore, QtWidgets, QtGui


class EditableLabel(QtWidgets.QFrame):
    editing_finished = QtCore.Signal(str)
    text_changed = QtCore.Signal(str)

    class Label(QtWidgets.QLabel):
        clicked = QtCore.Signal()

        def __init__(self, text: str, parent=None):
            super().__init__(text, parent)

        def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                self.clicked.emit()
            super().mousePressEvent(event)

        def enterEvent(self, event: QtCore.QEvent) -> None:  # type: ignore
            self.setCursor(QtCore.Qt.IBeamCursor)  # type: ignore
            super().enterEvent(event)

        def leaveEvent(self, event: QtCore.QEvent) -> None:
            self.setCursor(QtCore.Qt.ArrowCursor)  # type: ignore
            super().leaveEvent(event)

    class LineEdit(QtWidgets.QLineEdit):
        finished = QtCore.Signal()
        changed = QtCore.Signal(str)
        canceled = QtCore.Signal()

        def __init__(self, text: str, validator: QtGui.QValidator, parent=None):
            super().__init__(text, parent)

            self.setValidator(validator)

            self.textChanged.connect(self.text_changed)  # type: ignore
            self.returnPressed.connect(lambda: self.finished.emit())  # type: ignore
            self.editingFinished.connect(lambda: self.finished.emit())  # type: ignore

        def text_changed(self, text: str):
            if self.validator():
                if self.validator().validate(text, len(text) - 1) == QtGui.QValidator.Acceptable:  # type: ignore
                    self.setStyleSheet('border: 1px solid green')
                else:
                    self.setStyleSheet('border: 1px solid red')
            self.changed.emit(text)

        def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
            # keep focus here if value is not valid
            if self.validator() is None or \
                self.validator().validate(self.text(),
                                          len(self.text()) - 1) == QtGui.QValidator.Acceptable:  # type: ignore
                self.finished.emit()
            else:
                self.canceled.emit()
                # self.setFocus()  maybe it's better to not allow focus-stealing, but seems much harder to implement

            super().focusOutEvent(event)

        def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
            if event.key() == QtCore.Qt.Key_Escape:  # type: ignore
                self.canceled.emit()

            super().keyPressEvent(event)

    def __init__(self, text: str, validator: QtGui.QValidator = None, parent=None):
        super().__init__(parent)

        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)  # type: ignore

        self.text = text
        self.validator = validator
        self.label: typing.Optional[EditableLabel.Label] = None
        self.lineedit = None

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)

        self.display()

    def display(self):
        if self.label:
            return

        if self.lineedit:
            self._layout.removeWidget(self.lineedit)
            self.lineedit.deleteLater()
            self.lineedit = None

        self.label = EditableLabel.Label(self.text)
        self.label.clicked.connect(self.edit)
        self._layout.insertWidget(0, self.label)

    def edit(self):
        if self.lineedit:
            return

        if self.label:
            self._layout.removeWidget(self.label)
            self.label.deleteLater()
            self.label = None

        self.lineedit = EditableLabel.LineEdit(self.text, self.validator)
        self.lineedit.changed.connect(lambda x: self.text_changed.emit(x))
        self.lineedit.finished.connect(self.finish_editing)
        self.lineedit.canceled.connect(self.cancel_editing)

        self._layout.insertWidget(0, self.lineedit)

        self.lineedit.setFocus()

    def cancel_editing(self):
        self.editing_finished.emit(self.text)
        self.display()

    def finish_editing(self):
        if self.lineedit:
            if self.text != self.lineedit.text():
                self.text = self.lineedit.text()
                self.editing_finished.emit(self.text)
        self.display()
