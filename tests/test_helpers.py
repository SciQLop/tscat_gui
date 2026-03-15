import pytest
from PySide6 import QtCore, QtGui

from tscat_gui.utils.helper import (
    AttributeNameValidator,
    BoolDelegate,
    FloatDelegate,
    IntDelegate,
    StrDelegate,
)
from tscat_gui.model_base.constants import EntityRole, PathAttributeName, UUIDDataRole


class TestAttributeNameValidator:
    @pytest.fixture
    def validator(self):
        return AttributeNameValidator()

    @pytest.fixture
    def validator_with_reserved(self):
        return AttributeNameValidator(invalid_words=["uuid", "name"])

    @pytest.mark.parametrize("name", ["my_attr", "name123", "X", "abc_def_123"])
    def test_accepts_valid_names(self, validator, name):
        state = validator.validate(name, 0)
        assert state == QtGui.QValidator.Acceptable

    @pytest.mark.parametrize("name", ["1abc", "9_thing"])
    def test_rejects_names_starting_with_digit(self, validator, name):
        state = validator.validate(name, 0)
        assert state == QtGui.QValidator.Intermediate

    def test_rejects_empty_string(self, validator):
        state = validator.validate("", 0)
        assert state == QtGui.QValidator.Intermediate

    @pytest.mark.parametrize("name", ["hello world", "a-b", "x.y"])
    def test_rejects_invalid_characters(self, validator, name):
        state = validator.validate(name, 0)
        assert state == QtGui.QValidator.Intermediate

    def test_rejects_reserved_words(self, validator_with_reserved):
        assert validator_with_reserved.validate("uuid", 0) == QtGui.QValidator.Intermediate
        assert validator_with_reserved.validate("name", 0) == QtGui.QValidator.Intermediate

    def test_accepts_non_reserved_words(self, validator_with_reserved):
        assert validator_with_reserved.validate("other", 0) == QtGui.QValidator.Acceptable


class TestIntDelegate:
    def test_default_value(self, qtbot):
        w = IntDelegate()
        qtbot.addWidget(w)
        assert w.value() == 0

    def test_initial_value(self, qtbot):
        w = IntDelegate(value=42)
        qtbot.addWidget(w)
        assert w.value() == 42

    def test_set_value(self, qtbot):
        w = IntDelegate()
        qtbot.addWidget(w)
        w.set_value(99)
        assert w.value() == 99

    def test_none_defaults_to_zero(self, qtbot):
        w = IntDelegate(value=None)
        qtbot.addWidget(w)
        assert w.value() == 0

    def test_negative_value(self, qtbot):
        w = IntDelegate(value=-10)
        qtbot.addWidget(w)
        assert w.value() == -10


class TestFloatDelegate:
    def test_default_value(self, qtbot):
        w = FloatDelegate()
        qtbot.addWidget(w)
        assert w.value() == 0.0

    def test_initial_value(self, qtbot):
        w = FloatDelegate(value=3.14)
        qtbot.addWidget(w)
        assert w.value() == pytest.approx(3.14)

    def test_set_value(self, qtbot):
        w = FloatDelegate()
        qtbot.addWidget(w)
        w.set_value(2.718)
        assert w.value() == pytest.approx(2.718)

    def test_scientific_notation(self, qtbot):
        w = FloatDelegate(value=1.5e-3)
        qtbot.addWidget(w)
        assert w.value() == pytest.approx(0.0015)

    def test_has_scientific_notation_validator(self, qtbot):
        w = FloatDelegate()
        qtbot.addWidget(w)
        v = w.validator()
        assert isinstance(v, QtGui.QDoubleValidator)
        assert v.notation() == QtGui.QDoubleValidator.Notation.ScientificNotation


class TestStrDelegate:
    def test_default_value(self, qtbot):
        w = StrDelegate()
        qtbot.addWidget(w)
        assert w.value() == ""

    def test_initial_value(self, qtbot):
        w = StrDelegate(value="hello")
        qtbot.addWidget(w)
        assert w.value() == "hello"

    def test_set_value(self, qtbot):
        w = StrDelegate()
        qtbot.addWidget(w)
        w.set_value("world")
        assert w.value() == "world"

    def test_accepts_any_string(self, qtbot):
        w = StrDelegate(value="special chars: !@#$%^&*()")
        qtbot.addWidget(w)
        assert w.value() == "special chars: !@#$%^&*()"


class TestBoolDelegate:
    def test_default_false(self, qtbot):
        w = BoolDelegate()
        qtbot.addWidget(w)
        assert w.value() is False

    def test_initial_true(self, qtbot):
        w = BoolDelegate(value=True)
        qtbot.addWidget(w)
        assert w.value() is True

    def test_set_value(self, qtbot):
        w = BoolDelegate()
        qtbot.addWidget(w)
        w.set_value(True)
        assert w.value() is True
        w.set_value(False)
        assert w.value() is False

    def test_emits_editing_finished_on_toggle(self, qtbot):
        w = BoolDelegate(value=False)
        qtbot.addWidget(w)
        with qtbot.waitSignal(w.editingFinished, timeout=1000):
            w.setChecked(True)


class TestConstants:
    def test_uuid_data_role_is_custom_role(self):
        assert UUIDDataRole == QtCore.Qt.UserRole + 1

    def test_entity_role_is_custom_role(self):
        assert EntityRole == QtCore.Qt.UserRole + 2

    def test_path_attribute_name(self):
        assert PathAttributeName == "path__"
        assert isinstance(PathAttributeName, str)
