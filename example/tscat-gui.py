#!/usr/bin/env python3

from PySide2 import QtWidgets

import sys

from tscat_gui import TSCatGUI

if __name__ == "__main__":
    # QtWidgets.QApplication.setDesktopSettingsAware(False)  # defaulting to light mode

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
