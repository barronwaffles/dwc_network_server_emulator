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

import logging
import time
import traceback

from twisted.internet.protocol import Factory
from twisted.internet.endpoints import serverFromString
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning

import gamespy.gs_database as gs_database
import gamespy.gs_query as gs_query
import gamespy.gs_utility as gs_utils
import other.utils as utils
import dwc_config

logger = dwc_config.get_logger('GameSpyGamestatsServer')
address = dwc_config.get_ip_port('GameSpyGamestatsServer')


class GameSpyGamestatsServer(object):
    def __init__(self):
        pass

    def start(self):
        endpoint_search = serverFromString(
            reactor,
            "tcp:%d:interface=%s" % (address[1], address[0])
        )
        conn_search = endpoint_search.listen(GamestatsFactory())

        try:
            if not reactor.running:
                reactor.run(installSignalHandlers=0)
        except ReactorAlreadyRunning:
            pass


class GamestatsFactory(Factory):
    def __init__(self):
        logger.log(logging.INFO,
                   "Now listening for connections on %s:%d...",
                   address[0], address[1])
        self.sessions = {}

    def buildProtocol(self, address):
        return Gamestats(self.sessions, address)


class Gamestats(LineReceiver):
    def __init__(self, sessions, address):
        self.setRawMode()  # We're dealing with binary data so set to raw mode

        self.db = gs_database.GamespyDatabase()

        self.sessions = sessions
        self.address = address
        # Stores any unparsable/incomplete commands until the next
        # rawDataReceived
        self.remaining_message = ""

        self.session = ""
        self.gameid = ""

        self.lid = "0"

        self.data = ""

    def log(self, level, msg, *args, **kwargs):
        if not self.session:
            if not self.gameid:
                logger.log(level, "[%s:%d] " + msg,
                           self.address.host, self.address.port,
                           *args, **kwargs)
            else:
                logger.log(level, "[%s:%d | %s] " + msg,
                           self.address.host, self.address.port, self.gameid,
                           *args, **kwargs)
        else:
            if not self.gameid:
                logger.log(level, "[%s:%d | %s] " + msg,
                           self.address.host, self.address.port, self.session,
                           *args, **kwargs)
            else:
                logger.log(level, "[%s:%d | %s | %s] " + msg,
                           self.address.host, self.address.port, self.session,
                           self.gameid, *args, **kwargs)

    def connectionMade(self):
        try:
            self.log(logging.INFO,
                     "Received connection from %s:%d",
                     self.address.host, self.address.port)

            # Generate a random challenge string
            self.challenge = utils.generate_random_str(
                10, "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            )

            # The first command sent to the client is always a login challenge
            # containing the server challenge key.
            msg = gs_query.create_gamespy_message([
                ('__cmd__', "lc"),
                ('__cmd_val__', "1"),
                ('challenge', self.challenge),
                ('id', "1"),
            ])

            self.log(logging.DEBUG, "SENDING: '%s'...", msg)

            msg = self.crypt(msg)
            self.transport.write(bytes(msg))
        except:
            self.log(logging.ERROR,
                     "Unknown exception: %s",
                     traceback.format_exc())

    def connectionLost(self, reason):
        return

    def rawDataReceived(self, data):
        try:
            # Decrypt packet
            self.remaining_message += data

            if "\\final\\" not in data:
                return

            msg = str(self.crypt(self.remaining_message))
            self.data = msg
            self.remaining_message = ""

            commands, self.remaining_message = \
                gs_query.parse_gamespy_message(msg)
            logger.log(logging.DEBUG, "STATS RESPONSE: %s", msg)

            cmds = {
                "auth":    self.perform_auth,
                "authp":   self.perform_authp,
                "ka":      self.perform_ka,
                "setpd":   self.perform_setpd,
                "getpd":   self.perform_getpd,
                "newgame": self.perform_newgame,
                "updgame": self.perform_updgame,
            }

            def cmd_err(data_parsed):
                logger.log(logging.DEBUG,
                           "Found unknown command, don't know how to"
                           " handle '%s'.", data_parsed['__cmd__'])

            for data_parsed in commands:
                print(data_parsed)

                cmds.get(data_parsed['__cmd__'], cmd_err)(data_parsed)
        except:
            self.log(logging.ERROR,
                     "Unknown exception: %s",
                     traceback.format_exc())

    def perform_auth(self, data_parsed):
        self.log(logging.DEBUG, "%s", "Parsing 'auth'...")

        if "gamename" in data_parsed:
            self.gameid = data_parsed['gamename']

        self.session = utils.generate_random_number_str(10)

        msg = gs_query.create_gamespy_message([
            ('__cmd__', "lc"),
            ('__cmd_val__', "2"),
            ('sesskey', self.session),
            ('proof', 0),
            ('id', "1"),
        ])

        self.log(logging.DEBUG, "SENDING: '%s'...", msg)

        msg = self.crypt(msg)
        self.transport.write(bytes(msg))

    def perform_authp(self, data_parsed):
        authtoken_parsed = gs_utils.parse_authtoken(data_parsed['authtoken'],
                                                    self.db)
        # print authtoken_parsed

        if "lid" in data_parsed:
            self.lid = data_parsed['lid']

        userid, profileid, gsbrcd, uniquenick = \
            gs_utils.login_profile_via_parsed_authtoken(authtoken_parsed,
                                                        self.db)

        if profileid is not None:
            # Successfully logged in or created account, continue
            # creating session.
            sesskey = self.db.create_session(profileid, '')
            self.sessions[profileid] = self
            self.profileid = int(profileid)

            msg = gs_query.create_gamespy_message([
                ('__cmd__', "pauthr"),
                ('__cmd_val__', profileid),
                ('lid', self.lid),
            ])
        else:
            # login failed
            self.log(logging.WARNING, "Invalid password")
            msg = gs_query.create_gamespy_message([
                ('__cmd__', "pauthr"),
                ('__cmd_val__', -3),
                ('lid', self.lid),
                ('errmsg', 'Invalid Validation'),
            ])

        self.log(logging.DEBUG, "SENDING: '%s'...", msg)

        msg = self.crypt(msg)
        self.transport.write(bytes(msg))

    def perform_ka(self, data_parsed):
        msg = gs_query.create_gamespy_message([
            ('__cmd__', "ka"),
            ('__cmd_val__', ""),
        ])

        self.log(logging.DEBUG, "SENDING: '%s'...", msg)

        msg = self.crypt(msg)
        self.transport.write(bytes(msg))
        return

    def perform_setpd(self, data_parsed):
        data = self.data

        msg = gs_query.create_gamespy_message([
            ('__cmd__', "setpdr"),
            ('__cmd_val__', 1),
            ('lid', self.lid),
            ('pid', self.profileid),
            ('mod', int(time.time())),
        ])

        self.log(logging.DEBUG, "SENDING: '%s'...", msg)

        msg = self.crypt(msg)
        self.transport.write(bytes(msg))

        # TODO: Return error message.
        if int(data_parsed['pid']) != self.profileid:
            logger.log(logging.WARNING,
                       "ERROR: %d tried to update %d's profile",
                       int(data_parsed['pid']), self.profileid)
            return

        data_str = "\\data\\"
        length = int(data_parsed['length'])

        if len(data) < length:
            # The packet isn't complete yet, keep loop until we get the
            # entire packet. The length entire packet SHOULD always be
            # greater than the data field, so this check should be fine.
            return

        if data_str in data:
            idx = data.index(data_str) + len(data_str)
            data = data[idx:idx + length].rstrip("\\")
        else:
            logger.log(logging.ERROR,
                       "ERROR: Could not find \data\ in setpd command: %s",
                       data)
            data = ""

        current_data = self.db.pd_get(self.profileid,
                                      data_parsed['dindex'],
                                      data_parsed['ptype'])
        if current_data and data and 'data' in current_data:
            current_data = current_data['data'].lstrip('\\').split('\\')
            new_data = data.lstrip('\\').split('\\')

            current_data = dict(zip(current_data[0::2],
                                    current_data[1::2]))
            new_data = dict(zip(new_data[0::2], new_data[1::2]))
            for k in new_data.keys():
                current_data[k] = new_data[k]

            # TODO: use str.join()
            data = "\\"
            for k in current_data.keys():
                data += k + "\\" + current_data[k] + "\\"
            data = data.rstrip("\\")  # Don't put trailing \ into db

        self.db.pd_insert(self.profileid,
                          data_parsed['dindex'],
                          data_parsed['ptype'],
                          data)

    def perform_getpd(self, data_parsed):
        pid = int(data_parsed['pid'])
        profile = self.db.pd_get(pid,
                                 data_parsed['dindex'],
                                 data_parsed['ptype'])

        if profile is None:
            self.log(logging.WARNING,
                     "Could not find profile for %d %s %s",
                     pid, data_parsed['dindex'], data_parsed['ptype'])

        keys = data_parsed['keys'].split('\x01')

        profile_data = None
        data = ""

        # Someone figure out if this is actually a good way to handle this
        # when no profile is found
        if profile is not None and 'data' in profile:
            profile_data = profile['data']
            if profile_data.endswith("\\"):
                profile_data = profile_data[:-1]
            profile_data = \
                gs_query.parse_gamespy_message("\\prof\\" + profile_data +
                                               "\\final\\")

            if profile_data is not None:
                profile_data = profile_data[0][0]
            else:
                self.log(logging.WARNING,
                         "Could not get data section from profile for %d",
                         pid)

            if len(keys):
                # TODO: more clean/pythonic way to do (join?)
                for key in keys:
                    if key in ("__cmd__", "__cmd_val__", ""):
                        continue
                    data += "\\" + key + "\\"

                    if profile_data is not None and key in profile_data:
                        data += profile_data[key]
            else:
                self.log(logging.WARNING,
                         "No keys requested, defaulting to all keys: %s",
                         profile['data'])
                data = profile['data']

        modified = int(time.time())

        # Check if there is a nul byte and data after it
        data_blocks = data.split('\x00')
        if len(data_blocks) > 1 and any(block for block in data_blocks[1:]):
            self.log(logging.WARNING, "Data after nul byte: %s", data)

        data = data_blocks[0]
        msg = gs_query.create_gamespy_message([
            ('__cmd__', "getpdr"),
            ('__cmd_val__', 1),
            ('lid', self.lid),
            ('pid', pid),
            ('mod', modified),
            ('length', len(data)),
            ('data', ''),
            (data,)
        ])

        if msg.count('\\') % 2:
            # An empty field must be terminated by \ before \final\
            msg = msg.replace("\\final\\", "\\\\final\\")

        self.log(logging.DEBUG, "SENDING: '%s'...", msg)
        msg = self.crypt(msg)
        self.transport.write(bytes(msg))

    def perform_newgame(self, data_parsed):
        # No op
        return

    def perform_updgame(self, data_parsed):
        # No op
        return

    def crypt(self, data):
        key = bytearray(b"GameSpy3D")
        key_len = len(key)
        output = bytearray(data.encode("ascii"))

        if "\\final\\" in output:
            end = output.index("\\final\\")
        else:
            end = len(output)

        for i in range(end):
            output[i] ^= key[i % key_len]

        return output


if __name__ == "__main__":
    gsss = GameSpyGamestatsServer()
    gsss.start()
