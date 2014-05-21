import base64
import logging
import random
import struct
import string

def _generate_random_str(l, chs):
    return ''.join(random.choice(chs) for _ in range(l))

def generate_random_str(l):
    return _generate_random_str(l, string.letters + string.digits)

def generate_random_number_str(l):
    return _generate_random_str(l, string.digits)

def generate_random_hex_str(len):
    return _generate_random_str(l, string.hexdigits)

# Code: Tetris DS @ 020573F4
def calculate_crc8(input):
    crc_table = [ 0x00, 0x07, 0x0E, 0x09, 0x1C, 0x1B, 0x12, 0x15, 0x38, 0x3F, 0x36, 0x31, 0x24, 0x23, 0x2A, 0x2D,
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
                  0xDE, 0xD9, 0xD0, 0xD7, 0xC2, 0xC5, 0xCC, 0xCB, 0xE6, 0xE1, 0xE8, 0xEF, 0xFA, 0xFD, 0xF4, 0xF3 ]
    crc = 0

    for b in input:
        crc = crc_table[(b ^ crc) & 0xff]

    return crc


def base32_encode(num, reverse = True):
    alpha = "0123456789abcdefghijklmnopqrstuv"

    encoded = ""
    while num > 0:
        n = num & 0x1f
        num = num >> 5
        encoded += alpha[n]

    if reverse == True:
        encoded = encoded[::-1] # Reverse string

    return encoded


def base32_decode(str, reverse = False):
    alpha = "0123456789abcdefghijklmnopqrstuv"

    if reverse == True:
        str = str[::-1] # Reverse string

    orig = 0
    for b in str:
        orig = orig << 5
        orig = orig | alpha.index(b)

    return orig


# Number routines

def get_num_from_bytes(data, idx, bytes, bigEndian = False):
    '''
    Convert an arbitrary byte sequence of a given length into a number
    '''
    # Get only the bytes we want to work with
    sfmt = "<>"[bigEndian] + {"B":1, "H":2, "I":4, "L":8}[bytes]
    return struct.unpack(sfmt, data[idx:idx+bytes])[0]

# Instead of passing slices, pass the buffer and index so we can calculate the length automatically.
def get_short(data, idx):
    return get_num_from_bytes(data, idx, 2, False)

def get_short_be(data, idx):
    return get_num_from_bytes(data, idx, 2, True)

def get_int(data, idx):
    return get_num_from_bytes(data, idx, 4, False)

def get_int_be(data, idx):
    return get_num_from_bytes(data, idx, 4, True)

def get_string(data, idx):
    data = data[idx:]
    end = data.index('\0')
    return str(data[:end])

def get_bytes_from_num(num, size, bigEndian = False):
    '''
    Convert a number of a given size into a bytestring
    '''
    sfmt = "<>"[bigEndian]+{1:"B",2:"H",4:"I",8:"L"}[bytes]
    return struct.pack(sfmt, num)

def get_bytes_from_short(num):
    return get_bytes_from_num(num, 2, False)

def get_bytes_from_short_be(num):
    return get_bytes_from_num(num, 2, True)

def get_bytes_from_int(num):
    return get_bytes_from_num(num, 4, False)

def get_bytes_from_int_be(num):
    return get_bytes_from_num(num, 4, True)


# For server logging
def create_logger(loggername, filename, level, log_to_console, log_to_file):
    logging.addLevelName(-1, "TRACE")

    format= "[%(asctime)s | " + loggername + "] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    #logging.basicConfig(format=format, datefmt=date_format)
    logger = logging.getLogger(loggername)
    logger.setLevel(level)

    # Only needed when logging.basicConfig isn't set.
    if log_to_console == True:
        console_logger = logging.StreamHandler()
        console_logger.setFormatter(logging.Formatter(format, datefmt=date_format))
        logger.addHandler(console_logger)

    if log_to_file == True and filename != "":
        file_logger = logging.FileHandler(filename)
        file_logger.setFormatter(logging.Formatter(format, datefmt=date_format))
        logger.addHandler(file_logger)

    return logger

def print_hex(data, cols = 16):
    print pretty_print_hex(data, cols)

def pretty_print_hex(orig_data, cols = 16):
    data = bytearray(orig_data)
    output = "\n"

    for i in range(len(data) / cols + 1):
        output += "%08x | " % (i * 16)

        c = 0
        for x in range(cols):
            if (i * cols + x + 1) > len(data):
                break

            output += "%02x " % data[i * cols + x]
            c += 1

        c = cols - c
        output += " " * (c * 3 + 1)
        for x in range(cols):
            if (i * cols + x + 1) > len(data):
                break

            if data[i * cols + x] < 0x21 or data[i * cols + x] >= 0x7f:
                output += "."
            else:
                output += "%c" % data[i * cols + x]
        output += "\n"

    return output
