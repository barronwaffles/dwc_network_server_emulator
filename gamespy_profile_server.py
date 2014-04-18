import logging
import time

from twisted.internet.protocol import Factory
from twisted.internet.endpoints import serverFromString
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning

import gamespy.gs_database as gs_database
import gamespy.gs_query as gs_query
import gamespy.gs_utility as gs_utils
import other.utils as utils


# Logger settings
logger_output_to_console = True
logger_output_to_file = True
logger_name = "GameSpyProfileServer"
logger_filename = "gamespy_profile_server.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

address = ("0.0.0.0", 29900)
class GameSpyProfileServer(object):
    def __init__(self):
        pass

    def start(self):
        endpoint = serverFromString(reactor, "tcp:%d:interface=%s" % (address[1], address[0]))
        conn = endpoint.listen(PlayerFactory())

        try:
            if reactor.running == False:
                reactor.run(installSignalHandlers=0)
        except ReactorAlreadyRunning:
            pass

class PlayerFactory(Factory):
    def __init__(self):
        # Instead of storing the sessions in the database, it might make more sense to store them in the PlayerFactory.
        logger.log(logging.INFO, "Now listening for connections on %s:%d...", address[0], address[1])
        self.sessions = {}

    def buildProtocol(self, address):
        return PlayerSession(self.sessions, address)

class PlayerSession(LineReceiver):
    def __init__(self, sessions, address):
        self.setRawMode() # We're dealing with binary data so set to raw mode

        self.db = gs_database.GamespyDatabase()

        self.sessions = sessions
        self.address = address
        self.remaining_message = "" # Stores any unparsable/incomplete commands until the next rawDataReceived

        self.profileid = 0
        self.gameid = ""

        self.buddies = []
        self.blocked = []

        self.status = ""
        self.statstring = ""
        self.locstring = ""

    def log(self, level, message):
        if self.profileid == 0:
            if self.gameid == "":
                logger.log(level, "[%s:%d] %s", self.address.host, self.address.port,message)
            else:
                logger.log(level, "[%s:%d | %s] %s", self.address.host, self.address.port, self.gameid, message)
        else:
            if self.gameid == "":
                logger.log(level, "[%s:%d | %d] %s", self.address.host, self.address.port, self.profileid, message)
            else:
                logger.log(level, "[%s:%d | %d | %s] %s", self.address.host, self.address.port, self.profileid, self.gameid, message)

    def get_ip_as_int(self, address):
        ipaddress = 0

        if address != None:
            for n in address.split('.'):
                ipaddress = (ipaddress << 8) | int(n)

        return ipaddress

    def connectionMade(self):
        self.log(logging.INFO, "Received connection from %s:%d" % (self.address.host, self.address.port))

        # Create new session id
        self.session = ""

        # Generate a random challenge string
        self.challenge = utils.generate_random_str(8, "ABCDEFGHIJKLMNOPQRSTUVWXYZ")

        # The first command sent to the client is always a login challenge containing the server challenge key.
        msg_d = []
        msg_d.append(('__cmd__', "lc"))
        msg_d.append(('__cmd_val__', "1"))
        msg_d.append(('challenge', self.challenge))
        msg_d.append(('id', "1"))
        msg = gs_query.create_gamespy_message(msg_d)

        self.log(logging.DEBUG, "SENDING: '%s'..." % msg)
        self.transport.write(bytes(msg))

    def connectionLost(self, reason):
        self.log(logging.INFO, "Client disconnected")

        self.status = "0"
        self.statstring = "Offline"
        self.locstring = ""
        self.send_status_to_friends()

        if self.session in self.sessions:
            del self.sessions[self.session]
            self.log(logging.INFO, "Deleted session %d" % self.sessions)

    def rawDataReceived(self, data):
        self.log(logging.DEBUG, "RESPONSE: '%s'..." % data)

        # In the case where command string is too big to fit into one read, any parts that could not be successfully
        # parsed are stored in the variable remaining_message. On the next rawDataReceived command, the remaining
        # message and the data are combined to create a full command.
        data = self.remaining_message + data
        commands, self.remaining_message = gs_query.parse_gamespy_message(data)

        for data_parsed in commands:
            self.log(-1, data_parsed)

            if data_parsed['__cmd__'] == "login":
                self.perform_login(data_parsed)
            elif data_parsed['__cmd__'] == "logout":
                self.perform_logout(data_parsed)
            elif data_parsed['__cmd__'] == "getprofile":
                self.perform_getprofile(data_parsed)
            elif data_parsed['__cmd__'] == "updatepro":
                self.perform_updatepro(data_parsed)
            elif data_parsed['__cmd__'] == "ka":
                self.perform_ka(data_parsed)
            elif data_parsed['__cmd__'] == "status":
                self.perform_status(data_parsed)
            elif data_parsed['__cmd__'] == "bm":
                self.perform_bm(data_parsed)
            elif data_parsed['__cmd__'] == "addbuddy":
                self.perform_addbuddy(data_parsed)
            elif data_parsed['__cmd__'] == "delbuddy":
                self.perform_delbuddy(data_parsed)
            elif data_parsed['__cmd__'] == "authadd":
                self.perform_authadd(data_parsed)
            else:
                # Maybe write unknown commands to a separate file later so new data can be collected more easily?
                self.log(logging.ERROR, "Found unknown command, don't know how to handle '%s'." % data_parsed['__cmd__'])

    def perform_login(self, data_parsed):
        authtoken_parsed = gs_utils.parse_authtoken(data_parsed['authtoken'], self.db)
        #print authtoken_parsed

        # Track what console is connecting and save it in the database during user creation just in case we can use
        # the information in the future.
        console = 0 # 0 = NDS, 1 = Wii

        # get correct information
        userid = authtoken_parsed['userid']

        # The Wii does not use passwd, so take another uniquely generated string as the password.
        if "passwd" in authtoken_parsed:
            password = authtoken_parsed['passwd']
        else:
            password = authtoken_parsed['gsbrcd']
            console = 1

        gsbrcd = authtoken_parsed['gsbrcd']
        gameid = gsbrcd[:4]
        uniquenick = utils.base32_encode(int(userid)) + gsbrcd
        email = uniquenick + "@nds" # The Wii also seems to use @nds.

        # Wii: Serial number
        if "csnum" in authtoken_parsed:
            csnum = authtoken_parsed['csnum']
            console = 1
        else:
            csnum = ""

        # Wii: Friend code
        if "cfc" in authtoken_parsed:
            cfc = authtoken_parsed['cfc']
            console = 1
        else:
            cfc = ""

        # NDS: Wifi network's BSSID
        if "bssid" in authtoken_parsed:
            bssid = authtoken_parsed['bssid']
        else:
            bssid = ""

        # NDS: Device name
        if "devname" in authtoken_parsed:
            devname = authtoken_parsed['devname']
        else:
            devname = ""

        # NDS: User's birthday
        if "birth" in authtoken_parsed:
            birth = authtoken_parsed['birth']
        else:
            birth = ""

        # Verify the client's response
        valid_response = gs_utils.generate_response(self.challenge, authtoken_parsed['challenge'], data_parsed['challenge'], data_parsed['authtoken'])
        if data_parsed['response'] != valid_response:
            self.log(logging.ERROR, "ERROR: Got invalid response. Got %s, expected %s" % (data_parsed['response'], valid_response))

        proof = gs_utils.generate_proof(self.challenge, authtoken_parsed['challenge'], data_parsed['challenge'], data_parsed['authtoken'])

        valid_user = self.db.check_user_exists(userid, gsbrcd)
        if valid_user == False:
            profileid = self.db.create_user(userid, password, email, uniquenick, gsbrcd, console, csnum, cfc, bssid, devname, birth, gameid)
        else:
            profileid = self.db.perform_login(userid, password, gsbrcd)

            if profileid == None:
                 # Handle case where the user is invalid
                self.log(logging.ERROR, "Invalid password")

        if profileid != None:
            # Successfully logged in or created account, continue creating session.
            sesskey = self.db.create_session(profileid)

            self.sessions[profileid] = self

            msg_d = []
            msg_d.append(('__cmd__', "lc"))
            msg_d.append(('__cmd_val__', "2"))
            msg_d.append(('sesskey', sesskey))
            msg_d.append(('proof', proof))
            msg_d.append(('userid', userid))
            msg_d.append(('profileid', profileid))
            msg_d.append(('uniquenick', uniquenick))
            msg_d.append(('lt', gs_utils.base64_encode(utils.generate_random_str(16)))) # Some kind of token... don't know it gets used or generated, but it doesn't seem to have any negative effects if it's not properly generated.
            msg_d.append(('id', data_parsed['id']))
            msg = gs_query.create_gamespy_message(msg_d)

            # Take the first 4 letters of gsbrcd instead of gamecd because they should be consistent across game
            # regions. For example, the US version of Metroid Prime Hunters has the gamecd "AMHE" and the first 4 letters
            # of gsbrcd are "AMHE". However, the Japanese version of Metroid Prime Hunters has the gamecd "AMHJ" with
            # the first 4 letters of bsbrcd as "AMHE". Tetris DS is the other way, with the first 4 letters as the
            # Japanese version (ATRJ) while the gamecd is region specific (ATRE for US and ATRJ for JP).
            # gameid is used to send all people on the player's friends list a status updates, so don't make it region
            # specific.
            self.gameid = gsbrcd[0:4]
            self.profileid = int(profileid)

            self.log(logging.DEBUG, "SENDING: %s" % msg)
            self.transport.write(bytes(msg))

            self.buddies = self.db.get_buddy_list(self.profileid)
            self.blocked = self.db.get_blocked_list(self.profileid)

            # Get pending messages.
            self.get_pending_messages()

            # Send any friend statuses when the user logs in.
            # This will allow the user to see if their friends are hosting a game as soon as they log in.
            self.get_status_from_friends()
            self.send_status_to_friends()

    def perform_logout(self, data_parsed):
        self.log(logging.INFO, "Session %s has logged off" % (data_parsed['sesskey']))
        self.db.delete_session(data_parsed['sesskey'])

    def perform_getprofile(self, data_parsed):
        #profile = self.db.get_profile_from_session_key(data_parsed['sesskey'])
        profile = self.db.get_profile_from_profileid(data_parsed['profileid'])

        # Wii example: \pi\\profileid\474888031\nick\5pde5vhn1WR9E2g1t533\userid\442778352\email\5pde5vhn1WR9E2g1t533@nds\sig\b126556e5ee62d4da9629dfad0f6b2a8\uniquenick\5pde5vhn1WR9E2g1t533\pid\11\lon\0.000000\lat\0.000000\loc\\id\2\final\
        sig = utils.generate_random_hex_str(32)

        msg_d = []
        msg_d.append(('__cmd__', "pi"))
        msg_d.append(('__cmd_val__', ""))
        msg_d.append(('profileid', profile['profileid']))
        msg_d.append(('nick', profile['uniquenick']))
        msg_d.append(('userid', profile['userid']))
        msg_d.append(('email', profile['email']))
        msg_d.append(('sig', sig))
        msg_d.append(('uniquenick', profile['uniquenick']))
        msg_d.append(('pid', profile['pid']))

        if profile['firstname'] != "":
            msg_d.append(('firstname', profile['firstname'])) # Wii gets a firstname

        if profile['lastname'] != "":
            msg_d.append(('lastname', profile['lastname']))

        msg_d.append(('lon', profile['lon']))
        msg_d.append(('lat', profile['lat']))
        msg_d.append(('loc', profile['loc']))
        msg_d.append(('id', data_parsed['id']))
        msg = gs_query.create_gamespy_message(msg_d)

        self.log(logging.DEBUG, "SENDING: %s" % msg)
        self.transport.write(bytes(msg))

    def perform_updatepro(self, data_parsed):
        # Wii example: \updatepro\\sesskey\199714190\firstname\Wii:2555151656076614@WR9E\partnerid\11\final\

        # Remove any fields not related to what we should be updating.
        # To avoid any crashes, make sure the key is actually in the dictionary before removing it.
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
        # No op
        return

    def perform_status(self, data_parsed):
        sesskey = data_parsed['sesskey']

        #fields = []
        #fields.append(("stat", data_parsed['statstring']))
        #fields.append(("loc", data_parsed['locstring']))

        #self.db.update_profile(sesskey, fields)

        self.status = data_parsed['__cmd_val__']
        self.statstring =  data_parsed['statstring']
        self.locstring =  data_parsed['locstring']

        # Send authorization requests to client
        self.get_buddy_requests()

        # Send authorizationed message to client
        self.get_buddy_authorized()

        self.send_status_to_friends()


    def perform_bm(self, data_parsed):
        if data_parsed['__cmd_val__'] == "1" or data_parsed['__cmd_val__'] == "5" or data_parsed['__cmd_val__'] == "102" or data_parsed['__cmd_val__'] == "103": # Message to/from clients?
            if "t" in data_parsed:
                # Send message to the profile id in "t"
                dest_profileid = int(data_parsed['t'])
                dest_profile_buddies = self.db.get_buddy_list(dest_profileid)
                dest_msg = data_parsed['msg']

                not_buddies = False

                # Check if the user is buddies with the target user before sending message.
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

                # Send error to user if they tried to send a message to someone who isn't a buddy.
                if not_buddies:
                    msg_d = []
                    msg_d.append(('__cmd__', "error"))
                    msg_d.append(('__cmd_val__', ""))
                    msg_d.append(('err', 2305))
                    msg_d.append(('errmsg', "The profile the message was to be sent to is not a buddy."))
                    msg_d.append(('id', 1))
                    msg = gs_query.create_gamespy_message(msg_d)
                    logger.log(logging.DEBUG, "Trying to send message to someone who isn't a buddy: %s" % msg)
                    self.transport.write(msg)
                    return

                msg_d = []
                msg_d.append(('__cmd__', "bm"))
                msg_d.append(('__cmd_val__', "1"))
                msg_d.append(('f', self.profileid))
                msg_d.append(('msg', dest_msg))
                msg = gs_query.create_gamespy_message(msg_d)

                if dest_profileid in self.sessions:
                    self.log(logging.DEBUG, "SENDING TO %s:%s: %s" % (self.sessions[dest_profileid].address.host, self.sessions[dest_profileid].address.port, msg))
                    self.sessions[dest_profileid].transport.write(bytes(msg))
                else:
                    if data_parsed['__cmd_val__'] == "1":
                        self.log(logging.DEBUG, "Saving message to %d: %s" % (dest_profileid, msg))
                        self.db.save_pending_message(self.profileid, dest_profileid, msg)
                    else:
                        msg_d = []
                        msg_d.append(('__cmd__', "error"))
                        msg_d.append(('__cmd_val__', ""))
                        msg_d.append(('err', 2307))
                        msg_d.append(('errmsg', "The buddy to send a message to is offline."))
                        msg_d.append(('id', 1))
                        msg = gs_query.create_gamespy_message(msg_d)
                        logger.log(logging.DEBUG, "Trying to send message to someone who isn't online: %s" % msg)
                        self.transport.write(msg)


    def perform_addbuddy(self, data_parsed):
        newprofileid = int(data_parsed['newprofileid'])
        if newprofileid == self.profileid:
            logger.log(logging.DEBUG, "Can't add self as friend: %d == %d", newprofileid, self.profileid)
            return

        # Sample: \addbuddy\\sesskey\231601763\newprofileid\476756820\reason\\final\
        self.buddies = self.db.get_buddy_list(self.profileid)

        buddy_exists = False
        for buddy in self.buddies:
            if buddy['buddyProfileId'] == newprofileid:
                buddy_exists = True
                break

        if buddy_exists == False:
            self.db.add_buddy(self.profileid, newprofileid)

            if newprofileid in self.sessions:
                logger.log(logging.DEBUG, "User is online, sending direct request from profile id %d to profile id %d..." % (self.profileid, newprofileid))
                self.send_buddy_request(self.sessions[newprofileid], self.profileid)


    def perform_delbuddy(self, data_parsed):
        # Sample: \delbuddy\\sesskey\61913621\delprofileid\1\final\
        self.db.delete_buddy(self.profileid, int(data_parsed['delprofileid']))

    def perform_authadd(self, data_parsed):
        # Sample: \authadd\\sesskey\231587549\fromprofileid\217936895\sig\f259f26d3273f8bda23c7c5e4bd8c5aa\final\
        # Authorize the other person's friend request.
        self.db.auth_buddy(int(data_parsed['fromprofileid']), self.profileid)

        self.get_buddy_authorized()

    def send_status_to_friends(self):
        # TODO: Cache buddy list so we don't have to query the database every time
        self.buddies = self.db.get_buddy_list(self.profileid)

        if self.status == "0" and self.statstring == "Offline":
            # Going offline, don't need to send the other information.
            status_msg = "|s|%s|ss|%s" % (self.status, self.statstring)
        else:
            status_msg = "|s|%s|ss|%s|ls|%s|ip|%d|p|0|qm|0" % (self.status, self.statstring, self.locstring, self.get_ip_as_int(self.address.host))

        msg_d = []
        msg_d.append(('__cmd__', "bm"))
        msg_d.append(('__cmd_val__', "100"))
        msg_d.append(('f', self.profileid))
        msg_d.append(('msg', status_msg))
        msg = gs_query.create_gamespy_message(msg_d)

        for buddy in self.buddies:
            if buddy['buddyProfileId'] in self.sessions:
                self.sessions[buddy['buddyProfileId']].transport.write(bytes(msg))

    def get_status_from_friends(self):
        # This will be called when the player logs in. Grab the player's buddy list and check the current sessions to
        # see if anyone is online. If they are online, make them send an update to the calling client.
        self.buddies = self.db.get_buddy_list(self.profileid)

        for buddy in self.buddies:
            if buddy['status'] != 1:
                continue

            if buddy['buddyProfileId'] in self.sessions and self.sessions[buddy['buddyProfileId']].gameid == self.gameid:
                status_msg = "|s|%s|ss|%s|ls|%s|ip|%d|p|0|qm|0" % (self.sessions[buddy['buddyProfileId']].status, self.sessions[buddy['buddyProfileId']].statstring, self.sessions[buddy['buddyProfileId']].locstring, self.get_ip_as_int(self.sessions[buddy['buddyProfileId']].address.host))
            else:
                status_msg = "|s|0|ss|Offline"

            msg_d = []
            msg_d.append(('__cmd__', "bm"))
            msg_d.append(('__cmd_val__', "100"))
            msg_d.append(('f', buddy['buddyProfileId']))
            msg_d.append(('msg', status_msg))
            msg = gs_query.create_gamespy_message(msg_d)

            self.transport.write(bytes(msg))

    def get_buddy_authorized(self):
        buddies = self.db.buddy_need_auth_message(self.profileid)

        for buddy in buddies:
            msg_d = []
            msg_d.append(('__cmd__', "bm"))
            msg_d.append(('__cmd_val__', "1"))
            msg_d.append(('f', buddy['userProfileId']))
            msg_d.append(('msg', "I have authorized your request to add me to your list"))
            msg = gs_query.create_gamespy_message(msg_d)

            self.transport.write(bytes(msg))
            self.db.buddy_sent_auth_message(buddy['userProfileId'], buddy['buddyProfileId'])

    def get_buddy_requests(self):
        # Get list people who have added the user but haven't been accepted yet.
        buddies = self.db.get_pending_buddy_requests(self.profileid)

        for buddy in buddies:
            self.send_buddy_request(self, buddy['userProfileId'], buddy['time'])

    def send_buddy_request(self, session, profileid, senttime = None):
        sig = utils.generate_random_hex_str(32)
        msg = "\r\n\r\n"
        msg += "|signed|" + sig

        if senttime == None:
            senttime = int(time.time())

        msg_d = []
        msg_d.append(('__cmd__', "bm"))
        msg_d.append(('__cmd_val__', "2"))
        msg_d.append(('f', profileid))
        msg_d.append(('date', senttime))
        msg_d.append(('msg', msg))
        msg = gs_query.create_gamespy_message(msg_d)

        session.transport.write(bytes(msg))

    def get_pending_messages(self):
        messages = self.db.get_pending_messages(self.profileid)

        for message in messages:
            if message['sourceid'] not in self.blocked:
                self.transport(message['msg'])


if __name__ == "__main__":
    gsps = GameSpyProfileServer()
    gsps.start()
