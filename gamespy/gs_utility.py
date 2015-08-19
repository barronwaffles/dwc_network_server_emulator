"""DWC Network Server Emulator

    Copyright (C) 2014 polaris-
    Copyright (C) 2014 ToadKing
    Copyright (C) 2014 AdmiralCurtiss
    Copyright (C) 2014 msoucy
    Copyright (C) 2015 Sepalani

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
import hashlib
import time

import other.utils as utils


def generate_secret_keys(filename="gslist.cfg"):
    """Generate list of secret keys based on a config file.

    gslist.cfg is the default config file and may be incomplete.
    TODO: Parse the config file in a cleaner way. (ex: using CSV module)
    """
    secret_key_list = {}
    with open(filename) as key_file:
        for line in key_file.readlines():
            # name = line[:54].strip()
            # Probably won't do anything with the name for now.
            id = line[54:54+19].strip()
            key = line[54+19:].strip()

            secret_key_list[id] = key

    return secret_key_list


def base64_encode(input):
    """Encode input in base64 using GameSpy variant.

    GameSpy uses a slightly modified version of base64 which replaces
    +/= with []_
    """
    output = base64.b64encode(input).replace('+', '[') \
                                    .replace('/', ']') \
                                    .replace('=', '_')
    return output


def base64_decode(input):
    """Decode input in base64 using GameSpy variant."""
    output = base64.b64decode(input.replace('[', '+')
                                   .replace(']', '/')
                                   .replace('_', '='))
    return output


def rc4_encrypt(_key, _data):
    """
    Tetris DS overlay 10 @ 0216E9B8
    """
    key = bytearray(_key)
    data = bytearray(_data)

    if len(key) == 0:
        # This shouldn't happen but it apparently can on a rare occasion.
        # Key should always be set.
        return

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
    for x, val in enumerate(data):
        # Modified RC4?
        i = (i + 1 + val) & 0xff
        j = (j + S[i]) & 0xff

        S[i], S[j] = S[j], S[i]

        data[x] ^= S[(S[i] + S[j]) & 0xff]

    return data


def prepare_rc4_base64(_key, _data):
    """Tetris DS overlay 10 @ 0216E9B8

    Used by the master server to send some data between the client and server.
    This seems to be what Luigi Auriemma calls "Gsmsalg".
    """
    data = rc4_encrypt(_key, _data)

    if data is None:
        data = bytearray()

    data.append(0)

    return base64.b64encode(buffer(data))


def parse_authtoken(authtoken, db):
    """Get the login data from nas.nintendowifi.net/ac from an authtoken"""
    return db.get_nas_login(authtoken)


def login_profile_via_parsed_authtoken(authtoken_parsed, db):
    """Return login profile via parsed authtoken.

    authtoken_parsed MUST HAVE userid field and can't be None!
    """
    if authtoken_parsed is None or 'userid' not in authtoken_parsed:
        return None, None, None, None
    console = 0
    userid = authtoken_parsed['userid']

    csnum = authtoken_parsed.get('csnum', '')      # Wii: Serial number
    cfc = authtoken_parsed.get('cfc', '')          # Wii: Friend code
    bssid = authtoken_parsed.get('bssid', '')      # NDS: Wifi network's BSSID
    devname = authtoken_parsed.get('devname', '')  # NDS: Device name
    birth = authtoken_parsed.get('birth', '')      # NDS: User's birthday

    # The Wii does not use passwd, so take another uniquely generated string
    # as the password.
    # if "passwd" in authtoken_parsed:
    #     password = authtoken_parsed['passwd']
    # else:
    #     password = authtoken_parsed['gsbrcd']
    #     console = 1

    if "passwd" not in authtoken_parsed:
        console = 1

    password = authtoken_parsed['gsbrcd']
    gsbrcd = authtoken_parsed['gsbrcd']
    gameid = gsbrcd[:4]
    macadr = authtoken_parsed['macadr']
    uniquenick = utils.base32_encode(int(userid)) + gsbrcd
    email = uniquenick + "@nds"  # The Wii also seems to use @nds.

    if "csnum" in authtoken_parsed:
        console = 1
    if "cfc" in authtoken_parsed:
        console = 1

    valid_user = db.check_user_exists(userid, gsbrcd)
    if valid_user is False:
        profileid = db.create_user(userid, password, email, uniquenick,
                                   gsbrcd, console, csnum, cfc, bssid,
                                   devname, birth, gameid, macadr)
    else:
        profileid = db.perform_login(userid, password, gsbrcd)

    return userid, profileid, gsbrcd, uniquenick


def generate_response(challenge, ac_challenge, secretkey, authtoken):
    """Generate a challenge response."""
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


def generate_proof(challenge, ac_challenge, secretkey, authtoken):
    """Generate a challenge proof.

    The proof is practically the same thing as the response, except it has
    the challenge and the secret key swapped.

    Maybe combine the two functions later?
    """
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


def get_friendcode_from_profileid(profileid, gameid):
    """
    Code: Tetris DS @ 02057A14
    """
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
    """Return profile ID from Friend Code."""
    # Get the lower 32 bits as the profile id
    profileid = friendcode & 0xffffffff
    return profileid


class EncTypeX:
    """Code from Luigi Auriemma's enctypex_decoder.c

    It's kind of sloppy in parts, but it works. Unless there's some issues
    then it'll probably not change any longer.
    """
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

        # Convert data from strings to byte arrays before use or else
        # it'll raise an error
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

        # The header of the data gets chopped off in init(), so save it
        header = data[:tmp_len]
        encxkey = bytearray([0] * 261)
        data = self.init(encxkey, key, validate, data)
        self.func6e(encxkey, data, len(data))

        # Reappend header that we saved earlier before returning to make
        # the complete buffer
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

        data = self.enctypex_funcx(
            encxkey,
            bytearray(key),
            bytearray(validate),
            data[header_len:],
            data_start
        )

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
        for i in range(255, -1, -1):
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
