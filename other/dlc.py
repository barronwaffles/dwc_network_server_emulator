"""DWC Network Server Emulator

    Copyright (C) 2014 polaris-
    Copyright (C) 2014 ToadKing
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

import os
import random
import time

from gamespy.gs_database import GamespyDatabase


# If a game from this list requests a file listing, the server will return
# that only one exists and return a random one.
# This is used for Mystery Gift distribution on Generation 4 Pokemon games
gamecodes_return_random_file = [
    'ADAD',
    'ADAE',
    'ADAF',
    'ADAI',
    'ADAJ',
    'ADAK',
    'ADAS',
    'CPUD',
    'CPUE',
    'CPUF',
    'CPUI',
    'CPUJ',
    'CPUK',
    'CPUS',
    'IPGD',
    'IPGE',
    'IPGF',
    'IPGI',
    'IPGJ',
    'IPGK',
    'IPGS'
]


def get_file_count(data):
    return sum(1 for line in data.splitlines() if line)


def filter_list(data, attr1=None, attr2=None, attr3=None,
                num=None, offset=None):
    """Filter the list based on the attribute fields.

    If nothing matches, at least return a newline.
    Pokemon BW at least expects this and will error without it.
    """
    if attr1 is None and attr2 is None and attr3 is None and \
       num is None and offset is None:
        # Nothing to filter, just return the input data
        return data

    nc = lambda a, b: (a is None or a == b)
    attrs = lambda data: (len(data) == 6 and nc(attr1, data[2]) and
                          nc(attr2, data[3]) and nc(attr3, data[4]))
    output = filter(lambda line: attrs(line.split("\t")),
                    data.splitlines())

    if offset is not None:
        output = output[offset:]

    if num is not None:
        output = output[:num]

    return '\r\n'.join(output) + '\r\n'


def filter_list_random_files(data, count):
    """Get [count] random files from the filelist."""
    samples = random.sample(data.splitlines(), count)
    return '\r\n'.join(samples) + '\r\n'


def filter_list_by_date(data, token):
    """Allow user to control which file to receive by setting
    the local date selected file will be the one at
    index (day of year) mod (file count)."""
    try:
        userData = GamespyDatabase().get_nas_login(token)
        date = time.strptime(userData['devtime'], '%y%m%d%H%M%S')
        files = data.splitlines()
        ret = files[(int(date.tm_yday) - 1) % len(files)] + '\r\n'
    except:
        ret = filter_list_random_files(data, 1)
    return ret


def filter_list_g5_mystery_gift(data, rhgamecd):
    """Custom selection for generation 5 mystery gifts, so that the random
    or data-based selection still works properly."""
    if rhgamecd[2] == 'A':
        filterBit = 0x100000
    elif rhgamecd[2] == 'B':
        filterBit = 0x200000
    elif rhgamecd[2] == 'D':
        filterBit = 0x400000
    elif rhgamecd[2] == 'E':
        filterBit = 0x800000
    else:
        # unknown game, can't filter
        return data

    output = []
    for line in data.splitlines():
        lineBits = int(line.split('\t')[3], 16)
        if lineBits & filterBit == filterBit:
            output.append(line)
    return '\r\n'.join(output) + '\r\n'


def safeloadfi(dlc_path, name, mode='rb'):
    """safeloadfi : string -> string

    Safely load contents of a file, given a filename,
    and closing the file afterward.
    """
    with open(os.path.join(dlc_path, name), mode) as f:
        return f.read()
