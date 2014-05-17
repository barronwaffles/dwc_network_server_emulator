import sqlite3
import hashlib
import itertools
import json
import time
import logging

import other.utils as utils
import gamespy.gs_utility as gs_utils

# Logger settings
logger_output_to_console = True
logger_output_to_file = True
logger_name = "GamespyDatabase"
logger_filename = "gamespy_database.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

class GamespyDatabase(object):
    def __init__(self, filename='gpcm.db'):
        self.conn = sqlite3.connect(filename)
        self.conn.row_factory = sqlite3.Row

        self.initialize_database(self.conn)

    def initialize_database(self, conn):
        c = self.conn.cursor()
        c.execute("SELECT * FROM sqlite_master WHERE name = 'users' AND type = 'table'")

        if c.fetchone() == None:
            # I highly doubt having everything in a database be of the type TEXT is a good practice,
            # but I'm not good with databases and I'm not 100% positive that, for instance, that all
            # user id's will be ints, or all passwords will be ints, etc, despite not seeing any
            # evidence yet to say otherwise as far as Nintendo DS games go.
            q = "CREATE TABLE users (profileid INT, userid TEXT, password TEXT, gsbrcd TEXT, email TEXT, uniquenick TEXT, pid TEXT, lon TEXT, lat TEXT, loc TEXT, firstname TEXT, lastname TEXT, stat TEXT, partnerid TEXT, console INT, csnum TEXT, cfc TEXT, bssid TEXT, devname BLOB, birth TEXT, gameid TEXT, enabled INT, zipcode TEXT, aim TEXT)"
            logger.log(-1, q)
            c.execute(q)

            q = "CREATE TABLE sessions (session TEXT, profileid INT)"
            logger.log(-1, q)
            c.execute(q)

            q = "CREATE TABLE buddies (userProfileId INT, buddyProfileId INT, time INT, status INT, notified INT, gameid TEXT, blocked INT)"
            logger.log(-1, q)
            c.execute(q)

            q = "CREATE TABLE pending_messages (sourceid INT, targetid INT, msg TEXT)"
            logger.log(-1, q)
            c.execute(q)

            q = "CREATE TABLE gamestat_profile (profileid INT, dindex TEXT, ptype TEXT, data TEXT)"
            logger.log(-1, q)
            c.execute(q)

            q = "CREATE TABLE gameinfo (profileid INT, dindex TEXT, ptype TEXT, data TEXT)"
            logger.log(-1, q)
            c.execute(q)

            q = "CREATE TABLE nas_logins (userid TEXT, authtoken TEXT, data TEXT)"
            logger.log(-1, q)
            c.execute(q)

            self.conn.commit()

    def get_dict(self, row):
        if row == None:
            return None

        return dict(itertools.izip(row.keys(), row))

    # User functions
    def get_next_free_profileid(self):
        # TODO: Make profile ids start at 1 for each game?
        q = "SELECT max(profileid) FROM users"
        logger.log(-1, q)

        c = self.conn.cursor()
        c.execute(q)

        r = self.get_dict(c.fetchone())

        profileid = 1 # Cannot be 0 or else it freezes the game.
        if r != None and r['max(profileid)'] != None:
            profileid = int(r['max(profileid)']) + 1

        c.close()

        return profileid

    def check_user_exists(self, userid, gsbrcd):
        q = "SELECT * FROM users WHERE userid = ? and gsbrcd = ?"
        q2 = q.replace("?", "%s") % (userid, gsbrcd)
        logger.log(-1, q)

        c = self.conn.cursor()
        c.execute(q, [userid, gsbrcd])

        r = self.get_dict(c.fetchone())

        valid_user = False  # Default, user doesn't exist
        if r != None:
            valid_user = True  # Valid password

        c.close()
        return valid_user

    def check_profile_exists(self, profileid):
        q = "SELECT * FROM users WHERE profileid = ?"
        q2 = q.replace("?", "%s") % (profileid)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [profileid])

        r = self.get_dict(c.fetchone())

        valid_profile = False  # Default, user doesn't exist
        if r != None:
            valid_profile = True  # Valid password

        c.close()
        return valid_profile

    def get_profile_from_profileid(self, profileid):
        profile = {}
        if profileid != 0:
            q = "SELECT * FROM users WHERE profileid = ?"
            q2 = q.replace("?", "%s") % (profileid)
            logger.log(-1, q2)

            c = self.conn.cursor()
            c.execute(q, [profileid])

            profile = self.get_dict(c.fetchone())
            c.close()

        return profile

    def perform_login(self, userid, password, gsbrcd):
        q = "SELECT * FROM users WHERE userid = ? and gsbrcd = ?"
        q2 = q.replace("?", "%s") % (userid, gsbrcd)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [userid, gsbrcd])

        r = self.get_dict(c.fetchone())

        profileid = None  # Default, user doesn't exist
        if r != None:
            md5 = hashlib.md5()
            md5.update(password)

            if r['password'] == md5.hexdigest():
                profileid = r['profileid']  # Valid password

        c.close()
        return profileid

    def create_user(self, userid, password, email, uniquenick, gsbrcd, console, csnum, cfc, bssid, devname, birth, gameid):
        if self.check_user_exists(userid, gsbrcd) == 0:
            profileid = self.get_next_free_profileid()

            pid = "11"  # Always 11??? Is this important? Not to be confused with dwc_pid.
                        # The three games I found it in (Tetris DS, Advance Wars - Days of Ruin, and
                        # Animal Crossing: Wild World) all use \pid\11.
            lon = "0.000000"  # Always 0.000000?
            lat = "0.000000"  # Always 0.000000?
            loc = ""
            firstname = ""
            lastname = ""
            stat = ""
            partnerid = ""
            enabled = 1
            zipcode = ""
            aim = ""

            # Hash password before entering it into the database.
            # For now I'm using a very simple MD5 hash.
            # TODO: Replace with something stronger later, although it's overkill for the NDS.
            md5 = hashlib.md5()
            md5.update(password)
            password = md5.hexdigest()

            q = "INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            q2 = q.replace("?", "%s") % (profileid, str(userid), password, gsbrcd, email, uniquenick, pid, lon, lat, loc, firstname, lastname, stat, partnerid, console, csnum, cfc, bssid, devname, birth, gameid, enabled, zipcode, aim)
            logger.log(-1, q2)

            c = self.conn.cursor()
            c.execute(q, [profileid, str(userid), password, gsbrcd, email, uniquenick, pid, lon, lat, loc, firstname, lastname, stat, partnerid, console, csnum, cfc, bssid, devname, birth, gameid, enabled, zipcode, aim])
            c.close()

            self.conn.commit()

            return profileid

    def import_user(self, profileid, uniquenick, firstname, lastname, email, gsbrcd, gameid, console):
        if self.check_profile_exists(profileid) == 0:
            pid = "11"
            lon = "0.000000"
            lat = "0.000000"
            loc = ""
            stat = ""
            partnerid = ""
            password = ""
            userid = ""

            csnum = ""
            cfc = ""
            bssid = ""
            devname = ""
            birth = ""
            zipcode = ""
            aim = ""

            enabled = 1

            q = "INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            q2 = q.replace("?", "%s") % (profileid, str(userid), password, gsbrcd, email, uniquenick, pid, lon, lat, loc, firstname, lastname, stat, partnerid, console, csnum, cfc, bssid, devname, birth, gameid, enabled, zipcode, aim)
            logger.log(-1, q2)

            c = self.conn.cursor()
            c.execute(q, [profileid, str(userid), password, gsbrcd, email, uniquenick, pid, lon, lat, loc, firstname, lastname, stat, partnerid, console, csnum, cfc, bssid, devname, birth, gameid, enabled, zipcode, aim])
            c.close()

            self.conn.commit()

            return profileid

    def get_user_list(self):
        c = self.conn.cursor()

        q = "SELECT * FROM users"
        logger.log(-1, q)

        users = []
        for row in c.execute(q):
            users.append(self.get_dict(row))

        return users

    def save_pending_message(self, sourceid, targetid, msg):
        q = "INSERT INTO pending_messages VALUES (?,?,?)"
        q2 = q.replace("?", "%s") % (sourceid, targetid, msg)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [sourceid, targetid, msg])
        c.close()

        self.conn.commit()

    def get_pending_messages(self, profileid):
        c = self.conn.cursor()

        q = "SELECT * FROM pending_messages WHERE targetid = ?"
        q2 = q.replace("?", "%s") % (profileid)
        logger.log(-1, q2)

        messages = []
        for row in c.execute(q, [profileid]):
            messages.append(self.get_dict(row))

        return messages

    def update_profile(self, profileid, field):
        # Found profile id associated with session key.
        # Start replacing each field one by one.
        # TODO: Optimize this so it's done all in one update.
        # FIXME: Possible security issue due to embedding an unsanitized string directly into the statement.
        q = "UPDATE users SET \"%s\" = ? WHERE profileid = ?"
        q2 = q.replace("?", "%s") % (field[0], field[1], profileid)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q % field[0], [field[1], profileid])
        self.conn.commit()

    # Session functions
    # TODO: Cache session keys so we don't have to query the database every time we get a profile id.
    def get_profileid_from_session_key(self, session_key):
        q = "SELECT profileid FROM sessions WHERE session = ?"
        q2 = q.replace("?", "%s") % (session_key)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [session_key])

        r = self.get_dict(c.fetchone())

        profileid = -1  # Default, invalid session key
        if r != None:
            profileid = r['profileid']

        c.close()
        return profileid

    def get_profile_from_session_key(self, session_key):
        profileid = self.get_profileid_from_session_key(session_key)

        profile = {}
        if profileid != 0:
            q = "SELECT profileid FROM sessions WHERE session = ?"
            q2 = q.replace("?", "%s") % (session_key)
            logger.log(-1, q2)

            c = self.conn.cursor()
            c.execute(q, [session_key])

            profile = self.get_dict(c.fetchone())
            c.close()

        return profile

    def generate_session_key(self, min_size):
        session_key = utils.generate_random_number_str(min_size)

        q = "SELECT session FROM sessions WHERE session = ?"
        q2 = q.replace("?", "%s") % (session_key)
        logger.log(-1, q2)

        c = self.conn.cursor()
        for r in c.execute(q, [session_key]):
            session_key = utils.generate_random_number_str(min_size)

        return session_key

    def delete_session(self, profileid):
        q = "DELETE FROM sessions WHERE profileid = ?"
        q2 = q.replace("?", "%s") % (profileid)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [profileid])
        self.conn.commit()

    def create_session(self, profileid):
        if profileid != None and self.check_profile_exists(profileid) == False:
            return None

        # Remove any old sessions associated with this user id
        self.delete_session(profileid)

        # Create new session
        session_key = self.generate_session_key(8)

        q ="INSERT INTO sessions VALUES (?, ?)"
        q2 = q.replace("?", "%s") % (session_key, profileid)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [session_key, profileid])
        self.conn.commit()

        return session_key

    def get_session_list(self, profileid=None):
        c = self.conn.cursor()

        sessions = []
        if profileid != None:
            q = "SELECT * FROM sessions WHERE profileid = ?"
            q2 = q.replace("?", "%s") % (profileid)
            logger.log(-1, q2)

            r = c.execute(q, [profileid])
        else:
            q = "SELECT * FROM sessions"
            logger.log(-1, q)

            r = c.execute(q)

        for row in r:
            sessions.append(self.get_dict(row))

        return sessions

    # nas server functions
    def get_nas_login(self, authtoken):
        q = "SELECT data FROM nas_logins WHERE authtoken = ?"
        q2 = q.replace("?", "%s") % (authtoken)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [authtoken])
        r = self.get_dict(c.fetchone())
        c.close()

        if r == None:
            return None
        else:
            return json.loads(r["data"])

    def generate_authtoken(self, userid, data):
        # Since the auth token passed back to the game will be random, we can make it small enough that there
        # should never be a crash due to the size of the token.
        size = 16
        authtoken = "NDS" + utils.generate_random_str(size)

        q = "SELECT authtoken FROM nas_logins WHERE authtoken = ?"
        q2 = q.replace("?", "%s") % (authtoken)
        logger.log(-1, q2)

        c = self.conn.cursor()
        for r in c.execute(q, [authtoken]):
            authtoken = "NDS" + utils.generate_random_str(size)

        q = "SELECT * FROM nas_logins WHERE userid = ?"
        q2 = q.replace("?", "%s") % (userid)
        logger.log(-1, q2)

        c.execute(q, [userid])
        r = self.get_dict(c.fetchone())

        if "devname" in data:
            data["devname"] = gs_utils.base64_encode(data["devname"])

        data = json.dumps(data)

        if r == None: # no row, add it
            q = "INSERT INTO nas_logins VALUES (?, ?, ?)"
            q2 = q.replace("?", "%s") % (userid, authtoken, data)
            logger.log(-1, q2)
            c.execute(q, [userid, authtoken, data])
        else:
            q = "UPDATE nas_logins SET authtoken = ?, data = ? WHERE userid = ?"
            q2 = q.replace("?", "%s") % (authtoken, data, userid)
            logger.log(-1, q2)
            c.execute(q, [authtoken, data, userid])

        c.close()
        self.conn.commit()

        return authtoken
        

    # Buddy functions
    def add_buddy(self, userProfileId, buddyProfileId):
        now = int(time.time())

        q = "INSERT INTO buddies VALUES (?, ?, ?, ?, ?, ?, ?)"
        q2 = q.replace("?", "%s") % (userProfileId, buddyProfileId, now, 0, 0, "", 0)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [userProfileId, buddyProfileId, now, 0, 0, "", 0]) # 0 will mean not authorized
        self.conn.commit()

    def auth_buddy(self, userProfileId, buddyProfileId):
        q = "UPDATE buddies SET status = ? WHERE userProfileId = ? AND buddyProfileId = ?"
        q2 = q.replace("?", "%s") % (1, userProfileId, buddyProfileId)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [1, userProfileId, buddyProfileId]) # 1 will mean authorized
        self.conn.commit()

    def block_buddy(self, userProfileId, buddyProfileId):
        q = "UPDATE buddies SET blocked = ? WHERE userProfileId = ? AND buddyProfileId = ?"
        q2 = q.replace("?", "%s") % (1, userProfileId, buddyProfileId)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [1, userProfileId, buddyProfileId]) # 1 will mean blocked
        self.conn.commit()

    def unblock_buddy(self, userProfileId, buddyProfileId):
        q = "UPDATE buddies SET blocked = ? WHERE userProfileId = ? AND buddyProfileId = ?"
        q2 = q.replace("?", "%s") % (0, userProfileId, buddyProfileId)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [0, userProfileId, buddyProfileId]) # 0 will mean not blocked
        self.conn.commit()

    def get_buddy(self, userProfileId, buddyProfileId):
        profile = {}
        if userProfileId != 0 and buddyProfileId != 0:
            q = "SELECT * FROM buddies WHERE userProfileId = ? AND buddyProfileId = ?"
            q2 = q.replace("?", "%s") % (userProfileId, buddyProfileId)
            logger.log(-1, q2)

            c = self.conn.cursor()
            c.execute(q, [userProfileId, buddyProfileId])
            profile = self.get_dict(c.fetchone())
            c.close()

        return profile

    def delete_buddy(self, userProfileId, buddyProfileId):
        q = "DELETE FROM buddies WHERE userProfileId = ? AND buddyProfileId = ?"
        q2 = q.replace("?", "%s") % (userProfileId, buddyProfileId)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [userProfileId, buddyProfileId])
        self.conn.commit()

    def get_buddy_list(self, userProfileId):
        q = "SELECT * FROM buddies WHERE userProfileId = ? AND blocked = 0"
        q2 = q.replace("?", "%s") % (userProfileId)
        logger.log(-1, q2)

        c = self.conn.cursor()

        users = []
        for row in c.execute(q, [userProfileId]):
            users.append(self.get_dict(row))

        return users

    def get_blocked_list(self, userProfileId):
        q = "SELECT * FROM buddies WHERE userProfileId = ? AND blocked = 1"
        q2 = q.replace("?", "%s") % (userProfileId)
        logger.log(-1, q2)

        c = self.conn.cursor()

        users = []
        for row in c.execute(q, [userProfileId]):
            users.append(self.get_dict(row))

        return users

    def get_pending_buddy_requests(self, userProfileId):
        q = "SELECT * FROM buddies WHERE buddyProfileId = ? AND status = 0"
        q2 = q.replace("?", "%s") % (userProfileId)
        logger.log(-1, q2)

        c = self.conn.cursor()

        users = []
        for row in c.execute(q, [userProfileId]):
            users.append(self.get_dict(row))

        return users

    def buddy_need_auth_message(self, userProfileId):
        q = "SELECT * FROM buddies WHERE buddyProfileId = ? AND status = 1 AND notified = 0"
        q2 = q.replace("?", "%s") % (userProfileId)
        logger.log(-1, q2)

        c = self.conn.cursor()

        users = []
        for row in c.execute(q, [userProfileId]):
            users.append(self.get_dict(row))

        return users

    def buddy_sent_auth_message(self, userProfileId, buddyProfileId):
        q = "UPDATE buddies SET notified = ? WHERE userProfileId = ? AND buddyProfileId = ?"
        q2 = q.replace("?", "%s") % (1, userProfileId, buddyProfileId)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [1, userProfileId, buddyProfileId]) # 1 will mean that the player has been sent the "
        self.conn.commit()

    # Gamestats-related functions
    def pd_insert(self, profileid, dindex, ptype, data):
        q = "INSERT OR IGNORE INTO gamestat_profile (profileid, dindex, ptype, data) VALUES(?,?,?,?)"
        q2 = q.replace("?", "%s") % (profileid, dindex, ptype, data)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [profileid, dindex, ptype, data])
        self.conn.commit()

        q = "UPDATE gamestat_profile SET data = ? WHERE profileid = ? AND dindex = ? AND ptype = ?"
        q2 = q.replace("?", "%s") % (data, profileid, dindex, ptype)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [data, profileid, dindex, ptype])
        self.conn.commit()

    def pd_get(self, profileid, dindex, ptype):
        q = "SELECT * FROM gamestat_profile WHERE profileid = ? AND dindex = ? AND ptype = ?"
        q2 = q.replace("?", "%s") % (profileid, dindex, ptype)
        logger.log(-1, q2)

        c = self.conn.cursor()
        c.execute(q, [profileid, dindex, ptype])

        r = self.get_dict(c.fetchone())

        c.close()

        return r
