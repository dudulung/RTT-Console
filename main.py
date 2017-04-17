#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os, sys
import ui_MainWindow
from PyQt5.QtWidgets import QApplication, QMainWindow, QFontDialog, QFileDialog, QMessageBox
from PyQt5 import QtCore, QtGui
import struct
import threading, time
import configparser
import jlink_lib
from kfifo import *

COTEX_RAM_BASE = 0x20000000
RTT_TAG        = "SEGGER RTT"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = ui_MainWindow.Ui_MainWindow()
        self.ui.setupUi(self)
        self.action_init()
        self.jlink   = None
        self.RTT_addr = None
        self.aUp     = None
        self.aDown   = None
        self.dllpath = None
        self.closed  = False
        self.init_setting()
        threading.Thread(target=self.serial_recv).start()

    def action_init(self):
        self.ui.actionStart.triggered.connect(self.on_btn_start_clicked)
        self.ui.actionFont.triggered.connect(self.on_btn_font_clicked)
        self.ui.actionClear.triggered.connect(self.on_btn_clear_clicked)
        self.ui.actionDll.triggered.connect(self.on_btn_dll_clicked)
        self.ui.plainTextEdit.signal_key.connect(self.on_text_edit_key_pressed)

    def init_setting(self):
        if not os.path.exists('setting.ini'):
            open('setting.ini', 'w')

        self.conf = configparser.ConfigParser()
        self.conf.read('setting.ini')

        if not self.conf.has_section('globals'):
            self.conf.add_section('globals')
            #self.conf.set('globals', 'dllpath', JLINK_DLL_PATH)
        try:
            self.dllpath = self.conf.get('globals', 'dllpath')
        except configparser.NoOptionError as e:
            self.dllpath = None

    def get_RTT_addr(self):
        data = self.jlink.read(COTEX_RAM_BASE, 0x80)
        addr = data.find(RTT_TAG.encode())
        if addr == -1:
            return COTEX_RAM_BASE
        return COTEX_RAM_BASE + addr

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

    def on_btn_dll_clicked(self):
        fname, ftype = QFileDialog.getOpenFileName(self, u"请选择JLinkARM.dll", ".", "DLL Files(*.dll)")
        if fname: self.dllpath = fname

    def on_btn_start_clicked(self):
        if self.ui.actionStart.text() == u'Start':
            try:
                self.jlink = jlink_lib.Jlink(self.dllpath)
                self.jlink.set_mode(jlink_lib.JLINK_MODE_SWD)
                self.jlink.set_speed(4000)
                self.RTT_addr = self.get_RTT_addr()
                self.setup_ring_buffer()
                self.ui.statusbar.showMessage(u"开启监控成功！！！")
                self.ui.actionStart.setText(u'Stop')
                self.dllpath = self.jlink.get_dll_path()
            except jlink_lib.JlinkError as e:
                QMessageBox.critical(self, u"错误", u"未找到JLinkARM.dll,请手动选择该文件路径后重试！")
                self.on_btn_dll_clicked()
            except Exception as e:
                print(e)
                self.ui.statusbar.showMessage(u"开启监控失败！！！")
        else:
            self.ui.actionStart.setText(u'Start')
            time.sleep(0.1)
            self.jlink.close()
            self.ui.statusbar.showMessage(u"关闭监控成功！！！")

    def update_ring_buffer(self):
        self.aUp.WrOff   = self.jlink.read_32(self.RTT_addr + 16 + (4 * 5) * 0 + 0)
        self.aDown.RdOff = self.jlink.read_32(self.RTT_addr + 16 + (4 * 5) * 1 + 4)

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
        if len(self.ui.plainTextEdit.toPlainText()) > 25000:
            self.ui.plainTextEdit.clear()
        self.ui.plainTextEdit.moveCursor(QtGui.QTextCursor.End)
        self.ui.plainTextEdit.insertPlainText(bytesUp.decode())
        self.ui.plainTextEdit.moveCursor(QtGui.QTextCursor.End)

    def closeEvent(self, evt):
        self.closed = True
        time.sleep(0.1)
        if self.dllpath is not None:
            self.conf.set('globals', 'dllpath', self.dllpath)
        self.conf.write(open('setting.ini', 'w'))

        if self.jlink and self.jlink.is_open():
            self.jlink.close()

if __name__ == '__main__':
    app = QApplication(sys.argv)

    w = MainWindow()
    w.show()

    sys.exit(app.exec_())
