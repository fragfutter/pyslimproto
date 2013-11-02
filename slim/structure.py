import struct
import meta

log = meta.log


class SlimStructure(object):
    """Abstract baseclass for slimprotocol message.

    derive Messages from SlimClientToServer or SlimServerToClient to get
    correct header parsing.
    """
    def __init__(self, data=None):
        """
        :param data: is a binary array with data to unpack (data includes headers!)
        """
        self._keys = []
        self._formats = []
        self._data = {}
        for definition in self.structure:
            self.add_field(definition)
        if data is not None:
            self.unpack(data)

    @classmethod
    def name(cls):
        try:
            return cls._name
        except AttributeError:
            return cls.__name__.lower()

    def add_field(self, definition):
        """add a new field. The definition accepts a colon seperated
        definition string fieldname: formatcharacter
        The fieldname is then accessible as object index.

        >> slimstructure.add_field('event_code:4s')
        >> slimstructure['event_code'] = 'four'
        """
        key, formatchar = definition.split(':')
        self._data[key] = None
        # only the last field can be of dynamic size
        # if we already have one, no other field can be added
        if self._has_payload():
            raise Exception("only the last field can be dynamic")
        self._keys.append(key)  # store key
        if formatchar != '*':
            # store format if we aren't the dynamic field
            self._formats.append(formatchar)

    def __len__(self):
        """number of fields. *not* bytelength"""
        return len(self._keys)

    def __getitem__(self, key):
        """access internal fields as dictionary"""
        return self._data[key]

    def __setitem__(self, key, value):
        """access internal fields as dictionary"""
        self._data[key] = value

    def _has_payload(self):
        return len(self._keys) != len(self._formats)

    def unpack(self, binarydata):
        """unpack a byte array (including header bytes!) into fields

        >> slimstructure.unpack(b'four')
        >> slimstrcutre['event_code']
        >>   'four'
        """
        # drop header
        binarydata = binarydata[self.header_size:]
        s = struct.Struct(self.format_string())
        if self._has_payload():
            data = binarydata[:s.size]  # only take the bytes we need
            dynamic = binarydata[s.size:]  # and store the rest in dynamic field
        else:
            data = binarydata
            dynamic = False
        try:
            values = s.unpack(data)
        except struct.error as e:
            log.error('unpack wanted %d bytes, got %d bytes' % (s.size, len(data)))
            raise e
        if self._has_payload():
            values = values + tuple([dynamic, ])
        # zip values with keys and overwrite our internal data
        self._data = dict(zip(self._keys, values))

    def pack(self, *args, **kwargs):
        """either pack the list of values given, or our internal data
        :param args: values to pack in the same order as the field definitions
        :param kwargs: values as keywords in arbitary order. Missing fields will be None
        """
        if args:
            values = args
        elif kwargs:
            # construct values in correct order
            values = []
            for key in self._keys:
                values.append(kwargs.get(key, None))
        else:
            values = self.values()
        if self._has_payload():
            dynamic = bytearray(values.pop(), 'ascii')
        else:
            dynamic = b''
        binarydata = struct.pack(self.format_string(), *values)
        binarydata = binarydata + dynamic
        result = self.add_header(binarydata)
        return result

    def format_string(self):
        """construct the format string from the encoding formats of the fields"""
        return '!' + "".join(self._formats)

    def size(self):
        """byte length of structure including headers.
        For dynamic fields the current value is used.
        """
        result = self.header_size
        result = result + struct.Struct(self.format_string()).size
        if self._has_payload():
            result = result + len(self._data[self._keys[-1]])
        return result

    def keys(self):
        """the field names in order"""
        return self._keys

    def values(self):
        """the values in order"""
        result = []
        for key in self._keys:
            result.append(self._data[key])
        return result

    def has_key(self, key):
        return key in self._keys

    def __str__(self):
        result = []
        for key in self._keys:
            result.append('%s=%s' % (key, self._data[key]))
        return '<%s %s>' % (self.__class__.__name__, ', '.join(result))


class SlimClientToServer(SlimStructure):
    """Messages sent from a client to the server.
    They have a header of eight bytes (4s I) that contains command name
    and length of the payload (without the name or length bytes).

    commands names are uppercase
    """
    header_size = 8

    def add_header(self, binarydata):
        """add length and command to binarydata"""
        # add the command header including data length
        header = struct.pack('! 4s I', bytearray(self.name().upper(), 'ascii'), len(binarydata))
        result = header + binarydata
        return result


class SlimServerToClient(SlimStructure):
    """Messages sent from a server to the client.
    They hav a header of six bytes (H 4s) that contains the length
    of the payload (including command name, excluding the length Word)
    and the command name

    command names are lowercase
    """
    header_size = 6

    def add_header(self, binarydata):
        """add length and command to binarydata"""
        # add the command header including data length
        header = struct.pack('! H 4s', len(binarydata) + 4, bytearray(self.name().lower(), 'ascii'))
        result = header + binarydata
        return result


class Helo(SlimClientToServer):
    structure = [
        'deviceid:B',
        'revision:B',
        'mac:6s',
        'hostid:16s',
        'wifi:H',
        'bytes:Q',
        'language:2s',
    ]


class Bye(SlimClientToServer):
    _cmdname = b'BYE!'
    structure = [
        'upgrade:B',
    ]


class Stat(SlimClientToServer):
    structure = [
        'event_code:4s',
        'crlf:B',
        'mas_initialized:c',
        'mas_mode:c',
        'buffer_size:L',
        'buffer_fill:L',
        'bytes_received:Q',
        'signal_strength:H',
        'jiffies:L',
        'output_buffer_size:L',
        'output_buffer_fill:L',
        'elapsed_seconds:L',
        'voltage:H',
        'elapsed_milliseconds:L',
        'server_timestamp:L',
        'error_code:H',
    ]


class Strm(SlimServerToClient):
    """server to client message. Fieldnames are taken from the
    official documentation.
    But do not trust the logitech documentation, it is out of date
    look at the source in Slim/Player/Squeezebox.pm:540

    The structure is followed by a html header.
    TODO: how do we parse the html header
    """
    structure = [
        'command:c',
        'autostart:c',
        'mode:c',
        'pcm_sample_size:c',
        'pcm_sample_rate:c',
        'pcm_channels:c',
        'pcm_endian:c',
        'threshold:b',
        'spdif_enable:b',
        'transition_period:b',
        'transition_type:c',
        'flags:b',
        'output_threshold:b',
        'slaves:b',
        'replay_gain:L',
        'server_port:H',
        'server_ip:I',
        'headers:*',  # consumes the rest
    ]


class Aude(SlimServerToClient):
    """enable disable audio of dac, spdif"""
    structure = [
        'spdif_enable:b',
        'dac_enable:b',
    ]


class Audg(SlimServerToClient):
    """set audio gain on channels, allow digital volume control
    there is a second version of this structure including a sequencenumber"""
    structure = [
        'old_left:L',
        'old_right:L',
        'digitalvolumecontrol:B',
        'preamp:B',
        'new_left:L',
        'new_right:L',
    ]


class AudgSequence(SlimServerToClient):
    """set audio gain on channels, allow digital volume control
    there is a second version of this structure without a sequencenumber"""
    structure = [
        'old_left:L',
        'old_right:L',
        'digitalvolumecontrol:B',
        'preamp:B',
        'new_left:L',
        'new_right:L',
        'sequence:L',
    ]
