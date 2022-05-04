#!/usr/bin/env python3

from PySide2 import QtWidgets

import sys
import logging

from tscat_gui import TSCatGUI
from tscat_gui.logger import log

if __name__ == "__main__":
    # QtWidgets.QApplication.setDesktopSettingsAware(False)  # defaulting to light mode

    logging.basicConfig(level=logging.DEBUG)
    log.setLevel(logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)

    main = QtWidgets.QMainWindow()

    w = TSCatGUI(main)

    main.setCentralWidget(w)

    #     styles = """
    # QTreeView::!active { selection-background-color: gray;}
    # """
    #     main.setStyleSheet(styles)

    main.show()

    sys.exit(app.exec_())
