#!/usr/bin/python3
# -*- coding: utf-8 -*-

import fnmatch
import os, sys
import ctypes
import codecs
import enum

_DEFAULT_JLINK_SPEED_KHZ = 4000
JLINK_MODE_JTAG = 0
JLINK_MODE_SWD  = 1

if sys.platform.lower().startswith('win'):
    _DEFAULT_SEGGER_ROOT_PATH = r'C:\Program Files (x86)\SEGGER' if 'PROGRAMFILES(X86)' in os.environ else r'C:\Program Files\SEGGER'
elif sys.platform.lower().startswith('linux'):
    _DEFAULT_SEGGER_ROOT_PATH = r'/opt/SEGGER/JLink'
elif sys.platform.lower().startswith('dar'):
    _DEFAULT_SEGGER_ROOT_PATH = r'/Applications/SEGGER/JLink'


def find_latest_dll():

    if not os.path.isdir(_DEFAULT_SEGGER_ROOT_PATH):
        return None

    if sys.platform.lower().startswith('win'):
        jlink_sw_dirs = sorted([f for f in os.listdir(_DEFAULT_SEGGER_ROOT_PATH) if fnmatch.fnmatch(f, 'JLink_V*')])
        if sys.maxsize > 2**32:
            jlinkdll = os.path.join('bin_x64', 'JLink_x64.dll')
        else:
            jlinkdll = 'JLinkARM.dll'
        return os.path.join(_DEFAULT_SEGGER_ROOT_PATH, jlink_sw_dirs[-1], jlinkdll)

    elif sys.platform.lower().startswith('linux'):
        # Adding .dummy to filenames in linux (.so.x.x.x.dummy) because python compare strings will then work properly with the version number compare.
        jlink_so_files = sorted([f + ".dummy" for f in os.listdir(_DEFAULT_SEGGER_ROOT_PATH) if fnmatch.fnmatch(f, 'libjlinkarm.so*')])
        return os.path.join(_DEFAULT_SEGGER_ROOT_PATH, jlink_so_files[-1][:-len(".dummy")])

    elif sys.platform.lower().startswith('dar'):
        jlink_dylib_files = sorted([f for f in os.listdir(_DEFAULT_SEGGER_ROOT_PATH) if fnmatch.fnmatch(f, 'libjlinkarm.*dylib')])
        return os.path.join(_DEFAULT_SEGGER_ROOT_PATH, jlink_dylib_files[-1])

@enum.unique
class CpuRegister(enum.IntEnum):
    """
    Wraps cpu_registers_t values from DllCommonDefinitions.h
    """
    R0                        = 0
    R1                        = 1
    R2                        = 2
    R3                        = 3
    R4                        = 4
    R5                        = 5
    R6                        = 6
    R7                        = 7
    R8                        = 8
    R9                        = 9
    R10                       = 10
    R11                       = 11
    R12                       = 12
    R13                       = 13
    R14                       = 14
    R15                       = 15
    XPSR                      = 16
    MSP                       = 17
    PSP                       = 18


class JlinkError(Exception):
    """
    jlink DLL exception class, inherits from the built-in Exception class.
    """

    def __init__(self, err_code=None):
        """
        Constructs a new object and sets the err_code.
        @param int err_code: The error code returned by the jlink DLL.
        """
        """
        self.err_code = err_code
        if self.err_code in [member.value for name, member in NrfjprogdllErr.__members__.items()]:
            err_str = 'An error was reported by NRFJPROG DLL: {} {}.'.format(self.err_code, NrfjprogdllErr(self.err_code).name)
        else:
            err_str = 'An error was reported by NRFJPROG DLL: {}.'.format(self.err_code)

        Exception.__init__(self, err_str)
        """
        pass


class Jlink(object):
    def __init__(self, dllpath=None):
        self.jlink = None

        if dllpath and not isinstance(dllpath, str):
            raise ValueError("Parameter jlink_arm_dll_path must be a string.")

        if dllpath is None:
            dllpath = find_latest_dll()
            if dllpath is None:
                raise JlinkError("Could not locate a JLinkARM.dll in the default SEGGER installation path.")

        self.dllpath = os.path.abspath(dllpath)
        if os.path.exists(self.dllpath):
            try:
                self.jlink = ctypes.cdll.LoadLibrary(self.dllpath)
            except Exception as e:
                raise JlinkError("Could not load the JLINK DLL: '{}'.".format(e))
        else:
            raise JlinkError("Could not load JLinkARM.dll.")

    def get_dll_path(self):
        return self.dllpath

    def dll_version(self):
        """
        Returns the JLinkARM.dll version.
        @return (int, int, str): Tuple containing the major, minor and revision of the dll.
        """
        v = self.jlink.JLINKARM_GetDLLVersion()
        major = int(v / 10000)
        v -= major * 10000
        minor = int(v / 100)
        v -= minor * 100
        revision = int(v)
        return major, minor, chr(revision)

    def set_mode(self, mode=JLINK_MODE_SWD):
        self.jlink.JLINKARM_TIF_Select(mode)

    def is_open(self):
        """
        Checks if the JLinkARM.dll is open.
        @return bool: True if open.
        """
        return self.jlink.JLINKARM_IsOpen()

    def open(self):
        """
        Opens the JLinkARM.dll.
        """
        self.jlink.JLINKARM_Open()

    def close(self):
        """
        Closes and frees the JLinkARM DLL.
        """
        self.jlink.JLINKARM_Close()

    def reset(self):
        """
        system reset.
        """
        self.jlink.JLINKARM_Reset()

    def go(self):
        """
        Starts the device CPU .
        """
        #void JLINKARM_Go()
        self.jlink.JLINKARM_Go()

    def halt(self):
        """
        Halts the device CPU.
        """
        #bool JLINKARM_Halt()
        self.jlink.JLINKARM_Halt()

    def step(self):
        """
        Runs the device CPU for one instruction.
        """
        #bool JLINKARM_Step()
        self.jlink.JLINKARM_Step()

    def clear_error(self):
        #void JLINKARM_ClrError()
        self.jlink.JLINKARM_ClrError()

    def set_speed(self, speed=_DEFAULT_JLINK_SPEED_KHZ):
        """
        set the speed.
        @speed int: speed.
        """
        if not self._is_u32(speed):
            raise ValueError('The speed parameter must be an unsigned 32-bit value.')
        self.jlink.JLINKARM_SetSpeed(speed)

    def set_max_speed(self):
        """
        set the max speed.
        """
        self.jlink.JLINKARM_SetMaxSpeed()

    def get_speed(self):
        """
        Returns the speed.
        @return int: speed.
        """
        return self.jlink.JLINKARM_GetSpeed()

    def get_voltage(self):
        """
        Returns the target voltage.
        @return int: voltage.
        """
        return self.jlink.JLINKARM_GetVoltage()

    def is_halted(self):
        """
        Checks if the device CPU is halted.
        @return boolean: True if halted.
        """
        return self.jlink.JLINKARM_IsHalted()

    def is_connected(self):
        """
        Checks if the target is connected.
        @return bool: True if connected.
        """
        return self.jlink.JLINKARM_IsConnected()

    def clear_break_point(self, idx):
        #void JLINKARM_ClrBP(UInt32 index)
        self.jlink.JLINKARM_ClrBP(idx)

    def set_break_point(self, idx, addr):
        #void JLINKARM_SetBP(UInt32 index, UInt32 addr)
        self.jlink.JLINKARM_SetBP(idx, addr)

    def set_register(self, register_name, value):
        """
        Writes a CPU register.
        @param int, str, or CPURegister(IntEnum) register_name: CPU register to write.
        @param int value: Value to write.
        """
        if not self._is_u32(value):
            raise ValueError('The value parameter must be an unsigned 32-bit value.')

        if not self._is_enum(register_name, CpuRegister):
            raise ValueError('Parameter register_name must be of type int, str or CpuRegister enumeration.')

        register_name = self._decode_enum(register_name, CpuRegister)
        if register_name is None:
            raise ValueError('Parameter register_name must be of type int, str or CpuRegister enumeration.')

        register_name = ctypes.c_int(register_name.value)
        value = ctypes.c_uint32(value)
        self.jlink.JLINKARM_WriteReg(register_name, value)

    def get_register(self, register_name):
        """
        Reads a CPU register.
        @param  int, str, or CPURegister(IntEnum) register_name: CPU register to read.
        @return int: Value read.
        """
        if not self._is_enum(register_name, CpuRegister):
            raise ValueError('Parameter register_name must be of type int, str or CpuRegister enumeration.')

        register_name = self._decode_enum(register_name, CpuRegister)
        if register_name is None:
            raise ValueError('Parameter register_name must be of type int, str or CpuRegister enumeration.')

        register_name = ctypes.c_int(register_name.value)
        #value = ctypes.c_uint32()
        return self.jlink.JLINKARM_ReadReg(register_name)

    def write(self, addr, data):
        """
        Writes data from the array into the device starting at the given address.
        @param int addr: Start address of the memory block to write.
        @param sequence data: Data to write. Any type that implements the sequence API (i.e. string, list, bytearray...) is valid as input.
        """
        if not self._is_u32(addr):
            raise ValueError('The addr parameter must be an unsigned 32-bit value.')

        if not self._is_valid_buf(data):
            raise ValueError('The data parameter must be a sequence type with at least one item.')

        addr = ctypes.c_uint32(addr)
        data_len = ctypes.c_uint32(len(data))
        data = (ctypes.c_uint8 * data_len.value)(*data)
        self.jlink.JLINKARM_WriteMem(addr, data_len, ctypes.byref(data))

    def read(self, addr, data_len):
        """
        Reads data_len bytes from the device starting at the given address.
        @param int addr: Start address of the memory block to read.
        @param int data_len: Number of bytes to read.
        @return [int]: List of values read.
        """
        if not self._is_u32(addr):
            raise ValueError('The addr parameter must be an unsigned 32-bit value.')

        if not self._is_u32(data_len):
            raise ValueError('The data_len parameter must be an unsigned 32-bit value.')

        addr = ctypes.c_uint32(addr)
        data_len = ctypes.c_uint32(data_len)
        data = (ctypes.c_uint8 * data_len.value)()
        self.jlink.JLINKARM_ReadMem(addr, data_len, ctypes.byref(data))
        return bytes(data)

    def read_32(self, addr):
        """
        Reads one uint32_t from the given address.
        @param  int addr: Address to read.
        @return int: Value read.
        """
        if not self._is_u32(addr):
            raise ValueError('The addr parameter must be an unsigned 32-bit value.')

        addr = ctypes.c_uint32(addr)
        data = ctypes.c_uint32()
        status = ctypes.c_byte()
        self.jlink.JLINKARM_ReadMemU32(addr, 1, ctypes.byref(data), ctypes.byref(status))
        return data.value

    def write_32(self, addr, data):
        """
        Writes one uint32_t data into the given address.
        @param int addr: Address to write.
        @param int data: Value to write.
        """
        if not self._is_u32(addr):
            raise ValueError('The addr parameter must be an unsigned 32-bit value.')

        if not self._is_u32(data):
            raise ValueError('The data parameter must be an unsigned 32-bit value.')

        addr = ctypes.c_uint32(addr)
        data = ctypes.c_uint32(data)
        self.jlink.JLINKARM_WriteU32(addr, data)

    def read_16(self, addr):
        addr = ctypes.c_uint32(addr)
        data = ctypes.c_uint16()
        status = ctypes.c_byte()
        self.jlink.JLINKARM_ReadMemU16(addr, 1, ctypes.byref(data), ctypes.byref(status))
        return data.value

    def write_16(self, addr, data):
        addr = ctypes.c_uint32(addr)
        data = ctypes.c_uint16(data)
        self.jlink.JLINKARM_WriteU16(addr, data)

    def read_8(self, addr, buf, len, status):
        addr = ctypes.c_uint32(addr)
        data = ctypes.c_uint8()
        status = ctypes.c_byte()
        self.jlink.JLINKARM_ReadMemU8(addr, 1, ctypes.byref(data), ctypes.byref(status))
        return data.value

    def write_8(self, addr, data):
        addr = ctypes.c_uint32(addr)
        data = ctypes.c_uint8(data)
        self.jlink.JLINKARM_WriteU8(addr, data)


    def get_hardware_verion(self):
        #UInt32 JLINKARM_GetHardwareVersion()
        return self.jlink.JLINKARM_GetHardwareVersion()

    def get_feature_string(self):
        buffer_size = ctypes.c_uint32(255)
        fwstr = ctypes.create_string_buffer(buffer_size.value)
        self.jlink.JLINKARM_GetFeatureString(fwstr)
        return fwstr.value

    def get_oem_string(self):
        buffer_size = ctypes.c_uint32(255)
        fwstr = ctypes.create_string_buffer(buffer_size.value)
        self.jlink.JLINKARM_GetOEMString(fwstr)
        return fwstr.value

    def get_compile_date_time(self):
        #Text.StringBuilder JLINKARM_GetCompileDateTime()
        return self.jlink.JLINKARM_GetCompileDateTime()

    def get_SN(self):
        #UInt32 JLINKARM_GetSN()
        return self.jlink.JLINKARM_GetSN()

    def get_ID(self):
        #UInt32 JLINKARM_GetId()
        return self.jlink.JLINKARM_GetId()

    def _is_u32(self, value):
        return isinstance(value, int) and 0 <= value <= 0xFFFFFFFF

    def _is_u8(self, value):
        return isinstance(value, int) and 0 <= value <= 0xFF

    def _is_bool(self, value):
        return isinstance(value, bool) or 0 <= value <= 1

    def _is_valid_buf(self, buf):
        if buf is None:
            return False
        for value in buf:
            if not self._is_u8(value):
                return False
        return len(buf) > 0

    def _is_valid_encoding(self, encoding):
        try:
            codecs.lookup(encoding)
        except LookupError:
            return False
        else:
            return True

    def _is_enum(self, param, enum_type):
        if isinstance(param, int) and param in [member for name, member in enum_type.__members__.items()]:
            return True
        elif isinstance(param, str) and param in [name for name, member in enum_type.__members__.items()]:
            return True
        return False

    def _decode_enum(self, param, enum_type):
        if not self._is_enum(param, enum_type):
            return None

        if isinstance(param, int):
            return enum_type(param)
        elif isinstance(param, str):
            return enum_type[param]

if __name__ == '__main__':
    jlink = Jlink()
    print(jlink.dll_version())
    print("Jlink %s"%("Opened" if jlink.is_open() else "Closed"))
    jlink.set_mode()
    jlink.set_speed()
    print(jlink.get_speed())
    print("Jlink %s"%("Connected" if jlink.is_connected() else "Disonnected"))
    #jlink.write(0x20000008+12, bytes("se", encoding = "utf8"))
    #print(jlink.read(0x20000008, 16))
    #jlink.write_32(0x20000008+12, 2)
    #print(jlink.read_32(0x20000008+12))
    print(jlink.get_feature_string())
    print(jlink.get_oem_string())
    print(jlink.get_ID())
    jlink.close()
    print("Jlink %s" % ("Opened" if jlink.is_open() else "Closed"))
