"""DWC Network Server Emulator

    Copyright (C) 2014 polaris-
    Copyright (C) 2014 msoucy
    Copyright (C) 2016 Sepalani

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import base64
import logging
import logging.handlers
import random
import string
import struct
import urlparse
import ctypes
import os


def generate_random_str_from_set(ln, chs):
    """Generate a random string of size <ln> based on charset <chs>."""
    return ''.join(random.choice(chs) for _ in range(ln))


def generate_random_str(ln, chs=""):
    """Generate a random string of size <ln>."""
    return generate_random_str_from_set(
        ln,
        chs or (string.ascii_letters + string.digits)
    )


def generate_random_number_str(ln):
    """Generate a random number string of size <ln>."""
    return generate_random_str_from_set(ln, string.digits)


def generate_random_hex_str(ln):
    """Generate a random hexadecimal number string of size <ln>."""
    return generate_random_str_from_set(ln, string.hexdigits.lower())


def calculate_crc8(inp):
    """
    Code: Tetris DS @ 020573F4
    """
    crc_table = [
        0x00, 0x07, 0x0E, 0x09, 0x1C, 0x1B, 0x12, 0x15, 0x38, 0x3F, 0x36, 0x31, 0x24, 0x23, 0x2A, 0x2D,
        0x70, 0x77, 0x7E, 0x79, 0x6C, 0x6B, 0x62, 0x65, 0x48, 0x4F, 0x46, 0x41, 0x54, 0x53, 0x5A, 0x5D,
        0xE0, 0xE7, 0xEE, 0xE9, 0xFC, 0xFB, 0xF2, 0xF5, 0xD8, 0xDF, 0xD6, 0xD1, 0xC4, 0xC3, 0xCA, 0xCD,
        0x90, 0x97, 0x9E, 0x99, 0x8C, 0x8B, 0x82, 0x85, 0xA8, 0xAF, 0xA6, 0xA1, 0xB4, 0xB3, 0xBA, 0xBD,
        0xC7, 0xC0, 0xC9, 0xCE, 0xDB, 0xDC, 0xD5, 0xD2, 0xFF, 0xF8, 0xF1, 0xF6, 0xE3, 0xE4, 0xED, 0xEA,
        0xB7, 0xB0, 0xB9, 0xBE, 0xAB, 0xAC, 0xA5, 0xA2, 0x8F, 0x88, 0x81, 0x86, 0x93, 0x94, 0x9D, 0x9A,
        0x27, 0x20, 0x29, 0x2E, 0x3B, 0x3C, 0x35, 0x32, 0x1F, 0x18, 0x11, 0x16, 0x03, 0x04, 0x0D, 0x0A,
        0x57, 0x50, 0x59, 0x5E, 0x4B, 0x4C, 0x45, 0x42, 0x6F, 0x68, 0x61, 0x66, 0x73, 0x74, 0x7D, 0x7A,
        0x89, 0x8E, 0x87, 0x80, 0x95, 0x92, 0x9B, 0x9C, 0xB1, 0xB6, 0xBF, 0xB8, 0xAD, 0xAA, 0xA3, 0xA4,
        0xF9, 0xFE, 0xF7, 0xF0, 0xE5, 0xE2, 0xEB, 0xEC, 0xC1, 0xC6, 0xCF, 0xC8, 0xDD, 0xDA, 0xD3, 0xD4,
        0x69, 0x6E, 0x67, 0x60, 0x75, 0x72, 0x7B, 0x7C, 0x51, 0x56, 0x5F, 0x58, 0x4D, 0x4A, 0x43, 0x44,
        0x19, 0x1E, 0x17, 0x10, 0x05, 0x02, 0x0B, 0x0C, 0x21, 0x26, 0x2F, 0x28, 0x3D, 0x3A, 0x33, 0x34,
        0x4E, 0x49, 0x40, 0x47, 0x52, 0x55, 0x5C, 0x5B, 0x76, 0x71, 0x78, 0x7F, 0x6A, 0x6D, 0x64, 0x63,
        0x3E, 0x39, 0x30, 0x37, 0x22, 0x25, 0x2C, 0x2B, 0x06, 0x01, 0x08, 0x0F, 0x1A, 0x1D, 0x14, 0x13,
        0xAE, 0xA9, 0xA0, 0xA7, 0xB2, 0xB5, 0xBC, 0xBB, 0x96, 0x91, 0x98, 0x9F, 0x8A, 0x8D, 0x84, 0x83,
        0xDE, 0xD9, 0xD0, 0xD7, 0xC2, 0xC5, 0xCC, 0xCB, 0xE6, 0xE1, 0xE8, 0xEF, 0xFA, 0xFD, 0xF4, 0xF3
    ]
    crc = 0

    for b in inp:
        crc = crc_table[(b ^ crc) & 0xff]

    return crc


def base32_encode(num, reverse=True):
    """Encode a number in base 32.

    Result string is reversed by default.
    """
    alpha = "0123456789abcdefghijklmnopqrstuv"

    encoded = ""
    while num > 0:
        encoded += alpha[num & 0x1f]
        num >>= 5

    encoded.ljust(9, '0')

    if reverse:
        encoded = encoded[::-1]

    return encoded


def base32_decode(s, reverse=False):
    """Decode a number in base 32.

    Input string is not reversed by default.
    """
    alpha = "0123456789abcdefghijklmnopqrstuv"

    if reverse:
        s = s[::-1]

    return reduce(lambda orig, b: ((orig << 5) | alpha.index(b)), s, 0)


# Number routines
def get_num_from_bytes(data, idx, fmt, bigEndian=False):
    """Get number from bytes.

    Endianness by default is little.
    """
    return struct.unpack_from("<>"[bigEndian] + fmt, buffer(bytearray(data)), idx)[0]

# Instead of passing slices, pass the buffer and index so we can calculate
# the length automatically.


def get_short_signed(data, idx, be=False):
    """Get short from bytes.

    Endianness by default is little.
    """
    return get_num_from_bytes(data, idx, 'h', be)


def get_short(data, idx, be=False):
    """Get unsigned short from bytes.

    Endianness by default is little.
    """
    return get_num_from_bytes(data, idx, 'H', be)


def get_int_signed(data, idx, be=False):
    """Get int from bytes.

    Endianness by default is little.
    """
    return get_num_from_bytes(data, idx, 'i', be)


def get_int(data, idx, be=False):
    """Get unsigned int from bytes.

    Endianness by default is little.
    """
    return get_num_from_bytes(data, idx, 'I', be)


def get_ip(data, idx, be=False):
    """Get IP from bytes.

    Endianness by default is little.
    """
    return ctypes.c_int32(get_int(data, idx, be)).value


def get_ip_str(data, idx):
    """Get IP string from bytes."""
    return '.'.join("%d" % x for x in bytearray(data[idx:idx+4]))


def get_ip_from_str(ip_str, be=False):
    """Get IP from string.

    Endianness by default is little.
    """
    return get_ip(bytearray([int(x) for x in ip_str.split('.')]), 0, be)


def get_local_addr(data, idx):
    """Get local address."""
    localip = get_ip_str(data, idx)
    localip_int_le = get_ip(data, idx)
    localip_int_be = get_ip(data, idx, True)
    localport = get_short(data, idx + 4, True)
    return (localip, localport, localip_int_le, localip_int_be)


def get_string(data, idx):
    """Get string from bytes."""
    data = data[idx:]
    end = data.index('\x00')
    return str(''.join(data[:end]))


def get_bytes_from_num(num, fmt, bigEndian=False):
    """Get bytes from number.

    Endianness by default is little.
    """
    return struct.pack("<>"[bigEndian] + fmt, num)


def get_bytes_from_short_signed(num, be=False):
    """Get bytes from short.

    Endianness by default is little.
    """
    return get_bytes_from_num(num, 'h', be)


def get_bytes_from_short(num, be=False):
    """Get bytes from unsigned short.

    Endianness by default is little.
    """
    return get_bytes_from_num(num, 'H', be)


def get_bytes_from_int_signed(num, be=False):
    """Get bytes from int.

    Endianness by default is little.
    """
    return get_bytes_from_num(num, 'i', be)


def get_bytes_from_int(num, be=False):
    """Get bytes from unsigned int.

    Endianness by default is little.
    """
    return get_bytes_from_num(num, 'I', be)


def get_bytes_from_ip_str(ip_str):
    """Get bytes from IP string."""
    return bytearray([int(x) for x in ip_str.split('.')])


def create_logger(loggername, filename, level, log_to_console, log_to_file):
    """Server logging."""
    log_folder = "logs"

    # Create log folder if it doesn't exist
    if not os.path.exists(log_folder):
        os.makedirs(log_folder)

    # Build full path to log file
    filename = os.path.join(log_folder, filename)

    logging.addLevelName(-1, "TRACE")

    fmt = "[%(asctime)s | " + loggername + "] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # logging.basicConfig(format=format, datefmt=date_format)
    logger = logging.getLogger(loggername)
    logger.setLevel(level)

    # Only needed when logging.basicConfig isn't set.
    if log_to_console:
        console_logger = logging.StreamHandler()
        console_logger.setFormatter(
            logging.Formatter(fmt, datefmt=date_format)
        )
        logger.addHandler(console_logger)

    if log_to_file and filename:
        # Use a rotating log set to rotate every night at midnight with a
        # max of 10 backups
        file_logger = logging.handlers.TimedRotatingFileHandler(
            filename,
            when='midnight',
            backupCount=10)  # logging.FileHandler(filename)
        file_logger.setFormatter(
            logging.Formatter(fmt, datefmt=date_format)
        )
        logger.addHandler(file_logger)

    return logger


def print_hex(data, cols=16, sep=' ', pretty=True):
    """Print data in hexadecimal.

    Customizable separator and columns number.
    Can be pretty printed but takes more time.
    """
    if pretty:
        print pretty_print_hex(data, cols, sep)
    else:
        print sep.join("%02x" % b for b in bytearray(data))


def pretty_print_hex(orig_data, cols=16, sep=' '):
    """Hexadecimal pretty print.

    Takes ~1s per characters.
    Customizable separator and columns number.
    """
    data = bytearray(orig_data)
    end = len(data)
    line = "\n%08x | %-*s | %s"
    size = cols * 3 - 1

    i = 0
    output = ""
    while i < end:
        if i + cols < end:
            j = i + cols
        else:
            j = end
        output += line % (
            i,
            size,
            sep.join("%02x" % c for c in data[i:j]),
            "".join(chr(c) if 0x20 <= c < 0x7F else
                    '.'
                    for c in data[i:j])
        )
        i += cols

    return output

# def pretty_print_hex(orig_data, cols=16):
#    """Takes ~1.5s per characters"""
#
#    data = bytearray(orig_data)
#    output = "\n"
#
#    for i in range(len(data) / cols + 1):
#        output += "%08x | " % (i * 16)
#
#        c = 0
#        for x in range(cols):
#            if (i * cols + x + 1) > len(data):
#                break
#
#            output += "%02x " % data[i * cols + x]
#            c += 1
#
#        c = cols - c
#        output += " " * (c * 3 + 1)
#        for x in range(cols):
#            if (i * cols + x + 1) > len(data):
#                break
#
#            if not chr(data[i * cols + x]) in string.printable:
#                output += "."
#            else:
#                output += "%c" % data[i * cols + x]
#        output += "\n"
#
#    return output


def qs_to_dict(s):
    """Convert query string to dict."""
    ret = urlparse.parse_qs(s, True)

    for k, v in ret.items():
        try:
            # I'm not sure about the replacement for '-', but it'll at
            # least let it be decoded.
            # For the most part it's not important since it's mostly
            # used for the devname/ingamesn fields.
            ret[k] = base64.b64decode(urlparse.unquote(v[0])
                                              .replace("*", "=")
                                              .replace("?", "/")
                                              .replace(">", "+")
                                              .replace("-", "/"))
        except TypeError:
            """
            print("Could not decode following string: ret[%s] = %s"
                  % (k, v[0]))
            print("url: %s" % s)
            """
            # If you don't assign it like this it'll be a list, which
            # breaks other code.
            ret[k] = v[0]

    return ret


def dict_to_qs(d):
    """Convert dict to query string.

    nas(wii).nintendowifi.net has a URL query-like format but does not
    use encoding for special characters.
    """
    # Dictionary comprehension is used to not modify the original
    ret = {k: base64.b64encode(v).replace("=", "*") for k, v in d.items()}

    return "&".join("{!s}={!s}".format(k, v) for k, v in ret.items()) + "\r\n"
