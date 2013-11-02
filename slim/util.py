import string


__printables = string.ascii_letters + string.digits + string.punctuation + ' '
__format = '0x%04x:  ' + ('%s' * 2 + ' ') * 8 + ' ' + '%s' * 16


def hexlines(data, format_=__format):
    """yield data in a hexformat
    0x0000:  0011 2233 4455 6677 8899 aabb ccdd eeff  .................
    """
    position = 0
    while position < len(data):
        chunk = data[position:position + 16]
        # the hex part
        line = [position]
        line.extend(map(lambda x: '%02x' % x, chunk))
        line.extend(['  '] * (16 - len(chunk)))  # fill up with double spaces
        # the ascii part
        line.extend(map(lambda x: chr(x) if chr(x) in __printables else '.', chunk))
        line.extend([' '] * (16 - len(chunk)))  # fill up with single spaces
        line = format_ % tuple(line)
        yield line
        position = position + 16


if __name__ == '__main__':
    for line in hexlines(b'hello world 12345'):
        print(line)
