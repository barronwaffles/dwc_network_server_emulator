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
logger_name = "GameSpyGamestatsServer"
logger_filename = "gamespy_gamestats_server.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

address = ("0.0.0.0", 29920)

class GameSpyGamestatsServer(object):
    def __init__(self):
        pass

    def start(self):
        endpoint_search = serverFromString(reactor, "tcp:%d:interface=%s" % (address[1], address[0]))
        conn_search = endpoint_search.listen(GamestatsFactory())

        try:
            if reactor.running == False:
                reactor.run(installSignalHandlers=0)
        except ReactorAlreadyRunning:
            pass


class GamestatsFactory(Factory):
    def __init__(self):
        logger.log(logging.INFO, "Now listening for connections on %s:%d...", address[0], address[1])
        self.sessions = {}

    def buildProtocol(self, address):
        return Gamestats(self.sessions, address)


class Gamestats(LineReceiver):
    def __init__(self, sessions, address):
        self.setRawMode() # We're dealing with binary data so set to raw mode

        self.db = gs_database.GamespyDatabase()

        self.sessions = sessions
        self.address = address
        self.remaining_message = "" # Stores any unparsable/incomplete commands until the next rawDataReceived

        self.session = ""
        self.gameid = ""

        self.lid = "0"

    def log(self, level, message):
        if self.session == "":
            if self.gameid == "":
                logger.log(level, "[%s:%d] %s", self.address.host, self.address.port,message)
            else:
                logger.log(level, "[%s:%d | %s] %s", self.address.host, self.address.port, self.gameid, message)
        else:
            if self.gameid == "":
                logger.log(level, "[%s:%d | %s] %s", self.address.host, self.address.port, self.session, message)
            else:
                logger.log(level, "[%s:%d | %s | %s] %s", self.address.host, self.address.port, self.session, self.gameid, message)

    def connectionMade(self):
        self.log(logging.INFO, "Received connection from %s:%d" % (self.address.host, self.address.port))

        # Generate a random challenge string
        self.challenge = utils.generate_random_str(10, "ABCDEFGHIJKLMNOPQRSTUVWXYZ")

        # The first command sent to the client is always a login challenge containing the server challenge key.
        msg = gs_query.create_gamespy_message([
            ('__cmd__', "lc"),
            ('__cmd_val__', "1"),
            ('challenge', self.challenge),
            ('id', "1"),
        ])

        self.log(logging.DEBUG, "SENDING: '%s'..." % msg)

        msg = self.crypt(msg)
        self.transport.write(bytes(msg))

    def connectionLost(self, reason):
        return

    def rawDataReceived(self, data):
        # Decrypt packet
        data = self.remaining_message + data
        msg = str(self.crypt(data))

        #data = self.leftover + data
        commands, self.remaining_message = gs_query.parse_gamespy_message(msg)
        #logger.log(logging.DEBUG, "STATS RESPONSE: %s" % msg)

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
            logger.log(logging.DEBUG, "Found unknown command, don't know how to handle '%s'.", data_parsed['__cmd__'])

        for data_parsed in commands:
            print(data_parsed)

            cmds.get(data_parsed['__cmd__'], cmd_err)(data_parsed)

    def perform_auth(self, data_parsed):
        self.log(logging.DEBUG, "Parsing 'auth'...")

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

        self.log(logging.DEBUG, "SENDING: '%s'..." % msg)

        msg = self.crypt(msg)
        self.transport.write(bytes(msg))

    def perform_authp(self, data_parsed):
        authtoken_parsed = gs_utils.parse_authtoken(data_parsed['authtoken'], self.db)
        #print authtoken_parsed

        if "lid" in data_parsed:
            self.lid = data_parsed['lid']

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

        valid_user = self.db.check_user_exists(userid, gsbrcd)
        profileid = None
        if valid_user:
            profileid = self.db.perform_login(userid, password, gsbrcd)

            if profileid == None:
                 # Handle case where the user is invalid
                self.log(logging.ERROR, "Invalid password")

        if profileid != None:
            # Successfully logged in or created account, continue creating session.
            sesskey = self.db.create_session(profileid, '')

            self.sessions[profileid] = self

            msg = gs_query.create_gamespy_message([
                ('__cmd__', "pauthr"),
                ('__cmd_val__', profileid),
                ('lid', self.lid),
            ])

            self.profileid = int(profileid)

            self.log(logging.DEBUG, "SENDING: '%s'..." % msg)

            msg = self.crypt(msg)
            self.transport.write(bytes(msg))
        else:
            # Return error
            pass

    def perform_ka(self, data_parsed):
        msg = gs_query.create_gamespy_message([
            ('__cmd__', "ka"),
            ('__cmd_val__', ""),
        ])

        self.log(logging.DEBUG, "SENDING: '%s'..." % msg)

        msg = self.crypt(msg)
        self.transport.write(bytes(msg))
        return

    def perform_setpd(self, data_parsed, data):
        msg = gs_query.create_gamespy_message([
            ('__cmd__', "setpdr"),
            ('__cmd_val__', 1),
            ('lid', self.lid),
            ('pid', self.profileid),
            ('mod', int(time.time())),
        ])

        self.log(logging.DEBUG, "SENDING: '%s'..." % msg)

        msg = self.crypt(msg)
        self.transport.write(bytes(msg))

        # TODO: Return error message.
        if int(data_parsed['pid']) != self.profileid:
            logger.log(logging.WARNING, "ERROR: %d tried to update %d's profile" % (int(data_parsed['pid']), self.profileid))
            return

        data_str = "\\data\\"
        length = int(data_parsed['length'])

        if len(data) < length:
            # The packet isn't complete yet, keep loop until we get the entire packet.
            # The length entire packet SHOULD always be greater than the data field, so this check should be fine.
            return

        idx = data.index(data_str) + len(data_str)
        data = data[idx:idx+length]

        self.db.pd_insert(self.profileid, data_parsed['dindex'], data_parsed['ptype'], data)

    def perform_getpd(self, data_parsed):
        profile = self.db.pd_get(self.profileid, data_parsed['dindex'], data_parsed['ptype'])

        keys = data_parsed['keys'].split('\x01')

        profile_data = None

        if profile != None and 'data' in profile:
            profile_data = gs_query.parse_gamespy_message("\\prof\\" + profile['data'] + "\\final\\")

        if profile_data != None:
            profile_data = profile_data[0][0]

        data = ""
        for key in (key for key in keys if key not in ("__cmd__", "__cmd_val__", "")):
            data += "\\" + key + "\\"
            # this WILL error if profile_data isn't properly set above
            if key in profile_data:
                data += profile_data[key]

        modified = int(time.time())

        msg = gs_query.create_gamespy_message([
            ('__cmd__', "getpdr"),
            ('__cmd_val__', 1),
            ('lid', self.lid),
            ('pid', self.profileid),
            ('mod', modified),
            ('length', len(data)),
            ('data', data),
        ])

        self.log(logging.DEBUG, "SENDING: '%s'..." % msg)




    def perform_newgame(self, data_parsed):
        # No op
        return

    def perform_updgame(self, data_parsed):
        # No op
        return

    def crypt(self, data):
        key = "GameSpy3D"
        output = bytearray(data)

        if "\\final\\" in output:
            end = output.index("\\final\\")
        else:
            end = len(output)

        for i in range(end):
            output[i] ^= ord(key[i % len(key)])

        return output

if __name__ == "__main__":
    gsss = GameSpyGamestatsServer()
    gsss.start()

