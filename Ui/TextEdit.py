#!/usr/bin/python3
# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtGui, QtWidgets


class MyTextEdit(QtWidgets.QPlainTextEdit):
    def __init__(self, obj):
        super().__init__(obj)
        self.key_pressed_cache = bytearray()

    signal_key = QtCore.pyqtSignal(bytearray)
    
    def keyPressEvent(self, event):
        if type(event) != QtGui.QKeyEvent:
            return super().keyPressEvent(event)

        try:
            #print(event.text())
            self.key_pressed_cache.append(ord(event.text()))
            if event.text() == "\r":
                self.signal_key.emit(self.key_pressed_cache)
                self.key_pressed_cache = bytearray()
        except Exception as e:
            if event.key() == QtCore.Qt.Key_Question:
                self.key_pressed_cache.append(0x3F)

        return super().keyPressEvent(event)

    '''
    def mousePressEvent(self, QMouseEvent):
        pass
    '''
