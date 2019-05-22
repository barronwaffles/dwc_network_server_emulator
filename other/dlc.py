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
from datetime import date
from datetime import datetime
import json

from gamespy.gs_database import GamespyDatabase

# If a game from this list requests a file listing, the server will return
# that only one exists and return a random one.
# This is used for Mystery Gift distribution on Generation 4 Pokemon games
# Gen 4 Pokemon Games (for Mystery Gift Distribution)
# If a game from this list requests a file listing, the server will compare
# the client Nintendo DS's date setting to the list of Mystery Gifts
# that were actually distributed in real life at the given time.
# This way, if someone knows exactly when an event happened in real life,
# they know exactly which date to change to in order to receive
# a particular gift.
gen_4_pokemon_gamecodes = [
    'ADAE',
    'ADAP',
    'ADAF',
    'ADAD',
    'ADAI',
    'ADAS',
    'ADAJ',
    'ADAK',
    'APAE',
    'APAP',
    'APAF',
    'APAD',
    'APAI',
    'APAS',
    'APAJ',
    'APAK',
    'CPUE',
    'CPUP',
    'CPUF',
    'CPUD',
    'CPUI',
    'CPUS',
    'CPUJ',
    'CPUK',
    'IPKE',
    'IPKP',
    'IPKF',
    'IPKD',
    'IPKI',
    'IPKS',
    'IPKJ',
    'IPKK',
    'IPGE',
    'IPGP',
    'IPGF',
    'IPGD',
    'IPGI',
    'IPGS',
    'IPGJ',
    'IPGK'
]

filter_bit_g5 = {
    'A': 0x100000,
    'B': 0x200000,
    'D': 0x400000,
    'E': 0x800000
}


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

    def attrs(data):
        """Filter attrs."""
        def nc(a, b):
            """Filter nc."""
            return a is None or a == b
        return \
            len(data) == 6 and \
            nc(attr1, data[2]) and \
            nc(attr2, data[3]) and \
            nc(attr3, data[4])
    output = filter(lambda line: attrs(line.split("\t")), data.splitlines())

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


def todays_g4_event_filename(today, gamecd, dlc_path):
    event_filename = "null"

    gameid_map = {
        "ADA": "D",
        "APA": "P",
        "CPU": "T",
        "IPK": "G",
        "IPG": "S"
    }

    lang_map = {
        "E": "ENG",
        "P": "ENG",
        "F": "FRA",
        "D": "GER",
        "I": "ITA",
        "S": "SPN",
        "J": "JPN",
        "K": "KOR"
    }

    json_path = os.path.abspath(os.path.join(dlc_path, '..', 'g4_events.json'))
    event_db = json.loads(open(json_path).read())["events"]
    for event in event_db:
        if gamecd[-1:] in event["lang_subcodes"]:
            if gameid_map[gamecd[:3]] in event["valid_games"]:
                date_start = datetime.strptime(
                    event["date_start"], '%Y-%m-%d').date()
                date_end = datetime.strptime(
                    event["date_end"], '%Y-%m-%d').date()
                if date_start <= today <= date_end:
                    shortcodes = event["valid_games"]
                    if shortcodes == "DPTGS":
                        valid_games = "ALL"
                    elif shortcodes == "T":
                        valid_games = "Plat"
                    else:
                        valid_games = ""
                        for gamecode in event["valid_games"]:
                            if gamecode == "T":
                                valid_games += "Pt"
                            elif gamecode == "G":
                                valid_games += "HG"
                            elif gamecode == "S":
                                valid_games += "SS"
                            else:
                                valid_games += gamecode

                    event_filename = \
                        lang_map[gamecd[-1:]] + "_" + \
                        str(event["wc_id"]).zfill(3) + "_" + \
                        valid_games + "_" + \
                        event["shortname"] + ".myg"
    return event_filename


def filter_list_g4_mystery_gift(data, token, gamecd, dlc_path):
    try:
        userData = GamespyDatabase().get_nas_login(token)
        time_struct = time.strptime(userData['devtime'], '%y%m%d%H%M%S')
        ds_date = date(time_struct.tm_year,
                       time_struct.tm_mon, time_struct.tm_mday)
        event_filename = todays_g4_event_filename(ds_date, gamecd, dlc_path)
        if event_filename != "null":
            event_size = str(os.path.getsize(
                os.path.join(dlc_path, event_filename)))
            ret = event_filename + "\t\t\t\t\t" + event_size + '\r\n'
        else:
            files = data.splitlines()
            ret = files[(int(ds_date.tm_yday) - 1) % len(files)] + '\r\n'
    except:
        ret = filter_list_random_files(data, 1)
    return ret


def filter_list_g5_mystery_gift(data, rhgamecd):
    """Custom selection for generation 5 mystery gifts, so that the random
    or data-based selection still works properly."""
    if len(rhgamecd) < 2 or rhgamecd[2] not in filter_bit_g5:
        # unknown game, can't filter
        return data
    filter_bit = filter_bit_g5[rhgamecd[2]]

    output = []
    for line in data.splitlines():
        attrs = line.split('\t')
        if len(attrs) < 3:
            continue
        line_bits = int(attrs[3], 16)
        if line_bits & filter_bit == filter_bit:
            output.append(line)
    return '\r\n'.join(output) + '\r\n'


def safeloadfi(dlc_path, name, mode='rb'):
    """safeloadfi : string -> string

    Safely load contents of a file, given a filename,
    and closing the file afterward.
    """
    try:
        with open(os.path.join(dlc_path, name), mode) as f:
            return f.read()
    except:
        return None


def download_count(dlc_path, post):
    """Handle download count request."""
    gamecd = post["gamecd"]
    if gamecd in gen_4_pokemon_gamecodes:
        userData = GamespyDatabase().get_nas_login(post["token"])
        time_struct = time.strptime(userData['devtime'], '%y%m%d%H%M%S')
        ds_date = date(time_struct.tm_year,
                       time_struct.tm_mon, time_struct.tm_mday)
        event_filename = todays_g4_event_filename(ds_date, gamecd, dlc_path)
        if event_filename != "null":
            return "1"
        else:
            return "0"
    if os.path.exists(dlc_path):
        attr1 = post.get("attr1", None)
        attr2 = post.get("attr2", None)
        attr3 = post.get("attr3", None)
        if os.path.isfile(os.path.join(dlc_path, "_list.txt")):
            dlc_file = safeloadfi(dlc_path, "_list.txt")
            ls = filter_list(dlc_file, attr1, attr2, attr3)
            return "{}".format(get_file_count(ls))
        elif attr1 is None and attr2 is None and attr3 is None:
            return "{}".format(len(os.listdir(dlc_path)))
    return "0"


def download_size(dlc_path, name):
    """Return download filename and size.

    Used in download list.
    """
    return (name, str(os.path.getsize(os.path.join(dlc_path, name))))


def download_list(dlc_path, post):
    """Handle download list request.

    Look for a list file first. If the list file exists, send the
    entire thing back to the client.
    """
    # Get list file
    if not os.path.exists(dlc_path):
        return "\r\n"
    elif os.path.isfile(os.path.join(dlc_path, "_list.txt")):
        list_data = safeloadfi(dlc_path, "_list.txt") or "\r\n"
    else:
        # Doesn't have _list.txt file
        try:
            ls = [
                download_size(dlc_path, name)
                for name in sorted(os.listdir(dlc_path))
            ]
            list_data = "\r\n".join("\t\t\t\t\t".join(f) for f in ls) + "\r\n"
        except:
            return "\r\n"

    attr1 = post.get("attr1", None)
    attr2 = post.get("attr2", None)
    attr3 = post.get("attr3", None)

    if post["gamecd"].startswith("IRA") and attr1.startswith("MYSTERY"):
        # Pokemon BW Mystery Gifts, until we have a better solution for that
        ret = filter_list(list_data, attr1, attr2, attr3)
        ret = filter_list_g5_mystery_gift(ret, post["rhgamecd"])
        return filter_list_by_date(ret, post["token"])
    elif post["gamecd"] in gen_4_pokemon_gamecodes:
        # Pokemon Gen 4 Mystery Gifts
        # Uses dates defined in g4_events.json to distribute gifts
        ret = filter_list(list_data, attr1, attr2, attr3)
        return filter_list_g4_mystery_gift(
            ret,
            post["token"],
            post["gamecd"],
            dlc_path)
    else:
        # Default case for most games
        num = post.get("num", None)
        if num is not None:
            num = int(num)

        offset = post.get("offset", None)
        if offset is not None:
            offset = int(offset)

        return filter_list(list_data, attr1, attr2, attr3, num, offset)


def download_contents(dlc_path, post):
    """Handle download contents request.

    Get only the base filename just in case there is a path involved
    somewhere in the filename string.
    """
    contents = os.path.basename(post["contents"])
    return safeloadfi(dlc_path, contents)
