#!/usr/bin/env python
# Copyright (c) 2007-9 Qtrac Ltd. All rights reserved.
# This program or module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 2 of the License, or
# version 3 of the License, or (at your option) any later version. It is
# provided for educational purposes and is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
# the GNU General Public License for more details.

import os
import platform
import stat
import sys
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

__version__ = "1.1.2"


class Form(QMainWindow):

    def __init__(self):
        super(Form, self).__init__(None)

        pathLabel = QLabel("Path:")
        settings = QSettings()

        path = os.getcwd()

        self.pathLabel = QLabel(path)
        self.pathLabel.setFrameStyle(QFrame.StyledPanel|QFrame.Sunken)
        self.pathButton = QPushButton("&Path...")
        self.recurseCheckBox = QCheckBox("&Recurse")
        self.transCheckBox = QCheckBox("&Translate")
        self.debugCheckBox = QCheckBox("&Dry Run")
        self.logBrowser = QTextBrowser()
        self.logBrowser.setLineWrapMode(QTextEdit.NoWrap)

        self.buttonBox = QDialogButtonBox()
        self.buildButton = self.buttonBox.addButton("&Build", QDialogButtonBox.ActionRole)
        self.cleanButton = self.buttonBox.addButton("&Clean", QDialogButtonBox.ActionRole)
        quitButton = self.buttonBox.addButton("&Quit", QDialogButtonBox.RejectRole)

        topLayout = QHBoxLayout()
        topLayout.addWidget(pathLabel)
        topLayout.addWidget(self.pathLabel, 1)
        topLayout.addWidget(self.pathButton)
        bottomLayout = QHBoxLayout()
        bottomLayout.addWidget(self.recurseCheckBox)
        bottomLayout.addWidget(self.transCheckBox)
        bottomLayout.addWidget(self.debugCheckBox)
        bottomLayout.addStretch()
        bottomLayout.addWidget(self.buttonBox)
        layout = QVBoxLayout()
        layout.addLayout(topLayout)
        layout.addWidget(self.logBrowser)
        layout.addLayout(bottomLayout)
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        self.pathButton.clicked.connect(self.setPath)
        self.buildButton.clicked.connect(self.build)
        self.cleanButton.clicked.connect(self.clean)
        quitButton.clicked.connect(self.close)

        self.setWindowTitle("Make PyQt")

    def setPath(self):
        path = QFileDialog.getExistingDirectory(self, "Make PyQt - Set Path", self.pathLabel.text())
        if path:
            self.pathLabel.setText(QDir.toNativeSeparators(path))

    def build(self):
        self.updateUi(False)
        self.logBrowser.clear()
        recurse = self.recurseCheckBox.isChecked()
        path = str(self.pathLabel.text())
        self._apply(recurse, self._build, path)
        if self.transCheckBox.isChecked():
            self._apply(recurse, self._translate, path)
        self.updateUi(True)

    def clean(self):
        self.updateUi(False)
        self.logBrowser.clear()
        recurse = self.recurseCheckBox.isChecked()
        path = str(self.pathLabel.text())
        self._apply(recurse, self._clean, path)
        self.updateUi(True)

    def updateUi(self, enable):
        for widget in (self.buildButton, self.cleanButton,
                self.pathButton, self.recurseCheckBox,
                self.transCheckBox, self.debugCheckBox):
            widget.setEnabled(enable)
        if not enable:
            QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()
            self.buildButton.setFocus()

    def _apply(self, recurse, function, path):
        if not recurse:
            function(path)
        else:
            for root, dirs, files in os.walk(path):
                for dir in sorted(dirs):
                    function(os.path.join(root, dir))

    def _make_error_message(self, command, process):
        err = ""
        ba = process.readAllStandardError()
        if not ba.isEmpty():
            err = ": " + str(QString(ba))
        return "<font color=red>FAILED: %s%s</font>" % (command, err)

    def _build(self, path):
        settings = QSettings()
        pyuic5 = PYUIC5
        pyrcc5 = PYRCC5
        prefix = str(self.pathLabel.text())
        if not prefix.endswith(os.sep):
            prefix += os.sep
        failed = 0
        process = QProcess()
        for name in os.listdir(path):
            source = os.path.join(path, name)
            target = None
            if source.endswith(".ui"):
                target = os.path.join(path,
                                    "ui_" + name.replace(".ui", ".py"))
                command = pyuic5
            elif source.endswith(".qrc"):
                #target = os.path.join(path,
                #                    "qrc_" + name.replace(".qrc", ".py"))
                target = os.path.join(path, name.replace(".qrc", "_rc.py"))
                command = pyrcc5
            if target is not None:
                if not os.access(target, os.F_OK) or (
                   os.stat(source)[stat.ST_MTIME] > \
                   os.stat(target)[stat.ST_MTIME]):
                    args = ["-o", target, source]
                    msg = "converted <font color=darkblue>" + source + \
                          "</font> to <font color=blue>" + target + \
                          "</font>"
                    if self.debugCheckBox.isChecked():
                        msg = "<font color=green># " + msg + "</font>"
                    else:
                        process.start(command, args)
                        if (not process.waitForFinished(2 * 60 * 1000) or
                            not QFile.exists(target)):
                            msg = self._make_error_message(command,
                                                           process)
                            failed += 1
                    self.logBrowser.append(msg.replace(prefix, ""))
                else:
                    self.logBrowser.append("<font color=green>"
                            "# %s is up-to-date</font>" % \
                            source.replace(prefix, ""))
                QApplication.processEvents()
        if failed:
            QMessageBox.information(self, "Make PyQt - Failures",
                    "Try manually setting the paths to the tools "
                    "using <b>More-&gt;Tool paths</b>")


    def _clean(self, path):
        prefix = str(self.pathLabel.text())
        if not prefix.endswith(os.sep):
            prefix += os.sep
        deletelist = []
        for name in os.listdir(path):
            target = os.path.join(path, name)
            source = None
            if target.endswith(".py") or target.endswith(".pyc") or \
               target.endswith(".pyo"):
                if name.startswith("ui_") and not name[-1] in "oc":
                    source = os.path.join(path, name[3:-3] + ".ui")
                elif name.startswith("qrc_"):
                    if target[-1] in "oc":
                        source = os.path.join(path, name[5:-5] + ".qrc")
                    else:
                        source = os.path.join(path, name[5:-3] + ".qrc")
                elif target[-1] in "oc":
                    source = target[:-1]
                if source is not None:
                    if os.access(source, os.F_OK):
                        if self.debugCheckBox.isChecked():
                            self.logBrowser.append("<font color=green>"
                                    "# delete %s</font>" % \
                                    target.replace(prefix, ""))
                        else:
                            deletelist.append(target)
                    else:
                        self.logBrowser.append("<font color=darkred>"
                                "will not remove "
                                "'%s' since `%s' not found</font>" % (
                                target.replace(prefix, ""),
                                source.replace(prefix, "")))
        if not self.debugCheckBox.isChecked():
            for target in deletelist:
                self.logBrowser.append("deleted "
                        "<font color=red>%s</font>" % \
                        target.replace(prefix, ""))
                os.remove(target)
                QApplication.processEvents()


    def _translate(self, path):
        prefix = str(self.pathLabel.text())
        if not prefix.endswith(os.sep):
            prefix += os.sep
        files = []
        tsfiles = []
        for name in os.listdir(path):
            if name.endswith((".py", ".pyw")):
                files.append(os.path.join(path, name))
            elif name.endswith(".ts"):
                tsfiles.append(os.path.join(path, name))
        if not tsfiles:
            return
        settings = QSettings()
        pylupdate5 = str(settings.value("pylupdate5",
                             QVariant(PYLUPDATE5)).toString())
        lrelease = str(settings.value("lrelease",
                           QVariant(LRELEASE)).toString())
        process = QProcess()
        failed = 0
        for ts in tsfiles:
            qm = ts[:-3] + ".qm"
            command1 = pylupdate5
            args1 = files + ["-ts", ts]
            command2 = lrelease
            args2 = ["-silent", ts, "-qm", qm]
            msg = "updated <font color=blue>%s</font>" % \
                    ts.replace(prefix, "")
            if self.debugCheckBox.isChecked():
                msg = "<font color=green># %s</font>" % msg
            else:
                process.start(command1, args1)
                if not process.waitForFinished(2 * 60 * 1000):
                    msg = self._make_error_message(command1, process)
                    failed += 1
            self.logBrowser.append(msg)
            msg = "generated <font color=blue>%s</font>" % \
                    qm.replace(prefix, "")
            if self.debugCheckBox.isChecked():
                msg = "<font color=green># %s</font>" % msg
            else:
                process.start(command2, args2)
                if not process.waitForFinished(2 * 60 * 1000):
                    msg = self._make_error_message(command2, process)
                    failed += 1
            self.logBrowser.append(msg)
            QApplication.processEvents()
        if failed:
            QMessageBox.information(self, "Make PyQt - Failures",
                    "Try manually setting the paths to the tools "
                    "using <b>More-&gt;Tool paths</b>")


app = QApplication(sys.argv)
PATH = app.applicationDirPath()
if sys.platform.startswith("win"):
    PATH = os.path.join(os.path.dirname(sys.executable),
                        "Lib/site-packages/PyQt5")
PYUIC5 = os.path.join(PATH, "pyuic5")
PYRCC5 = os.path.join(PATH, "pyrcc5")
PYLUPDATE5 = os.path.join(PATH, "pylupdate5")
LRELEASE = "lrelease"
if sys.platform.startswith("win"):
    PYUIC5 = PYUIC5.replace("/", "\\") + ".bat"
    PYRCC5 = PYRCC5.replace("/", "\\") + ".exe"
    PYLUPDATE5 = PYLUPDATE5.replace("/", "\\") + ".exe"
app.setOrganizationName("Qtrac Ltd.")
app.setOrganizationDomain("qtrac.eu")
app.setApplicationName("Make PyQt")
form = Form()
form.show()
app.exec_()

# 1.0.1 Fixed bug reported by Brian Downing where paths that contained
#       spaces were not handled correctly.
# 1.0.2 Fixed bug reported by Ben Thompson that if the UIC program
#       fails, no problem was reported; I try to report one now.
# 1.1.0 Added Remember path option; if checked the program starts with
#       the last used path, otherwise with the current directory, unless
#       overridden on the command line
# 1.1.1 Changed default path on Windows to match PyQt 5.5
# 1.1.2 Added stderr to error message output as per Michael Jackson's
#       suggestion
