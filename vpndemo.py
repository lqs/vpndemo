#!/usr/bin/env python

import sys
import os
import struct
import time
import socket
import threading
import random
import platform

is_windows = platform.system() == 'Windows'

if is_windows:
    import _winreg
    import win32file
else:
    import fcntl

TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_TAP = 0x0002
IFF_NO_PI = 0x1000
IFNAMSIZ = 16

BUFSIZE = 65536

class Tunnel:

    def __init__(self, local_port=12345, peer_address=None):
        self.peer_address = peer_address
        self.is_server = peer_address == None
        self.tun_fd, self.ifname = self.open_tun()
        self.udp_sock = self.open_udp(local_port)

        threading.Thread(target=self.tun_to_udp).start()
        threading.Thread(target=self.udp_to_tun).start()

    def open_tun(self):
        if is_windows:
            def get_device_guid():
                adapter_key = r'SYSTEM\CurrentControlSet\Control\Class\{4D36E972-E325-11CE-BFC1-08002BE10318}'
                adapters = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, adapter_key)
                index = 0
                while True:
                    try:
                        key_name = _winreg.EnumKey(adapters, index)
                    except WindowsError, err:
                        if err.winerror == 259:
                            break
                        raise

                    try:
                        adapter = _winreg.OpenKey(adapters, key_name)
                        try:
                            component_id = _winreg.QueryValueEx(adapter, 'ComponentId')[0]
                            if component_id in ('tap0801', 'tap0901'):
                                return _winreg.QueryValueEx(adapter, 'NetCfgInstanceId')[0]
                        except WindowsError, err:
                            print err
                    except WindowsError, err:
                        pass

                    index += 1

            guid = get_device_guid()


            def CTL_CODE(device_type, function, method, access):
                return (device_type << 16) | (access << 14) | (function << 2) | method;
             
            def TAP_CONTROL_CODE(request, method):
                return CTL_CODE(34, request, method, 0)
             
            TAP_IOCTL_SET_MEDIA_STATUS = TAP_CONTROL_CODE(6, 0)

            handle = win32file.CreateFile(r'\\.\Global\%s.tap' % guid,
                                              win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                                              win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                                              None, win32file.OPEN_EXISTING,
                                              win32file.FILE_ATTRIBUTE_SYSTEM, # | win32file.FILE_FLAG_OVERLAPPED,
                                              None)

            win32file.DeviceIoControl(handle, TAP_IOCTL_SET_MEDIA_STATUS, '\x01\x00\x00\x00', None)

            return handle, guid

        else:
            fd = os.open('/dev/net/tun', os.O_RDWR)
            ifs = fcntl.ioctl(fd, TUNSETIFF, struct.pack('16sH', '', IFF_TAP | IFF_NO_PI))
            ifname = ifs[:16].strip('\x00')
            if self.is_server:
                os.system('ifconfig %s 10.4.0.1/16' % ifname)
            else:
                os.system('ifconfig %s 10.4.%d.%d/16' % (ifname, random.randrange(256), random.randrange(256)))
            return fd, ifname

    def open_udp(self, local_port):
        sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', local_port))
        return sock

    def encrypt(self, s):
        return s

    def decrypt(self, s):
        return s

    def tun_to_udp(self):
        while True:
            if is_windows:
                l, s = win32file.ReadFile(self.tun_fd, BUFSIZE)
            else:
                s = os.read(self.tun_fd, BUFSIZE)
            if self.peer_address:
                self.udp_sock.sendto(self.encrypt(s), self.peer_address)

    def udp_to_tun(self):
        while True:
            s, self.peer_address = self.udp_sock.recvfrom(BUFSIZE)
            if is_windows:
                win32file.WriteFile(self.tun_fd, self.decrypt(s))
            else:
                os.write(self.tun_fd, self.decrypt(s))

if __name__ == '__main__':
    if len(sys.argv) == 2:
        tunnel = Tunnel(local_port=int(sys.argv[1]))
    elif len(sys.argv) == 4:
        tunnel = Tunnel(local_port=int(sys.argv[1]), peer_address=(sys.argv[2], int(sys.argv[3])))
    else:
        print 'Usage: %s LOCAL_PORT [REMOTE_HOST REMOTE_PORT]' % sys.argv[0]

