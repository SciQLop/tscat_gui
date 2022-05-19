from .flow_layout import FlowLayout
from .editable_label import EditableLabel

from PySide6 import QtWidgets, QtCore, QtGui

import re

# UTF-8 letters in the beginning, then also numbers and underscore
_tag_validation_regex = re.compile(r'[a-z]\w*')


class _Keyword(EditableLabel):
    closed = QtCore.Signal(QtWidgets.QWidget)

    class DeleteLabel(QtWidgets.QLabel):
        clicked = QtCore.Signal()

        def __init__(self, parent=None):
            super().__init__('✕', parent)
            self.setMargin(1)
            self.setObjectName('DeleteLabel')
            self.setStyleSheet(
                f"""#DeleteLabel {{
                    border-radius: 5px;
                    background: {self.palette().dark().color().name()};
                    min-width: 10px;
                    min-height: 10px;
                }}""")

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

    class Validator(QtGui.QValidator):
        def __init__(self, parent=None):
            super().__init__(parent)

        def validate(self, word: str, pos: int) -> QtGui.QValidator.State:
            if len(word) == 0:
                return QtGui.QValidator.Intermediate

            if not _tag_validation_regex.match(word):
                return QtGui.QValidator.Intermediate

            return QtGui.QValidator.Acceptable

    def __init__(self, text: str, parent):
        super().__init__(text, _Keyword.Validator(), parent)

        self.list_widget = parent

        self.delete_label = _Keyword.DeleteLabel()
        self.delete_label.clicked.connect(lambda: self.closed.emit(self))

        self.layout.addWidget(self.delete_label)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.setObjectName('OneKeyword')
        self.setStyleSheet(f"""#OneKeyword {{
                border-radius: 15px;
                background: {self.palette().mid().color().name()};
            }}""")

    def edit(self):
        super().edit()

        completer = QtWidgets.QCompleter(self.list_widget.completion_strings, parent=self)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)

        self.lineedit.setCompleter(completer)


class EditableKeywordListWidget(QtWidgets.QWidget):
    editingFinished = QtCore.Signal()

    def __init__(self, strings: list[str], completion_strings: list[str] = [], parent=None):
        super().__init__(parent)

        self.layout = FlowLayout()

        self.new_tag = QtWidgets.QToolButton()
        self.new_tag.setText('➕')
        self.new_tag.clicked.connect(lambda _: self._add_tag('', edit=True))
        self.layout.addWidget(self.new_tag)

        self.tags = []
        for text in strings:
            self._add_tag(text)

        self.completion_strings = set(completion_strings + strings)

        self.setLayout(self.layout)

    def _add_tag(self, text: str, edit=False):
        tag = _Keyword(text, self)
        self.tags += [tag]
        tag.editing_finished.connect(lambda x, _tag=tag: self._tag_text_updated(tag, x))
        tag.closed.connect(self._delete_tag)

        # insert before the new_tag-button
        self.layout.removeWidget(self.new_tag)
        self.layout.addWidget(tag)
        self.layout.addWidget(self.new_tag)

        if edit:
            self._request_edit(tag)

    def _update_tag_texts(self):
        self.editingFinished.emit()

    def _tag_text_updated(self, tag: _Keyword, text: str):
        if len(text) == 0:
            self._delete_tag(tag)
        else:
            self.completion_strings.add(text)
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

    def value(self) -> list[str]:
        return [tag.text for tag in self.tags if tag.text]
