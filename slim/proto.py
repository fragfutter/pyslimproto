import logging
import socket
import struct
import meta
# from discover import SlimDiscovery

log = meta.log


class SlimProtocol(object):
    deviceid = meta.deviceid
    revision = meta.revision
    mac = meta.mac
    hostid = meta.hostid
    wifichannels = 0b0000011111111111  # US default channellist 0 to 11
    language = b'en'
    buffersize = 1024

    def __init__(self, host, port=meta.SLIMPORT):
        self.host = host
        self.port = port
        self.connection = None
        self.bytesreceived = 0

    def connect(self):
        if self.is_connected():
            log.debug('already connected')
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.connect((self.host, self.port))
        log.debug('connected to %s:%d' % (self.host, self.port))

    def is_connected(self):
        return self.connection is not None

    def helo(self):
        """tell the server who we are"""
        # 10 to  36 bytes
        data = struct.pack(
            '! B B 6s 16s H Q 2s',
            self.deviceid,   # deviceid 1 is an old slimp3, >=2 <= 4 is a squeezebox
            self.revision,   # firmware version
            self.mac,
            self.hostid,
            self.wifichannels,   # unsigned short = two bytes
            self.bytesreceived,  # unsigned long long = 8 bytes
            self.language,
        )
        header = struct.pack(
            '! 4s I',
            b'HELO',
            len(data),
        )
        # EXTEND: also send capabilities information in HELO
        self.send(header + data)

    def send(self, data):
        self.connection.sendall(data)

    def receive(self, length):
        """wait for length bytes of data.
        raises timeout error
        raises no data error"""
        log.debug('receiving %d bytes of data' % length)
        result = b''
        while length > 0:
            data = self.connection.recv(min(length, self.buffersize))
            if len(data) == 0:
                raise socket.error('not data received. socket read error')
            length -= len(data)
            result += data
            log.info('got %s' % data)
        if length < 0:
            raise socket.error('too much data received')
        return result

    def receive_cmd(self):
        expect = 2  # first thing we want is the length
        # fetch the length
        log.debug('waiting for length field')
        data = self.receive(2)
        expect, = struct.unpack('! H', data)
        log.debug('need to fetch %d bytes of data' % expect)
        data = self.receive(expect)
        log.info('received command %s' % data[:4])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    # disco = SlimDiscovery()
    #( host, port), name = disco.find()[0]
    host = '192.168.2.200'
    port = meta.SLIMPORT
    proto = SlimProtocol(host)
    proto.connect()
    proto.helo()
    while True:
        proto.receive_cmd()
    # NEXT:
    # handle the received commands
    # reconnect if connection closes
