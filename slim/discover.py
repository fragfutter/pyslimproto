import logging
import socket
import struct


import meta

log = meta.log


class SlimDiscovery(object):
    deviceid = meta.deviceid
    revision = meta.revision
    mac = meta.mac
    buffersize = 1024

    def __init__(self, port=meta.SLIMPORT):
        self.port = port

    def pack(self):
        """byte pack a discovery package, see Slim/Networking/Discovery.pm"""
        # 18bytes
        # 1 byte - 'd' - discovery
        # 1 byte - ? - reserved
        # 1 byte - ? - deviceid, 1 is an old slimp3, >=2 <= 4 is a squeezebox
        # 1 byte - ? - firmware revision
        # 8 byte - ? - reserved
        # 6 byte - ? - mac address of client
        result = struct.pack(
            'B x B B 8x 6s',
            ord('d'),       # discovery
            #,              # reserverd
            self.deviceid,  # deviceid 1 is an old slimp3, >=2 <= 4 is a squeezebox
            self.revision,  # firmware version
            #,              # 8 reserved bytes
            self.mac)      # mac address
        return result

    def unpack(self, data):
        """unpack a reply package. see Slim/Networking/Discovery.pm
        As we send version 4 as firmware, we expect a D + 17char hostname.
        Function returns unicode string hostname or None if wrong data"""
        try:
            (packtype, hostname) = struct.unpack('c17s', data)
        except:
            log.debug('unable to parse as discovery reply: %s' % data)
            return None
        if packtype != b'D':
            log.debug('not a discovery reply: %s' % data)
            return None
        else:
            return str(hostname, 'utf-8').rstrip('\0')

    def find(self, singleshot=True, timeout=10):
        """find slim server on the subnet via broadcast.
        @param singleshot, return first who answers, otherwise wait for more replies
        @param timeout, timeout to wait for reply/replies
        @return list of [ ((ip, port), name) ]"""
        result = []
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.settimeout(timeout)
        log.debug('sending discovery broadcast')
        s.sendto(self.pack(), (('<broadcast>', self.port)))
        log.debug('waiting for discovery reply')
        try:
            while True:
                (data, (ip, port)) = s.recvfrom(self.buffersize)
                log.debug('received reply from %s: %s' % (ip, data))
                name = self.unpack(data)
                if name:
                    log.debug('found host %s:%s named %s' % (ip, port, name))
                    result.append(((ip, port), name))
                else:
                    log.debug('package ignored')
                if result and singleshot:
                    break
        except socket.timeout:
            pass
        log.info('slim discovery: %s' % result)
        return result

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    disco = SlimDiscovery()
    log.info(disco.find(singleshot=False))
