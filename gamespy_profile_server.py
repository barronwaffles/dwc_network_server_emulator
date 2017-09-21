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

logger = dwc_config.get_logger('GameSpyProfileServer')
address = dwc_config.get_ip_port('GameSpyProfileServer')


class GameSpyProfileServer(object):
    def __init__(self):
        pass

    def start(self):
        endpoint = serverFromString(
            reactor,
            "tcp:%d:interface=%s" % (address[1], address[0])
        )
        conn = endpoint.listen(PlayerFactory())

        try:
            if not reactor.running:
                reactor.run(installSignalHandlers=0)
        except ReactorAlreadyRunning:
            pass


class PlayerFactory(Factory):
    def __init__(self):
        """Player Factory.

        Instead of storing the sessions in the database, it might make more
        sense to store them in the PlayerFactory.
        """
        logger.log(logging.INFO,
                   "Now listening for connections on %s:%d...",
                   address[0], address[1])
        self.sessions = {}

    def buildProtocol(self, address):
        return PlayerSession(self.sessions, address)


class PlayerSession(LineReceiver):
    def __init__(self, sessions, address):
        self.setRawMode()  # We're dealing with binary data so set to raw mode

        self.db = gs_database.GamespyDatabase()

        self.sessions = sessions
        self.address = address
        # Stores any unparsable/incomplete commands until the next
        # rawDataReceived
        self.remaining_message = ""

        self.profileid = 0
        self.gameid = ""

        self.buddies = []
        self.blocked = []

        self.status = ""
        self.statstring = ""
        self.locstring = ""

        self.keepalive = int(time.time())
        self.sesskey = ""

        self.sdkrevision = "0"

    def log(self, level, msg, *args, **kwargs):
        if not self.profileid:
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
                logger.log(level, "[%s:%d | %d] " + msg,
                           self.address.host, self.address.port,
                           self.profileid, *args, **kwargs)
            else:
                logger.log(level, "[%s:%d | %d | %s] " + msg,
                           self.address.host, self.address.port,
                           self.profileid, self.gameid, *args, **kwargs)

    def get_ip_as_int(self, address):
        ipaddress = 0

        if address is not None:
            for n in address.split('.'):
                ipaddress = (ipaddress << 8) | int(n)

        return ipaddress

    def connectionMade(self):
        try:
            self.transport.setTcpKeepAlive(1)

            self.log(logging.INFO,
                     "Received connection from %s:%d",
                     self.address.host, self.address.port)

            # Create new session id
            self.session = ""

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
            self.transport.write(bytes(msg))
        except:
            self.log(logging.ERROR,
                     "Unknown exception: %s",
                     traceback.format_exc())

    def connectionLost(self, reason):
        try:
            self.log(logging.INFO, "%s", "Client disconnected")

            self.status = "0"
            self.statstring = "Offline"
            self.locstring = ""
            self.send_status_to_friends()

            if self.profileid in self.sessions:
                del self.sessions[self.profileid]

            self.db.delete_session(self.sesskey)
            self.log(logging.INFO, "Deleted session %s", self.session)
        except:
            self.log(logging.ERROR,
                     "Unknown exception: %s",
                     traceback.format_exc())

    def rawDataReceived(self, data):
        try:
            self.log(logging.DEBUG, "RESPONSE: '%s'...", data)

            # In the case where command string is too big to fit into one
            # read, any parts that could not be successfully parsed are
            # stored in the variable remaining_message. On the next
            # rawDataReceived command, the remaining message and the data
            # are combined to create a full command.
            data = self.remaining_message + data

            # Check to make sure the data buffer starts with a valid command.
            if len(data) > 0 and data[0] != '\\':
                # There is data in the buffer but it doesn't start with a \ so
                # there's no chance of it being valid. Look for the first
                # instance of \final\ and remove everything before it. If
                # \final\ is not in the command string then ignore it.
                final = "\\final\\"
                data = data[data.index(final) + len(final):] \
                    if final in data else ""

            commands, self.remaining_message = \
                gs_query.parse_gamespy_message(data)

            cmds = {
                "login": self.perform_login,
                "logout": self.perform_logout,
                "getprofile": self.perform_getprofile,
                "updatepro": self.perform_updatepro,
                "ka": self.perform_ka,
                "status": self.perform_status,
                "bm": self.perform_bm,
                "addbuddy": self.perform_addbuddy,
                "delbuddy": self.perform_delbuddy,
                "authadd": self.perform_authadd,
            }

            def cmd_err(data_parsed):
                # Maybe write unknown commands to a separate file later so
                # new data can be collected more easily?
                self.log(logging.ERROR,
                         "Found unknown command, don't know how to handle"
                         " '%s'.", data_parsed['__cmd__'])

            for data_parsed in commands:
                # self.log(-1, data_parsed)
                self.log(logging.DEBUG, "%s", data_parsed)
                cmds.get(data_parsed['__cmd__'], cmd_err)(data_parsed)
        except:
            self.log(logging.ERROR,
                     "Unknown exception: %s",
                     traceback.format_exc())

    def perform_login(self, data_parsed):
        authtoken_parsed = gs_utils.parse_authtoken(data_parsed['authtoken'],
                                                    self.db)

        if authtoken_parsed is None:
            self.log(logging.WARNING, "%s", "Invalid Authtoken.")
            msg = gs_query.create_gamespy_message([
                ('__cmd__', "error"),
                ('__cmd_val__', ""),
                ('err', '266'),
                ('fatal', ''),
                ('errmsg', 'There was an error validating the'
                           ' pre-authentication.'),
                ('id', data_parsed['id']),
            ])
            self.transport.write(bytes(msg))
            return

        if 'sdkrevision' in data_parsed:
            self.sdkrevision = data_parsed['sdkrevision']

        # Verify the client's response
        valid_response = gs_utils.generate_response(
            self.challenge,
            authtoken_parsed['challenge'],
            data_parsed['challenge'],
            data_parsed['authtoken']
        )
        if data_parsed['response'] != valid_response:
            self.log(logging.ERROR,
                     "ERROR: Got invalid response."
                     " Got %s, expected %s",
                     data_parsed['response'], valid_response)

        proof = gs_utils.generate_proof(
            self.challenge,
            authtoken_parsed['challenge'],
            data_parsed['challenge'],
            data_parsed['authtoken']
        )

        userid, profileid, gsbrcd, uniquenick = \
            gs_utils.login_profile_via_parsed_authtoken(authtoken_parsed,
                                                        self.db)

        if profileid is not None:
            # Successfully logged in or created account, continue
            # creating session.
            loginticket = gs_utils.base64_encode(
                utils.generate_random_str(16)
            )
            self.sesskey = self.db.create_session(profileid, loginticket)

            self.sessions[profileid] = self

            self.buddies = self.db.get_buddy_list(self.profileid)
            self.blocked = self.db.get_blocked_list(self.profileid)

            if self.sdkrevision == "11":  # Used in Tatsunoko vs Capcom
                def make_list(data):
                    return [str(d['buddyProfileId'])
                            for d in data
                            if d['status'] == 1]

                block_list = make_list(self.blocked)
                msg = gs_query.create_gamespy_message([
                    ('__cmd__', "blk"),
                    ('__cmd_val__', str(len(block_list))),
                    ('list', ','.join(block_list)),
                ])

                self.log(logging.DEBUG, "SENDING: %s", msg)
                self.transport.write(bytes(msg))

                buddy_list = make_list(self.buddies)
                msg = gs_query.create_gamespy_message([
                    ('__cmd__', "bdy"),
                    ('__cmd_val__', str(len(buddy_list))),
                    ('list', ','.join(buddy_list)),
                ])

                self.log(logging.DEBUG, "SENDING: %s", msg)
                self.transport.write(bytes(msg))

            msg = gs_query.create_gamespy_message([
                ('__cmd__', "lc"),
                ('__cmd_val__', "2"),
                ('sesskey', self.sesskey),
                ('proof', proof),
                ('userid', userid),
                ('profileid', profileid),
                ('uniquenick', uniquenick),
                # Some kind of token... don't know it gets used or generated,
                # but it doesn't seem to have any negative effects if it's
                # not properly generated.
                ('lt', loginticket),
                ('id', data_parsed['id']),
            ])

            # Take the first 4 letters of gsbrcd instead of gamecd because
            # they should be consistent across game regions. For example, the
            # US version of Metroid Prime Hunters has the gamecd "AMHE" and
            # the first 4 letters of gsbrcd are "AMHE". However, the Japanese
            # version of Metroid Prime Hunters has the gamecd "AMHJ" with the
            # first 4 letters of bsbrcd as "AMHE". Tetris DS is the other way,
            # with the first 4 letters as the Japanese version (ATRJ) while
            # the gamecd is region specific (ATRE for US and ATRJ for JP).
            # gameid is used to send all people on the player's friends list a
            # status updates, so don't make it region specific.
            self.gameid = gsbrcd[:4]
            self.profileid = int(profileid)

            self.log(logging.DEBUG, "SENDING: %s", msg)
            self.transport.write(bytes(msg))

            # Get pending messages.
            self.get_pending_messages()

            # Send any friend statuses when the user logs in.
            # This will allow the user to see if their friends are hosting a
            # game as soon as they log in.
            self.get_status_from_friends()
            self.send_status_to_friends()

            # profile = self.db.get_profile_from_profileid(profileid)
            # if profile is not None:
            #     self.statstring = profile['stat']
            #     self.locstring = profile['loc']
        else:
            self.log(logging.INFO, "%s", "Invalid password or banned user")
            msg = gs_query.create_gamespy_message([
                ('__cmd__', "error"),
                ('__cmd_val__', ""),
                ('err', '256'),
                ('fatal', ''),
                ('errmsg', 'Login failed.'),
                ('id', data_parsed['id']),
            ])
            self.log(logging.DEBUG, "SENDING: %s", msg)
            self.transport.write(bytes(msg))

    def perform_logout(self, data_parsed):
        self.log(logging.INFO,
                 "Session %s has logged off",
                 data_parsed['sesskey'])
        self.db.delete_session(data_parsed['sesskey'])

        if self.profileid in self.sessions:
            del self.sessions[self.profileid]

        self.transport.loseConnection()

    def perform_getprofile(self, data_parsed):
        # profile = self.db.get_profile_from_session_key(
        #     data_parsed['sesskey']
        # )
        profile = self.db.get_profile_from_profileid(data_parsed['profileid'])

        # Wii example:
        # \pi\\profileid\474888031\nick\5pde5vhn1WR9E2g1t533\userid\442778352
        # \email\5pde5vhn1WR9E2g1t533@nds\sig\b126556e5ee62d4da9629dfad0f6b2a8
        # \uniquenick\5pde5vhn1WR9E2g1t533\pid\11\lon\0.000000\lat\0.000000
        # \loc\\id\2\final\
        sig = utils.generate_random_hex_str(32)

        msg_d = [
            ('__cmd__', "pi"),
            ('__cmd_val__', ""),
            ('profileid', profile['profileid']),
            ('nick', profile['uniquenick']),
            ('userid', profile['userid']),
            ('email', profile['email']),
            ('sig', sig),
            ('uniquenick', profile['uniquenick']),
            ('pid', profile['pid']),
        ]

        if profile['firstname']:
            # Wii gets a firstname
            msg_d.append(('firstname', profile['firstname']))

        if profile['lastname']:
            msg_d.append(('lastname', profile['lastname']))

        msg_d.extend([
            ('lon', profile['lon']),
            ('lat', profile['lat']),
            ('loc', profile['loc']),
            ('id', data_parsed['id']),
        ])
        msg = gs_query.create_gamespy_message(msg_d)

        self.log(logging.DEBUG, "SENDING: %s", msg)
        self.transport.write(bytes(msg))

    def perform_updatepro(self, data_parsed):
        """Wii example:
        \updatepro\\sesskey\199714190\firstname\Wii:2555151656076614@WR9E
        \partnerid\11\final\

        Remove any fields not related to what we should be updating.
        To avoid any crashes, make sure the key is actually in the dictionary
        before removing it.
        """
        if "__cmd__" in data_parsed:
            data_parsed.pop('__cmd__')
        if "__cmd_val__" in data_parsed:
            data_parsed.pop('__cmd_val__')
        if "updatepro" in data_parsed:
            data_parsed.pop('updatepro')
        if "partnerid" in data_parsed:
            data_parsed.pop('partnerid')
        if "sesskey" in data_parsed:
            data_parsed.pop('sesskey')

        # Create a list of fields to be updated.
        for f in data_parsed:
            self.db.update_profile(self.profileid, (f, data_parsed[f]))

    def perform_ka(self, data_parsed):
        self.keepalive = int(time.time())

        msg = gs_query.create_gamespy_message([
            ('__cmd__', "ka"),
            ('__cmd_val__', ""),
        ])
        self.transport.write(msg)

    def perform_status(self, data_parsed):
        self.sesskey = data_parsed['sesskey']
        self.status = data_parsed['__cmd_val__']
        self.statstring = data_parsed['statstring']
        self.locstring = data_parsed['locstring']

        # Send authorization requests to client
        self.get_buddy_requests()

        # Send authorizationed message to client
        self.get_buddy_authorized()

        self.send_status_to_friends()

    def perform_bm(self, data_parsed):
        # Message to/from clients?
        if data_parsed['__cmd_val__'] in ("1", "5", "102", "103"):
            if "t" in data_parsed:
                # Send message to the profile id in "t"
                dest_profileid = int(data_parsed['t'])
                dest_profile_buddies = self.db.get_buddy_list(dest_profileid)
                dest_msg = data_parsed['msg']

                not_buddies = False

                # Check if the user is buddies with the target user before
                # sending message.
                if not_buddies:
                    for buddy in self.buddies:
                        if buddy['userProfileId'] == dest_profileid:
                            not_buddies = True
                            break

                if not_buddies:
                    for buddy in dest_profile_buddies:
                        if buddy['userProfileId'] == self.profile:
                            not_buddies = True
                            break

                # Send error to user if they tried to send a message to
                # someone who isn't a buddy.
                if not_buddies:
                    msg = gs_query.create_gamespy_message([
                        ('__cmd__', "error"),
                        ('__cmd_val__', ""),
                        ('err', 2305),
                        ('errmsg',
                         "The profile the message was to be sent to is not"
                         " a buddy."),
                        ('id', 1),
                    ])
                    logger.log(logging.DEBUG,
                               "Trying to send message to someone who isn't"
                               " a buddy: %s", msg)
                    self.transport.write(msg)
                    return

                msg = gs_query.create_gamespy_message([
                    ('__cmd__', "bm"),
                    ('__cmd_val__', "1"),
                    ('f', self.profileid),
                    ('msg', dest_msg),
                ])

                if dest_profileid in self.sessions:
                    self.log(logging.DEBUG,
                             "SENDING TO %s:%s: %s",
                             self.sessions[dest_profileid].address.host,
                             self.sessions[dest_profileid].address.port, msg)
                    self.sessions[dest_profileid].transport.write(bytes(msg))
                    self.send_status_to_friends(dest_profileid)
                    self.get_status_from_friends(dest_profileid)
                else:
                    if data_parsed['__cmd_val__'] == "1":
                        self.log(logging.DEBUG,
                                 "Saving message to %d: %s",
                                 dest_profileid, msg)
                        self.db.save_pending_message(self.profileid,
                                                     dest_profileid, msg)
                    else:
                        msg = gs_query.create_gamespy_message([
                            ('__cmd__', "error"),
                            ('__cmd_val__', ""),
                            ('err', 2307),
                            ('errmsg', "The buddy to send a message to"
                             " is offline."),
                            ('id', 1),
                        ])
                        logger.log(logging.DEBUG,
                                   "Trying to send message to someone who"
                                   " isn't online: %s", msg)
                        self.transport.write(msg)

    def perform_addbuddy(self, data_parsed):
        newprofileid = int(data_parsed['newprofileid'])
        if newprofileid == self.profileid:
            logger.log(logging.DEBUG,
                       "Can't add self as friend: %d == %d",
                       newprofileid, self.profileid)
            return

        # Sample:
        # \addbuddy\\sesskey\231601763\newprofileid\476756820\reason\\final\
        self.buddies = self.db.get_buddy_list(self.profileid)

        buddy_exists = False
        for buddy in self.buddies:
            if buddy['buddyProfileId'] == newprofileid:
                buddy_exists = True
                break

        if not buddy_exists:
            self.db.add_buddy(self.profileid, newprofileid)

            if newprofileid in self.sessions:
                logger.log(logging.DEBUG,
                           "User is online, sending direct request from"
                           " profile id %d to profile id %d...",
                           self.profileid, newprofileid)

                # TODO: Add a way to check if a profile id is already a buddy
                # using SQL
                other_player_authorized = False
                target_buddy_list = self.db.get_buddy_list(newprofileid)
                logger.log(logging.DEBUG, "%s", target_buddy_list)
                for buddy in target_buddy_list:
                    if buddy['buddyProfileId'] == self.profileid and \
                       not buddy['blocked']:
                        other_player_authorized = True
                        break

                if other_player_authorized:
                    logger.log(logging.DEBUG,
                               "Automatic authorization: %d (target) already"
                               " has %d (source) as a friend.",
                               newprofileid, self.profileid)

                    # Force them both to add each other
                    self.send_buddy_request(self.sessions[newprofileid],
                                            self.profileid)
                    self.send_buddy_request(self.sessions[self.profileid],
                                            newprofileid)

                    self.send_bm4(newprofileid)

                    self.db.auth_buddy(newprofileid, self.profileid)
                    self.db.auth_buddy(self.profileid, newprofileid)

                    self.send_status_to_friends(newprofileid)
                    self.get_status_from_friends(newprofileid)

                else:
                    self.send_buddy_request(self.sessions[newprofileid],
                                            self.profileid)
        else:
            # Trying to add someone who is already a friend.
            # Just send status updates.
            self.send_status_to_friends(newprofileid)
            self.get_status_from_friends(newprofileid)

        self.buddies = self.db.get_buddy_list(self.profileid)

    def send_bm4(self, playerid):
        date = int(time.time())
        msg = gs_query.create_gamespy_message([
            ('__cmd__', "bm"),
            ('__cmd_val__', "4"),
            ('f', playerid),
            ('date', date),
            ('msg', ""),
        ])

        self.transport.write(bytes(msg))

    def perform_delbuddy(self, data_parsed):
        """Sample:
        \delbuddy\\sesskey\61913621\delprofileid\1\final\
        """
        self.db.delete_buddy(self.profileid, int(data_parsed['delprofileid']))
        self.buddies = self.db.get_buddy_list(self.profileid)

    def perform_authadd(self, data_parsed):
        """Authorize the other person's friend request.

        Sample:
        \authadd\\sesskey\231587549\fromprofileid\217936895
        \sig\f259f26d3273f8bda23c7c5e4bd8c5aa\final\
        """
        target_profile = int(data_parsed['fromprofileid'])
        self.db.auth_buddy(target_profile, self.profileid)
        self.get_buddy_authorized()
        self.buddies = self.db.get_buddy_list(self.profileid)

        self.send_bm4(target_profile)

        self.send_status_to_friends(target_profile)
        self.get_status_from_friends(target_profile)

    def send_status_to_friends(self, buddy_profileid=None):
        """TODO: Cache buddy list so we don't have to query the
        database every time."""
        self.buddies = self.db.get_buddy_list(self.profileid)

        if self.status == "0" and self.statstring == "Offline":
            # Going offline, don't need to send the other information.
            status_msg = "|s|%s|ss|%s" % (self.status, self.statstring)
        else:
            status_msg = "|s|%s|ss|%s|ls|%s|ip|%d|p|0|qm|0" % (
                self.status, self.statstring, self.locstring,
                self.get_ip_as_int(self.address.host)
            )

        msg = gs_query.create_gamespy_message([
            ('__cmd__', "bm"),
            ('__cmd_val__', "100"),
            ('f', self.profileid),
            ('msg', status_msg),
        ])

        buddy_list = self.buddies
        if buddy_profileid is not None:
            buddy_list = [{"buddyProfileId": buddy_profileid}]

        for buddy in buddy_list:
            if buddy['buddyProfileId'] in self.sessions:
                # self.log(logging.DEBUG,
                #          "Sending status to buddy id %s (%s:%d): %s",
                #          str(buddy['buddyProfileId']),
                #          self.sessions[
                #              buddy['buddyProfileId']
                #          ].address.host,
                #          self.sessions[
                #              buddy['buddyProfileId']
                #          ].address.port, msg)
                self.sessions[buddy['buddyProfileId']].transport \
                                                      .write(bytes(msg))

    def get_status_from_friends(self, buddy_profileid=None):
        """This will be called when the player logs in.

        Grab the player's buddy list and check the current sessions to
        see if anyone is online. If they are online, make them send an update
        to the calling client.
        """
        self.buddies = self.db.get_buddy_list(self.profileid)

        buddy_list = self.buddies
        if buddy_profileid is not None:
            buddy_list = [{"buddyProfileId": buddy_profileid}]

        for buddy in self.buddies:
            if buddy['status'] != 1:
                continue

            if buddy['buddyProfileId'] in self.sessions and \
               self.sessions[buddy['buddyProfileId']].gameid == self.gameid:
                status_msg = "|s|%s|ss|%s|ls|%s|ip|%d|p|0|qm|0" % (
                    self.sessions[buddy['buddyProfileId']].status,
                    self.sessions[buddy['buddyProfileId']].statstring,
                    self.sessions[buddy['buddyProfileId']].locstring,
                    self.get_ip_as_int(self.sessions[
                        buddy['buddyProfileId']
                    ].address.host))
            else:
                status_msg = "|s|0|ss|Offline"

            msg = gs_query.create_gamespy_message([
                ('__cmd__', "bm"),
                ('__cmd_val__', "100"),
                ('f', buddy['buddyProfileId']),
                ('msg', status_msg),
            ])

            self.transport.write(bytes(msg))

    def get_buddy_authorized(self):
        buddies = self.db.buddy_need_auth_message(self.profileid)

        for buddy in buddies:
            msg = gs_query.create_gamespy_message([
                ('__cmd__', "bm"),
                ('__cmd_val__', "1"),
                ('f', buddy['userProfileId']),
                ('msg', "I have authorized your request to add me to"
                 " your list"),
            ])

            self.transport.write(bytes(msg))
            self.db.buddy_sent_auth_message(buddy['userProfileId'],
                                            buddy['buddyProfileId'])

    def get_buddy_requests(self):
        """Get list people who have added the user but haven't been accepted
        yet."""
        buddies = self.db.get_pending_buddy_requests(self.profileid)

        for buddy in buddies:
            self.send_buddy_request(self,
                                    buddy['userProfileId'],
                                    buddy['time'])

    def send_buddy_request(self, session, profileid, senttime=None):
        sig = utils.generate_random_hex_str(32)
        msg = "\r\n\r\n"
        msg += "|signed|" + sig

        if senttime is None:
            senttime = int(time.time())

        msg = gs_query.create_gamespy_message([
            ('__cmd__', "bm"),
            ('__cmd_val__', "2"),
            ('f', profileid),
            ('date', senttime),
            ('msg', msg),
        ])

        session.transport.write(bytes(msg))

    def get_pending_messages(self):
        messages = self.db.get_pending_messages(self.profileid)

        for message in messages:
            if message['sourceid'] not in self.blocked:
                try:
                    self.transport.write(bytes(message['msg']))
                except:
                    self.transport.write(bytes(message['msg'], "utf-8"))


if __name__ == "__main__":
    gsps = GameSpyProfileServer()
    gsps.start()
