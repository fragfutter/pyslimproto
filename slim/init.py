import socket
import asyncore
import uuid
import struct
import logging

log = logging.getLogger('slim')

SLIMPORT = 3483    # server listens on tcp, client on udp
WEBPORT = 9000     # webinterface
BUFFERSIZE = 1024  # reading messages in this blocksize


class SlimProto(object):
    """implements the logitech/slimdevices squeezbox media
    protocol parsing"""
    def __init__(self):
        pass


class SlimClient(object):
    """implements the logitech/slimdevices squeezebox media
    communication layer"""
    def __init__(self, host, port=SLIMPORT):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        log.debug('connecting to %s:%d' % (host, port))
        self._socket.connect((host, port))

    def send(self, msg):
        """send a SlimProto message to the server"""
        pass

    def receive(self, length=None):
        """receive length bytes of data from server,
        and return a SlimProto Object with the parsed data"""
        pass




if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    discover = SlimDiscover()
    asyncore.loop(30)
    discover.send()

