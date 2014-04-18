import base64
import hashlib
import json
import time

import other.utils as utils

def generate_secret_keys(filename="gslist.cfg"):
    key_file = open(filename)

    secret_key_list = {}
    for line in key_file.readlines():
        #name = line[:54].strip() # Probably won't do anything with the name for now.
        id = line[54:54+19].strip()
        key = line[54+19:].strip()

        secret_key_list[id] = key

    return secret_key_list

# GameSpy uses a slightly modified version of base64 which replaces +/= with []_
def base64_encode(input):
    output = base64.b64encode(input).replace('+', '[').replace('/', ']').replace('=', '_')
    return output


def base64_decode(input):
    output = base64.b64decode(input.replace('[', '+').replace('/', ']').replace('_', '='))
    return output

# Tetris DS overlay 10 @ 0216E9B8
def rc4_encrypt(_key, _data):
    key = bytearray(_key)
    data = bytearray(_data)

    # Key-scheduling algorithm
    S = range(0x100)

    j = 0
    for i in range(0x100):
        # Get index to swap with
        j = (j + S[i] + key[i % len(key)]) & 0xff

        # Perform swap
        S[i], S[j] = S[j], S[i]

    # Pseudo-random generation algorithm + encryption
    i = 0
    j = 0
    for x in range(len(data)):
        i = (i + 1 + data[x]) & 0xff # Modified RC4? What's this data[x] doing here?
        j = (j + S[i]) & 0xff

        S[i], S[j] = S[j], S[i]

        data[x] ^= S[(S[i] + S[j]) & 0xff]

    return data

# Tetris DS overlay 10 @ 0216E9B8
# Used by the master server to send some data between the client and server.
# This seems to be what Luigi Auriemma calls "Gsmsalg".
def prepare_rc4_base64(_key, _data):
    data = rc4_encrypt(_key, _data)
    data.append(0)
    return base64.b64encode(buffer(data))

# get the login data from nas.nintendowifi.net/ac from an authtoken
def parse_authtoken(authtoken, db):
    messages = {}
    nas_data = db.get_nas_login(authtoken)

    if nas_data == None:
       return None

    return json.loads(nas_data)


def generate_response(challenge, ac_challenge, secretkey, authtoken):
    md5 = hashlib.md5()
    md5.update(ac_challenge)

    output = md5.hexdigest()
    output += ' ' * 0x30
    output += authtoken
    output += secretkey
    output += challenge
    output += md5.hexdigest()

    md5_2 = hashlib.md5()
    md5_2.update(output)

    return md5_2.hexdigest()


# The proof is practically the same thing as the response, except it has the challenge and the secret key swapped.
# Maybe combine the two functions later?
def generate_proof(challenge, ac_challenge, secretkey, authtoken):
    md5 = hashlib.md5()
    md5.update(ac_challenge)

    output = md5.hexdigest()
    output += ' ' * 0x30
    output += authtoken
    output += challenge
    output += secretkey
    output += md5.hexdigest()

    md5_2 = hashlib.md5()
    md5_2.update(output)

    return md5_2.hexdigest()

# Code: Tetris DS @ 02057A14
def get_friendcode_from_profileid(profileid, gameid):
    friendcode = 0

    # Combine the profileid and gameid into one buffer
    buffer = [(profileid >> (8 * i)) & 0xff for i in range(4)]
    buffer += [ord(c) for c in gameid]

    crc = utils.calculate_crc8(buffer)

    # The upper 32 bits is the crc8 of the combined buffer.
    # The lower 32 bits of the friend code is the profileid.
    friendcode = ((crc & 0x7f) << 32) | profileid

    return friendcode

def get_profileid_from_friendcode(friendcode):
    # Get the lower 32 bits as the profile id
    profileid = friendcode & 0xffffffff
    return profileid

# Code from Luigi Auriemma's enctypex_decoder.c
# It's kind of sloppy in parts, but it works. Unless there's some issues then it'll probably not change any longer.
class EncTypeX:
    def __init__(self):
        return

    def decrypt(self, key, validate, data):
        if not key or not validate or not data:
            return None

        encxkey = bytearray([0] * 261)
        data = self.init(encxkey, key, validate, data)
        self.func6(encxkey, data, len(data))

        return data

    def encrypt(self, key, validate, data):
        if not key or not validate or not data:
            return None

        # Convert data from strings to byte arrays before use or else it'll raise an error
        key = bytearray(key)
        validate = bytearray(validate)

        # Add room for the header
        tmp_len = 20
        data = bytearray(tmp_len) + data

        keylen = len(key)
        vallen = len(validate)
        rnd = ~int(time.time())

        for i in range(tmp_len):
            rnd = (rnd * 0x343FD) + 0x269EC3
            data[i] = (rnd ^ key[i % keylen] ^ validate[i % vallen]) & 0xff

        header_len = 7
        data[0] = (header_len - 2) ^ 0xec
        data[1] = 0x00
        data[2] = 0x00
        data[header_len - 1] = (tmp_len - header_len) ^ 0xea

        header = data[:tmp_len]  # The header of the data gets chopped off in init(), so save it
        encxkey = bytearray([0] * 261)
        data = self.init(encxkey, key, validate, data)
        self.func6e(encxkey, data, len(data))

        # Reappend header that we saved earlier before returning to make the complete buffer
        return header + data


    def init(self, encxkey, key, validate, data):
        data_len = len(data)

        if data_len < 1:
            return None

        header_len = (data[0] ^ 0xec) + 2
        if data_len < header_len:
            return None

        data_start = (data[header_len - 1] ^ 0xea)
        if data_len < (header_len + data_start):
            return None

        data = self.enctypex_funcx(encxkey, bytearray(key), bytearray(validate), data[header_len:], data_start)
        return data[data_start:]


    def enctypex_funcx(self, encxkey, key, validate, data, datalen):
        keylen = len(key)

        for i in range(datalen):
            validate[(key[i % keylen] * i) & 7] ^= validate[i & 7] ^ data[i]

        self.func4(encxkey, validate, 8)
        return data

    def func4(self, encxkey, id, idlen):
        if idlen < 1:
            return

        for i in range(256):
            encxkey[i] = i

        n1 = 0
        n2 = 0
        for i in range(255,-1,-1):
            t1, n1, n2 = self.func5(encxkey, i, id, idlen, n1, n2)
            t2 = encxkey[i]
            encxkey[i] = encxkey[t1]
            encxkey[t1] = t2

        encxkey[256] = encxkey[1]
        encxkey[257] = encxkey[3]
        encxkey[258] = encxkey[5]
        encxkey[259] = encxkey[7]
        encxkey[260] = encxkey[n1 & 0xff]

    def func5(self, encxkey, cnt, id, idlen, n1, n2):
        if cnt == 0:
            return 0, n1, n2

        mask = 1
        doLoop = True
        if cnt > 1:
            while doLoop:
                mask = (mask << 1) + 1
                doLoop = mask < cnt

        i = 0
        tmp = 0
        doLoop = True
        while doLoop:
            n1 = encxkey[n1 & 0xff] + id[n2]
            n2 += 1

            if n2 >= idlen:
                n2 = 0
                n1 += idlen

            tmp = n1 & mask

            i += 1
            if i > 11:
                tmp %= cnt

            doLoop = tmp > cnt

        return tmp, n1, n2

    def func6(self, encxkey, data, data_len):
        for i in range(data_len):
            data[i] = self.func7(encxkey, data[i])
        return len(data)

    def func7(self, encxkey, d):
        a = encxkey[256]
        b = encxkey[257]
        c = encxkey[a]
        encxkey[256] = (a + 1) & 0xff
        encxkey[257] = (b + c) & 0xff

        a = encxkey[260]
        b = encxkey[257]
        b = encxkey[b]
        c = encxkey[a]
        encxkey[a] = b

        a = encxkey[259]
        b = encxkey[257]
        a = encxkey[a]
        encxkey[b] = a

        a = encxkey[256]
        b = encxkey[259]
        a = encxkey[a]
        encxkey[b] = a

        a = encxkey[256]
        encxkey[a] = c

        b = encxkey[258]
        a = encxkey[c]
        c = encxkey[259]
        b = (a + b) & 0xff
        encxkey[258] = b

        a = b
        c = encxkey[c]
        b = encxkey[257]
        b = encxkey[b]
        a = encxkey[a]
        c = (b + c) & 0xff
        b = encxkey[260]
        b = encxkey[b]
        c = (b + c) & 0xff
        b = encxkey[c]
        c = encxkey[256]
        c = encxkey[c]
        a = (a + c) & 0xff
        c = encxkey[b]
        b = encxkey[a]
        encxkey[260] = d

        c ^= b ^ d
        encxkey[259] = c

        return c

    def func6e(self, encxkey, data, data_len):
        for i in range(data_len):
            data[i] = self.func7e(encxkey, data[i])
        return len(data)

    def func7e(self, encxkey, d):
        a = encxkey[256]
        b = encxkey[257]
        c = encxkey[a]
        encxkey[256] = (a + 1) & 0xff
        encxkey[257] = (b + c) & 0xff

        a = encxkey[260]
        b = encxkey[257]
        b = encxkey[b]
        c = encxkey[a]
        encxkey[a] = b

        a = encxkey[259]
        b = encxkey[257]
        a = encxkey[a]
        encxkey[b] = a

        a = encxkey[256]
        b = encxkey[259]
        a = encxkey[a]
        encxkey[b] = a

        a = encxkey[256]
        encxkey[a] = c

        b = encxkey[258]
        a = encxkey[c]
        c = encxkey[259]
        b = (a + b) & 0xff
        encxkey[258] = b

        a = b
        c = encxkey[c]
        b = encxkey[257]
        b = encxkey[b]
        a = encxkey[a]
        c = (b + c) & 0xff
        b = encxkey[260]
        b = encxkey[b]
        c = (b + c) & 0xff
        b = encxkey[c]
        c = encxkey[256]
        c = encxkey[c]
        a = (a + c) & 0xff
        c = encxkey[b]
        b = encxkey[a]
        c ^= b ^ d
        encxkey[260] = c
        encxkey[259] = d

        return c