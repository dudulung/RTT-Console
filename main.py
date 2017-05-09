#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys
from Ui import ui_MainWindow
from PyQt5.QtWidgets import QApplication, QMainWindow, QFontDialog, QFileDialog, QMessageBox
from PyQt5 import QtCore, QtGui, QtWidgets
import struct
import threading, time
import jlink
from kfifo import *

COTEX_RAM_BASE = 0x20000000
RTT_TAG        = "SEGGER RTT"

if getattr(sys, 'frozen', False): # we are running in a |PyInstaller| bundle
    basedir = sys._MEIPASS
else: # we are running in a normal Python environment
    basedir = os.path.dirname(__file__)

jlinkdllpath = os.path.join(basedir, "JLink_x64.dll")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.uiInit()
        self.action_init()
        self.jlink   = None
        self.RTT_addr = None
        self.aUp     = None
        self.aDown   = None
        self.closed  = False
        threading.Thread(target=self.serial_recv).start()

    def uiInit(self):
        self.ui = ui_MainWindow.Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.plainTextEdit.document().setMaximumBlockCount(1000)

        self.lineLbl = QtWidgets.QLabel()
        self.lineLbl.setToolTip(u"行数")
        self.lineLbl.setText("0")
        self.ui.statusbar.addPermanentWidget(self.lineLbl)

    def action_init(self):
        self.ui.actionStart.triggered.connect(self.on_btn_start_clicked)
        self.ui.actionFont.triggered.connect(self.on_btn_font_clicked)
        self.ui.actionClear.triggered.connect(self.on_btn_clear_clicked)
        self.ui.actionSave.triggered.connect(self.onBtnSaveClicked)
        self.ui.actionAbout.triggered.connect(self.about)
        self.ui.plainTextEdit.signal_key.connect(self.on_text_edit_key_pressed)

    def about(self):
        QMessageBox.about(self, "About Console",
                          "Version 1.1 build at 20170419<br/>"
                          "Copyright @ dudulung<br/>")

    def get_RTT_addr(self):
        idx = 0
        while idx < (20*1024):
            data = self.jlink.read(COTEX_RAM_BASE + idx, 0x80)
            addr = data.find(RTT_TAG.encode())
            if addr >= 0:
                return COTEX_RAM_BASE + idx + addr
            idx += 0x80-16
        return COTEX_RAM_BASE

    def mem_read(self, addr, data_len):
        return self.jlink.read(addr, data_len)

    def mem_write(self, addr, data):
        self.jlink.write(addr, data)

    def setup_ring_buffer(self):
        """
        struct __kfifo
        {
            unsigned int	in;
            unsigned int	out;
            unsigned int	mask;
            unsigned int	esize;
            void		*data;
        };
        typedef struct
        {
            char   acID[16];                                                       
            struct __kfifo fifo_up;
            struct __kfifo fifo_down;
            uint8_t mode_up;
            uint8_t mode_down; 
        } SEGGER_RTT_CB;
        """
        LEN = (4 * 5) * 2
        data = self.jlink.read(self.RTT_addr + 16, LEN)
        arr = struct.unpack('10L', data)
        self.aUp   = RingBuffer(self.mem_read, self.mem_write, arr[0:5])
        self.aDown = RingBuffer(self.mem_read, self.mem_write, arr[5:10])

    def on_btn_font_clicked(self):
        font, ok = QFontDialog.getFont(self)
        if ok:
            self.ui.plainTextEdit.setFont(font)

    def on_btn_clear_clicked(self):
        self.ui.plainTextEdit.clear()
        self.lineLbl.setText("0")

    def onBtnSaveClicked(self):
        fname, ftype = QFileDialog.getSaveFileName(self, u"请选择保存文件", ".", "LOG Files(*.log)")
        if fname:
            with open(fname, 'w') as logfile:
                logfile.write(str(self.ui.plainTextEdit.toPlainText()))

    def on_btn_start_clicked(self):
        if self.ui.actionStart.text() == u'Start':
            try:
                self.jlink = jlink.Jlink(jlinkdllpath)
                self.jlink.get_hardware_verion()
                self.jlink.set_mode(jlink.JLINK_MODE_SWD)
                self.jlink.set_speed(4000)
                self.RTT_addr = self.get_RTT_addr()
                self.setup_ring_buffer()
                self.ui.statusbar.showMessage(u"开启监控成功")
                self.ui.actionStart.setText(u'Stop')
            except jlink.JlinkError as e:
                QMessageBox.critical(self, u"错误", u"'{}'.".format(e))
                #self.on_btn_dll_clicked()
                del self.jlink
                self.jlink = None
            except Exception as e:
                print(e)
                self.ui.statusbar.showMessage(u"开启监控失败")
        else:
            self.ui.actionStart.setText(u'Start')
            time.sleep(0.1)
            self.jlink.close()
            del self.jlink
            self.jlink = None
            self.ui.statusbar.showMessage(u"关闭监控成功")

    def update_ring_buffer(self):
        self.aUp.WrOff   = self.jlink.read_32(self.RTT_addr + 16 + (4 * 5) * 0 + 4 * 0)
        self.aUp.RdOff   = self.jlink.read_32(self.RTT_addr + 16 + (4 * 5) * 0 + 4 * 1)
        self.aUp.pBuffer = self.jlink.read_32(self.RTT_addr + 16 + (4 * 5) * 0 + 4 * 4)
        self.aDown.RdOff = self.jlink.read_32(self.RTT_addr + 16 + (4 * 5) * 1 + 4 * 1)

    def chn_down_full(self):
        return self.aDown.fifo_full()

    def chn_up_empty(self):
        return self.aUp.fifo_empty()

    def chn_up_read(self):
        len = self.aUp.fifo_len()
        b   = self.aUp.fifo_out(len)
        self.jlink.write_32(self.RTT_addr + 16 + (4 * 5) * 0 + 4, self.aUp.RdOff)
        return b

    def on_text_edit_key_pressed(self, keyarr):
        # do not response key event while jlink closed
        if self.jlink is None or not self.jlink.is_open():
            self.ui.statusbar.showMessage(u"请点击start开启监控")
            return

        if not self.aDown.fifo_full():
            #print(keyarr)
            self.aDown.fifo_in(bytes(keyarr))
            self.jlink.write_32(self.RTT_addr + 16 + (4 * 5) * 1 + 0, self.aDown.WrOff)

    received = QtCore.pyqtSignal(bytearray)
    def serial_recv(self):
        self.received.connect(self.on_received)

        while not self.closed:
            if self.ui.actionStart.text() == u'Stop':
                self.update_ring_buffer()
                if not self.chn_up_empty():
                    self.received.emit(self.chn_up_read())

            time.sleep(0.01)

    def on_received(self, bytesUp):
        try:
            self.ui.plainTextEdit.moveCursor(QtGui.QTextCursor.End)
            self.ui.plainTextEdit.insertPlainText(bytesUp.decode())
            self.ui.plainTextEdit.moveCursor(QtGui.QTextCursor.End)
            self.lineLbl.setText(str(self.ui.plainTextEdit.document().lineCount()))
        except Exception as e:
            QMessageBox.critical(self, u"错误", str(e))

    def closeEvent(self, evt):
        self.closed = True
        time.sleep(0.1)
        if self.jlink and self.jlink.is_open():
            self.jlink.close()

if __name__ == '__main__':
    app = QApplication(sys.argv)

    w = MainWindow()
    w.show()

    sys.exit(app.exec_())
