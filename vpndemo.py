import sys
import os
import fcntl
import struct
import time
import socket
import threading
import random

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
            s = os.read(self.tun_fd, BUFSIZE)
            if self.peer_address:
                self.udp_sock.sendto(self.encrypt(s), self.peer_address)

    def udp_to_tun(self):
        while True:
            s, self.peer_address = self.udp_sock.recvfrom(BUFSIZE)
            os.write(self.tun_fd, self.decrypt(s))

if __name__ == '__main__':
    if len(sys.argv) == 2:
        tunnel = Tunnel(local_port=int(sys.argv[1]))
    elif len(sys.argv) == 4:
        tunnel = Tunnel(local_port=int(sys.argv[1]), peer_address=(sys.argv[2], int(sys.argv[3])))
    else:
        print 'Usage: %s LOCAL_PORT [REMOTE_HOST REMOTE_PORT]' % sys.argv[0]

