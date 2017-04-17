#!/usr/bin/python3
# -*- coding: utf-8 -*-

MASK_32 = 0xffffffff


class RingBuffer(object):
    def __init__(self, mem_read, mem_write, arr):
        self.WrOff, self.RdOff, self.mask, self.esize, self.pBuffer = arr
        self.mem_read = mem_read
        self.mem_write= mem_write

    def fifo_empty(self):
        return self.WrOff == self.RdOff

    def fifo_len(self):
        return (self.WrOff - self.RdOff) & MASK_32

    def fifo_unused(self):
        return self.mask + 1 - self.fifo_len()

    def fifo_full(self):
        return self.fifo_unused() == 0

    def fifo_copy_in(self, src, off):
        '''
        src: bytearray
        '''
        size = self.mask + 1
        off &= self.mask

        l = min(len(src), size - off)

        self.mem_write(self.pBuffer + off, src[:l])
        if len(src) > l:
            self.mem_write(self.pBuffer, src[l:])

    def fifo_in(self, src):
        l = self.fifo_unused()
        if len(src) > l: src = src[:l]
        self.fifo_copy_in(src, self.WrOff)
        self.WrOff = (self.WrOff + len(src)) & MASK_32
        return len(src)

    def fifo_copy_out(self, len, off):
        size = self.mask + 1
        off &= self.mask

        l = min(len, size - off)

        # target addr, dst, len
        d = bytearray(self.mem_read(self.pBuffer + off, l))
        d.extend(self.mem_read(self.pBuffer, len - l))
        return d

    def fifo_out_peek(self, len):
        l = self.fifo_len()
        if len > l: len = l
        return self.fifo_copy_out(len, self.RdOff)

    def fifo_out(self, l):
        b = self.fifo_out_peek(l)
        l = len(b)
        self.RdOff = (self.RdOff + l) & MASK_32
        return b