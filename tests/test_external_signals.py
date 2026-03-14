"""Tests for external signal emission."""
import datetime as dt


from tscat_gui.tscat_driver.actions import (
    DeleteAttributeAction,
    SetAttributeAction,
)
from tscat_gui.tscat_driver.driver import tscat_driver


def _unparent_driver():
    """Prevent widget cleanup from destroying the global driver singleton."""
    tscat_driver.setParent(None)


class TestExternalSignalEmission:
    """Bug #7: action.entities[0] crashes with empty entities list."""

    def test_empty_entities_no_crash(self, qtbot):
        """SetAttributeAction with empty entities should not crash the signal handler."""
        from tscat_gui import TSCatGUI

        widget = TSCatGUI()
        qtbot.addWidget(widget)

        action = SetAttributeAction(None, [], 'name', [])
        action.entities = []
        action.completed = True

        widget._external_signal_emission_changed(action)
        _unparent_driver()

    def test_delete_attribute_empty_entities_no_crash(self, qtbot):
        """DeleteAttributeAction with empty entities should not crash."""
        from tscat_gui import TSCatGUI

        widget = TSCatGUI()
        qtbot.addWidget(widget)

        action = DeleteAttributeAction(None, [], 'name')
        action.entities = []
        action.completed = True

        widget._external_signal_emission_changed(action)
        _unparent_driver()

    def test_catalogue_change_emits_signal(self, qtbot):
        from tscat import create_catalogue
        from tscat_gui import TSCatGUI

        widget = TSCatGUI()
        qtbot.addWidget(widget)

        cat = create_catalogue(name='Test', author='test')
        action = SetAttributeAction(None, [cat.uuid], 'name', ['Updated'])
        action.entities = [cat]
        action.completed = True

        received = []
        widget.catalogues_changed.connect(lambda uuids: received.append(uuids))

        widget._external_signal_emission_changed(action)
        assert len(received) == 1
        assert cat.uuid in received[0]
        _unparent_driver()

    def test_event_change_emits_signal(self, qtbot):
        from tscat import create_event
        from tscat_gui import TSCatGUI

        widget = TSCatGUI()
        qtbot.addWidget(widget)

        evt = create_event(start=dt.datetime.now(), stop=dt.datetime.now(), author='test')
        action = SetAttributeAction(None, [evt.uuid], 'author', ['new_author'])
        action.entities = [evt]
        action.completed = True

        received = []
        widget.events_changed.connect(lambda uuids: received.append(uuids))

        widget._external_signal_emission_changed(action)
        assert len(received) == 1
        _unparent_driver()
