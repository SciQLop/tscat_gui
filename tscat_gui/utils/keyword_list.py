from .flow_layout import FlowLayout

from PySide2 import QtWidgets, QtCore, QtGui

# UTF-8 letters in the begging, then also numbers and underscore
_tag_validation_regex = QtCore.QRegularExpression(r'\p{L}\w*')


class _Keyword(QtWidgets.QFrame):
    updated = QtCore.Signal(QtWidgets.QWidget)
    closed = QtCore.Signal(QtWidgets.QWidget)

    class Label(QtWidgets.QLabel):
        clicked = QtCore.Signal()

        def __init__(self, text: str, parent=None):
            super().__init__(text, parent)

        def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                self.clicked.emit()
            super().mousePressEvent(event)

    class DeleteLabel(QtWidgets.QLabel):
        clicked = QtCore.Signal()

        def __init__(self, parent=None):
            super().__init__('✕', parent)
            self.setMargin(1)
            self.setObjectName('DeleteLabel')
            self.setStyleSheet(
                "#DeleteLabel { border-radius: 5px; background: #444; min-width: 10px; min-height: 10px; }")

        def enterEvent(self, event: QtCore.QEvent) -> None:
            self.setText('✖')
            super().enterEvent(event)

        def leaveEvent(self, event: QtCore.QEvent) -> None:
            self.setText('✕')
            super().leaveEvent(event)

        def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                self.clicked.emit()

            super().mousePressEvent(event)

    def __init__(self, text: str, tag_list: QtCore.QObject, parent=None):
        super().__init__(parent)

        self.text = text
        self.tag_list = tag_list

        self.setObjectName('OneKeyword')
        self.setStyleSheet("#OneKeyword { border-radius: 15px; background: #999; }")

        self.delete_label = _Keyword.DeleteLabel()
        self.delete_label.clicked.connect(lambda: self.closed.emit(self))

        self.layout = QtWidgets.QHBoxLayout()
        self.layout.addWidget(self.delete_label)
        self.layout.setMargin(5)
        self.setLayout(self.layout)

        self.lineedit = None
        self.tag_label = None
        self.display()

    def display(self):
        if self.tag_label:
            return

        if self.lineedit:
            self.layout.removeWidget(self.lineedit)
            self.lineedit.deleteLater()
            self.lineedit = None

        self.tag_label = _Keyword.Label(self.text)
        self.tag_label.clicked.connect(lambda: self.tag_list._request_edit(self))
        self.layout.insertWidget(0, self.tag_label)

    def edit(self):
        if self.lineedit:
            return

        if self.tag_label:
            self.layout.removeWidget(self.tag_label)
            self.tag_label.deleteLater()
            self.tag_label = None

        completer = QtWidgets.QCompleter(self.tag_list.completion_strings)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)

        self.lineedit = QtWidgets.QLineEdit(self.text)
        self.lineedit.setCompleter(completer)
        self.lineedit.setValidator(self.tag_list.regex_validator)
        self.lineedit.returnPressed.connect(self.finish_editing)
        self.lineedit.editingFinished.connect(self.finish_editing)

        self.layout.insertWidget(0, self.lineedit)

        self.lineedit.setFocus()

    def finish_editing(self):
        if self.lineedit:
            if self.text != self.lineedit.text():
                self.text = self.lineedit.text()
            self.updated.emit(self)
        self.display()


class EditableKeywordListWidget(QtWidgets.QWidget):
    editing_finished = QtCore.Signal(list)

    def __init__(self, strings: list[str], completion_strings: list[str] = [], parent=None):
        super().__init__(parent)

        self.layout = FlowLayout()
        # self.layout.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
        # self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        # self.setStyleSheet("border: 3px solid red")

        self.new_tag = QtWidgets.QPushButton('➕')
        self.new_tag.clicked.connect(lambda _: self._add_tag('', edit=True))
        self.layout.addWidget(self.new_tag)

        self.tags = []
        for text in strings:
            self._add_tag(text)

        self.completion_strings = set(completion_strings)

        self.regex_validator = QtGui.QRegularExpressionValidator(_tag_validation_regex)

        self.setLayout(self.layout)

    def _add_tag(self, text: str, edit=False):
        tag = _Keyword(text, self)
        self.tags += [tag]
        tag.updated.connect(self._tag_text_updated)
        tag.closed.connect(self._delete_tag)

        # insert before the new_tag-button
        self.layout.removeWidget(self.new_tag)
        self.layout.addWidget(tag)
        self.layout.addWidget(self.new_tag)

        if edit:
            self._request_edit(tag)

    def _update_tag_texts(self):
        tag_texts = [tag.text for tag in self.tags if tag.text]
        self.editing_finished.emit(tag_texts)

    def _tag_text_updated(self, tag: _Keyword):
        if len(tag.text) == 0:
            self._delete_tag(tag)
        else:
            self.completion_strings.add(tag.text)
        self._update_tag_texts()

    def _request_edit(self, tag: _Keyword):
        for t in self.tags:
            t.finish_editing()
        tag.edit()

    def _delete_tag(self, tag: _Keyword):
        self.tags.remove(tag)
        self.layout.removeWidget(tag)
        tag.deleteLater()

        self._update_tag_texts()
