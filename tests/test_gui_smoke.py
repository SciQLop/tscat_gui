"""Smoke tests for TSCatGUI widget."""
from tscat_gui import TSCatGUI
from tscat_gui.tscat_driver.driver import tscat_driver


def _unparent_driver():
    """Prevent widget cleanup from destroying the global driver singleton."""
    tscat_driver.setParent(None)


class TestTSCatGUISmoke:

    def test_instantiation(self, qtbot):
        """TSCatGUI should instantiate without crashing."""
        widget = TSCatGUI()
        qtbot.addWidget(widget)

        assert widget is not None
        assert widget.state is not None
        _unparent_driver()

    def test_has_views(self, qtbot):
        widget = TSCatGUI()
        qtbot.addWidget(widget)

        assert widget.events_view is not None
        assert widget.catalogues_view is not None
        assert widget.edit_view is not None
        _unparent_driver()

    def test_show_and_close(self, qtbot):
        widget = TSCatGUI()
        qtbot.addWidget(widget)

        widget.show()
        qtbot.waitExposed(widget)
        widget.close()
        _unparent_driver()
