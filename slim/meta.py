import logging
import uuid
import struct

SLIMPORT = 3483

log = logging.getLogger('slim')

"""
mac adresse of primary interface as byte array.
This is not clean as it uses uuid, but will always result
in the same uuid so slim is happy
"""
# only in python 3  mac = uuid.getnode().to_bytes(6, 'big')
mac = bytearray(struct.pack('>q', uuid.getnode())[2:])
"""deviceid, 1 is an old slimp3, >=2 <= 4 is a squeezebox, 12 is squeezeplay"""
deviceid = 12
"""firmware version"""
revision = 0
"""unique id of this host"""
hostid = uuid.uuid3(uuid.NAMESPACE_OID, str(uuid.getnode())).bytes
