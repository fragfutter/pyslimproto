import struct
import meta

log = meta.log

"""
Classes to handle Slimdevices Mesages.

Slimdevices uses different message formats from server to client
and vice versa. For this reason there is an abstract baseclass
SlimMessage.

Derived is the ClientMessage, for messages sent from a client to
the server. These messages have an eight byte header containing
a four character string (command name, uppercase) and four bytes
with the messager-length.

A ServerMessage is sent from a server to the client. It has a six
bytes header containing the messager-length (two bytes) and a four
character string (command name, lowercase).

To complicate things, the message-length has a different meaning for
ClientMessage and ServerMessage. For a ClientMessage message-length is
the number of bytes in the body, without the command name or the four
bytes of the message-length field. For a ServerMessage message-length is
the number of bytes in the body, including the command name, but without
the two bytes of the message-length field.


  * A server sends ServerMessages and receives ClientMessages

  * A client sends ClientMessages and receives ServerMessages

  * A ServerMessage has a six bytes header. message-length includes
    command-name. The order is message-length (2), command-name (4).

  * A ClientMessage has a eight bytes header. message-length excludes
    command-name. The order is command-name (4), message-length (4)
"""


class classproperty(object):
    def __init__(self, getter):
        self.getter = getter

    def __get__(self, instance, owner):
        return self.getter(owner)


class SlimMessage(object):
    """Abstract baseclass for slimprotocol message.

    derive Messages from SlimClientMessage or SlimServerMessage to get
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

    @classproperty
    def name(cls):
        """calculate the message name if not set as class attribute.

        The message name is derived from the classname by lowercasing it and
        removing trailing 'message'.

        This is method is called at most once for every class. It will overwrite
        the class attribute name with the value to never be called again.
        """
        name = cls.__name__.lower()
        if name.endswith('message'):
            name = name[:-len('message')]
        cls.name = name  # store it
        return name

    def add_field(self, definition):
        """add a new field. The definition accepts a colon seperated
        definition string fieldname: formatcharacter
        The fieldname is then accessible as object index.
        The last field added can be a wildcard ('*') field. This is
        a string of variable length.

        >> slimstructure.add_field('event_code:4s')
        >> slimstructure['event_code'] = 'four'
        """
        key, formatchar = definition.split(':')
        self._data[key] = None
        # only the last field can be of dynamic size
        # if we already have one, no other field can be added
        if self._has_variable_field():
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

    def _has_variable_field(self):
        """check if the last field is of variable length (has no format)"""
        return len(self._keys) != len(self._formats)

    def unpack(self, binarydata):
        """unpack a byte array (including header bytes) into fields

        >> slimstructure.unpack(b'four')
        >> slimstrcutre['event_code']
        >>   'four'
        """
        binarydata = binarydata[self.header_size:]  # drop header
        s = struct.Struct(self.format_string())
        if self._has_variable_field():
            # the last field is a string of variable length
            # only parse the fixed length fields, the rest is payload
            data = binarydata[:s.size]  # only take the bytes we need
            variable_field_value = binarydata[s.size:]  # and store the rest in dynamic field
        else:
            data = binarydata
        # check if we have the correct number of bytes
        if not s.size == len(data):
            raise ValueError("binary data length (%d) missmatch with structure length (%d)" % (len(data), s.size))
        try:
            values = s.unpack(data)
        except struct.error as e:
            log.error('unpack wanted %d bytes, got %d bytes' % (s.size, len(data)))
            raise e
        if self._has_variable_field():
            values = values + tuple([variable_field_value, ])
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
        if self._has_variable_field():
            # the variable_field is always the last, remove it from the list
            # (so struct.pack is happy) and convert it to byte array
            variable_field_value = bytearray(values.pop(), 'ascii')
        else:
            variable_field_value = b''
        binarydata = struct.pack(self.format_string(), *values)
        binarydata = binarydata + variable_field_value
        result = self.add_header(binarydata)
        return result

    def format_string(self):
        """construct the format string from the encoding formats of the fields"""
        return '!' + "".join(self._formats)

    def size(self):
        """byte length of structure including headers.
        For dynamic fields the current value is used.
        """
        result = self.header_size  # implemented by derived classes
        result = result + struct.Struct(self.format_string()).size
        if self._has_variable_field():
            # append current size of variable field
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

    @classmethod
    def factory(cls, data):
        """determine message type and return matching instance"""
        messagename = cls.name_from_data(data)
        for SubClass in cls.__subclasses__():
            # some messages have different implementations
            # for example audg exists with, or without a sequence number
            # after a parsing error we simply try for the next
            if SubClass.name == messagename:
                try:
                    result = SubClass(data)
                    log.debug("message parsed as %s" % result)
                    return result
                except ValueError:
                    log.debug("could not be parsed by %s, try other" % SubClass)
                    pass
        log.warning("unknown Message %s" % messagename)
        return None

    def add_header(self, body):
        """add the correct header to the packed message body.
        To be implemented in SubClasses"""
        raise NotImplementedError()

    @classmethod
    def name_from_data(cls, data):
        """fetch the message name from a binary array.
        To be implemented in SubClasses"""
        raise NotImplementedError()


class SlimClientMessage(SlimMessage):
    """Messages sent from a client to the server.
    They have a header of eight bytes (4s I) that contains command name
    and message-length of the body (without the name or length bytes).

    commands names are uppercase
    """
    header_size = 8

    @classmethod
    def name_from_data(cls, data):
        return struct.unpack('! 4s', data[0:4])[0].decode('ascii').lower()

    def add_header(self, binarydata):
        """add length and command to binarydata"""
        # add the command header including data length
        header = struct.pack('! 4s I', bytearray(self.name.upper(), 'ascii'), len(binarydata))
        result = header + binarydata
        return result


class SlimServerMessage(SlimMessage):
    """Messages sent from a server to the client.
    They hav a header of six bytes (H 4s) that contains the message-length
    of the body (including command name, excluding the length Word)
    and the command name

    command names are lowercase
    """
    header_size = 6

    @classmethod
    def name_from_data(cls, data):
        return struct.unpack('! 4s', data[2:6])[0].decode('ascii').lower()

    def add_header(self, binarydata):
        """add length and command to binarydata"""
        # add the command header including data length
        header = struct.pack('! H 4s', len(binarydata) + 4, bytearray(self.name.lower(), 'ascii'))
        result = header + binarydata
        return result


class Helo(SlimClientMessage):
    structure = [
        'deviceid:B',
        'revision:B',
        'mac:6s',
        'hostid:16s',
        'wifi:H',
        'bytes:Q',
        'language:2s',
    ]


class Bye(SlimClientMessage):
    name = 'bye!'
    structure = [
        'upgrade:B',
    ]


class Stat(SlimClientMessage):
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


class Strm(SlimServerMessage):
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


class Aude(SlimServerMessage):
    """enable disable audio of dac, spdif"""
    structure = [
        'spdif_enable:b',
        'dac_enable:b',
    ]


class Audg(SlimServerMessage):
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


class AudgSequence(SlimServerMessage):
    """set audio gain on channels, allow digital volume control
    there is a second version of this structure without a sequencenumber"""
    name = 'audg'
    structure = [
        'old_left:L',
        'old_right:L',
        'digitalvolumecontrol:B',
        'preamp:B',
        'new_left:L',
        'new_right:L',
        'sequence:L',
    ]


class Setd(SlimServerMessage):
    """these are player preferences, stored in the server.
    The payload can have different meanings and encodings.

    See Slim/Player/Squeezebox2.pm:playerSettingsFrame

    key:name valuetype
    0:playername Z* (null terminated string)
    1:digitalOutputEncoding B
    2:wordClockOutput B
    3:powerOffDac B
    4:disableDac B
    5:fxloopSource B
    6:fxloopClick B
    254:displayWidth B

    values can be empty, then a client should use it's default
    """
    # TODO implement the different cases (None, Byte, String)
    #      and an API to access them by name
    preferences = {
        0: 'playername',  # null terminated string, everything else is a byte
        1: 'digital_output_encoding',
        2: 'word_clock_output',
        3: 'power_off_dac',
        4: 'disable_dac',
        5: 'fxloop_source',
        6: 'fxloop_click',
        254: 'display_width',
    }
    structure = [
        'pref_id:B',
        'value:*',  # might need further parsing
    ]
