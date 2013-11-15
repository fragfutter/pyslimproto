import re
import logging
import socket
import time
import struct
import meta
from discover import SlimDiscovery
from message import SlimServerMessage, Helo, Bye, Stat
import util

log = meta.log


class SlimClient(object):
    """
    A client for slimdevices media server

    The main loop connects to a slimdevises server and sends a helo message.
    Afterwards it waits for SlimServerMessages. Messages are parsed by calling
    the SlimServerMessageFactory. Afterwards a function "handle_%s" % msg.name
    is called.

    To implement functionality add a function handle_msgname for each message
    type you want to process.
    """
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
        self.timeout = 10  # expect at least a stat package every ten seconds
        self.__terminate = False

    def connect(self):
        if self.is_connected():
            log.debug('already connected')
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.settimeout(self.timeout)
        self.connection.connect((self.host, self.port))
        log.debug('connected to %s:%d' % (self.host, self.port))

    def is_connected(self):
        return self.connection is not None

    def get_jiffies(self):
        """a monotonic increasing number with a resolution of 1khz"""
        # we will use current time since epoche * 1000
        # but we need to rebase so it fits into 32bit long
        # we module divide it by max int and use the remainder
        # this will wrap at some point, but should be ok
        MAX = pow(2, 32)  # make pep8 happy and do not use **
        return int((time.time() * 1000) % MAX)

    def dump(self, data, prefix=""):
        # log a hexdump
        # 0011 2233 4455 6677  8899 aabb ccdd eeff    .... .....  .... ....
        for line in util.hexlines(data):
            log.debug(prefix + line)

    def send(self, data):
        self.dump(data, prefix="sending ")
        self.connection.sendall(data)

    def receive(self, length):
        """wait for length bytes of data.
        raises timeout error
        raises no data error"""
        result = b''
        while length > 0:
            data = self.connection.recv(min(length, self.buffersize))
            if len(data) == 0:
                raise socket.error('no data received. socket read error')
            length -= len(data)
            result += data
        self.dump(result, prefix="received: ")
        if length < 0:
            raise socket.error('too much data received')
        return result

    def receive_message(self):
        expect = 2  # first thing we want is the length
        log.debug('waiting for length field')
        data = self.receive(expect)
        expect, = struct.unpack('! H', data)
        log.debug('need to fetch %d bytes of data' % expect)
        data = data + self.receive(expect)
        message = SlimServerMessage.factory(data)
        return message

    def run(self):
        """connect to slimserver, introduce self and wait for commands"""
        self.connect()
        self.action_helo()
        i = 200
        while True:
            try:
                message = self.receive_message()
            except socket.timeout:
                # no data from server
                log.debug("timeout waiting for message")
                if self.__terminate:
                    return
                else:
                    continue
            self.handle_message(message)
            i = i - 1
            if i < 0:
                break
        self.action_bye()

    def quit(self):
        """set terminate flag. """
        self.__terminate = True

    def handle_message(self, message, name=None):
        """dispatch message to handler.
        :message:
            a SlimMessage
        :name:
            optional overwrite message-name. For submessages
            where the name is not identical to the message-name.
        """
        if not message:
            log.info("empty message, ignoring")
            return
        if not name:
            name = re.sub('[^a-z_]', '', message.name.lower())
        handler_name = 'handle_%s' % name
        handler = getattr(self, handler_name, None)  # which function handles this?
        if not handler:
            log.info("no handler for message (%s), ignoring %s" % (handler_name, message))
            return
        handler(message)

    ### Actions
    def action_bye(self):
        """send bye and disconnect"""
        if self.is_connected:
            data = Bye().pack(upgrade=False)
            try:
                self.send(data)
            except socket.timeout:
                pass  # ignore timeout, the server might have gone
        self.connection = None

    def action_helo(self):
        """tell the server who we are"""
        data = Helo().pack(
            self.deviceid,
            self.revision,   # firmware version
            self.mac,
            self.hostid,
            self.wifichannels,   # unsigned short = two bytes
            self.bytesreceived,  # unsigned long long = 8 bytes
            self.language,
        )
        # EXTEND: also send capabilities information in HELO
        self.send(data)

    def action_stmt(self, timestamp=0):
        """report status information to the server"""
        fields = Stat()
        fields['event_code'] = b'STMt'
        fields['crlf'] = 0
        fields['mas_initialized'] = b'0'
        fields['mas_mode'] = b'0'
        fields['buffer_size'] = 0
        fields['buffer_fill'] = 0
        fields['bytes_received'] = 0
        fields['signal_strength'] = 100
        fields['jiffies'] = self.get_jiffies()
        fields['output_buffer_size'] = 0
        fields['output_buffer_fill'] = 0
        fields['elapsed_seconds'] = 0
        fields['voltage'] = 0
        fields['elapsed_milliseconds'] = 0
        fields['server_timestamp'] = timestamp
        fields['error_code'] = 0
        self.send(fields.pack())

    ### Message Handlers

    def handle_aude(self, message):
        log.debug(str(message))

    def handle_audg(self, message):
        log.debug(str(message))

    def handle_setd(self, message):
        log.debug(str(message))

    def handle_strm(self, message):
        """process a str command send by the server"""
        # do not trust documentation look at the source
        # in Slim/Player/Squeezebox.pm:540
        # message has subcommands
        self.handle_message(message, 'strm_%s' % message['command'].decode('ascii'))

    def handle_strm_t(self, message):
        self.action_stmt(message['replay_gain'])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    disco = SlimDiscovery()
    (host, port), name = disco.find()[0]
    #host = '127.0.0.1'
    #port = meta.SLIMPORT
    client = SlimClient(host)
    client.run()
