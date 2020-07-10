"""DWC Network Server Emulator

    Copyright (C) 2014 polaris-
    Copyright (C) 2014 ToadKing
    Copyright (C) 2014 AdmiralCurtiss
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

import sqlite3
import hashlib
import itertools
import json
import time
import logging
from contextlib import closing

import other.utils as utils
import gamespy.gs_utility as gs_utils

# Logger settings
SQL_LOGLEVEL = logging.DEBUG
logger_output_to_console = True
logger_output_to_file = True
logger_name = "GamespyDatabase"
logger_filename = "gamespy_database.log"
logger = utils.create_logger(logger_name, logger_filename, -1,
                             logger_output_to_console, logger_output_to_file)


class Transaction(object):
    def __init__(self, connection):
        self.conn = connection
        self.databaseAltered = False

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if self.databaseAltered:
            self.conn.commit()
        return

    def _executeAndMeasure(self, cursor, statement, parameters):
        logTransactionId = utils.generate_random_str(8)

        logger.log(SQL_LOGLEVEL, "[%s] STARTING: " % logTransactionId +
                                 statement.replace('?', '%s') % parameters)

        timeStart = time.time()
        clockStart = time.clock()

        cursor.execute(statement, parameters)

        clockEnd = time.clock()
        timeEnd = time.time()
        timeDiff = timeEnd - timeStart

        logger.log(SQL_LOGLEVEL,
                   "[%s] DONE: Took %s real time / %s processor time",
                   logTransactionId, timeDiff, clockEnd - clockStart)
        if timeDiff > 1.0:
            logger.log(logging.WARNING,
                       "[%s] WARNING: SQL Statement took %s seconds!",
                       logTransactionId, timeDiff)
            logger.log(logging.WARNING,
                       "[%s] " % logTransactionId +
                       statement.replace('?', '%s') % parameters)
        return

    def queryall(self, statement, parameters=()):
        with closing(self.conn.cursor()) as cursor:
            self._executeAndMeasure(cursor, statement, parameters)
            rows = cursor.fetchall()
            return rows
        return []

    def queryone(self, statement, parameters=()):
        with closing(self.conn.cursor()) as cursor:
            self._executeAndMeasure(cursor, statement, parameters)
            row = cursor.fetchone()
            return row
        return []

    def nonquery(self, statement, parameters=()):
        with closing(self.conn.cursor()) as cursor:
            self._executeAndMeasure(cursor, statement, parameters)
            self.databaseAltered = True
        return


class GamespyDatabase(object):
    def __init__(self, filename='gpcm.db'):
        self.conn = sqlite3.connect(filename, timeout=10.0)
        self.conn.row_factory = sqlite3.Row

        # self.initialize_database()

    def __del__(self):
        self.close()

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def initialize_database(self):
        with Transaction(self.conn) as tx:
            # I highly doubt having everything in a database be of the type
            # TEXT is a good practice, but I'm not good with databases and
            # I'm not 100% positive that, for instance, that all user id's
            # will be ints, or all passwords will be ints, etc, despite not
            # seeing any evidence yet to say otherwise as far as Nintendo
            # DS games go.

            tx.nonquery("CREATE TABLE IF NOT EXISTS users"
                        " (profileid INT, userid TEXT, password TEXT,"
                        " gsbrcd TEXT, email TEXT, uniquenick TEXT,"
                        " pid TEXT, lon TEXT, lat TEXT, loc TEXT,"
                        " firstname TEXT, lastname TEXT, stat TEXT,"
                        " partnerid TEXT, console INT, csnum TEXT,"
                        " cfc TEXT, bssid TEXT, devname BLOB, birth TEXT,"
                        " gameid TEXT, enabled INT, zipcode TEXT, aim TEXT)")
            tx.nonquery("CREATE TABLE IF NOT EXISTS sessions"
                        " (session TEXT, profileid INT, loginticket TEXT)")
            tx.nonquery("CREATE TABLE IF NOT EXISTS buddies"
                        " (userProfileId INT, buddyProfileId INT, time INT,"
                        " status INT, notified INT, gameid TEXT,"
                        " blocked INT)")
            tx.nonquery("CREATE TABLE IF NOT EXISTS pending_messages"
                        " (sourceid INT, targetid INT, msg TEXT)")
            tx.nonquery("CREATE TABLE IF NOT EXISTS gamestat_profile"
                        " (profileid INT, dindex TEXT, ptype TEXT,"
                        " data TEXT)")
            tx.nonquery("CREATE TABLE IF NOT EXISTS gameinfo"
                        " (profileid INT, dindex TEXT, ptype TEXT,"
                        " data TEXT)")
            tx.nonquery("CREATE TABLE IF NOT EXISTS nas_logins"
                        " (userid TEXT, authtoken TEXT, data TEXT)")
            tx.nonquery("CREATE TABLE IF NOT EXISTS banned"
                        " (gameid TEXT, ipaddr TEXT)")
            tx.nonquery("CREATE TABLE IF NOT EXISTS pending (macadr TEXT)")
            tx.nonquery("CREATE TABLE IF NOT EXISTS registered (macadr TEXT)")

            # Create some indexes for performance.
            tx.nonquery("CREATE UNIQUE INDEX IF NOT EXISTS"
                        " gamestatprofile_triple"
                        " ON gamestat_profile(profileid,dindex,ptype)")
            tx.nonquery("CREATE UNIQUE INDEX IF NOT EXISTS"
                        " users_profileid_idx ON users (profileid)")
            tx.nonquery("CREATE INDEX IF NOT EXISTS"
                        " users_userid_idx ON users (userid)")
            tx.nonquery("CREATE INDEX IF NOT EXISTS"
                        " pending_messages_targetid_idx"
                        " ON pending_messages (targetid)")
            tx.nonquery("CREATE UNIQUE INDEX IF NOT EXISTS"
                        " sessions_session_idx ON sessions (session)")
            tx.nonquery("CREATE INDEX IF NOT EXISTS"
                        " sessions_loginticket_idx ON sessions (loginticket)")
            tx.nonquery("CREATE INDEX IF NOT EXISTS"
                        " sessions_profileid_idx ON sessions (profileid)")
            tx.nonquery("CREATE UNIQUE INDEX IF NOT EXISTS"
                        " nas_logins_authtoken_idx ON nas_logins (authtoken)")
            tx.nonquery("CREATE INDEX IF NOT EXISTS"
                        " nas_logins_userid_idx ON nas_logins (userid)")
            tx.nonquery("CREATE INDEX IF NOT EXISTS"
                        " buddies_userProfileId_idx"
                        " ON buddies (userProfileId)")
            tx.nonquery("CREATE INDEX IF NOT EXISTS"
                        " buddies_buddyProfileId_idx"
                        " ON buddies (buddyProfileId)")
            tx.nonquery("CREATE INDEX IF NOT EXISTS"
                        " gamestat_profile_profileid_idx"
                        " ON gamestat_profile (profileid)")

    def get_dict(self, row):
        if not row:
            return None

        return dict(itertools.izip(row.keys(), row))

    # User functions
    def get_next_free_profileid(self):
        """TODO: Make profile ids start at 1 for each game?

        TODO: This leads to a race condition if two users try to create
        accounts at the same time. Instead, it's better to create a new row
        and return the sqlite ROWID instead.
        """
        with Transaction(self.conn) as tx:
            row = tx.queryone("SELECT max(profileid) AS m FROM users")
            r = self.get_dict(row)

        profileid = 1  # Cannot be 0 or else it freezes the game.
        if r is not None and r['m'] is not None:
            profileid = int(r['m']) + 1

        return profileid

    def check_user_exists(self, userid, gsbrcd):
        with Transaction(self.conn) as tx:
            row = tx.queryone(
                "SELECT COUNT(*) FROM users WHERE userid = ? AND gsbrcd = ?",
                (userid, gsbrcd)
            )
            count = int(row[0])
        return count > 0

    def check_user_enabled(self, userid, gsbrcd):
        with Transaction(self.conn) as tx:
            row = tx.queryone(
                "SELECT enabled FROM users WHERE userid = ? AND gsbrcd = ?",
                (userid, gsbrcd)
            )
            enabled = int(row[0])
        return enabled > 0

    def check_profile_exists(self, profileid):
        with Transaction(self.conn) as tx:
            row = tx.queryone(
                "SELECT COUNT(*) FROM users WHERE profileid = ?",
                (profileid,)
            )
            count = int(row[0])
        return count > 0

    def get_profile_from_profileid(self, profileid):
        profile = {}
        if profileid:
            with Transaction(self.conn) as tx:
                row = tx.queryone(
                    "SELECT * FROM users WHERE profileid = ?",
                    (profileid,)
                )
                profile = self.get_dict(row)
        return profile

    def perform_login(self, userid, password, gsbrcd):
        with Transaction(self.conn) as tx:
            row = tx.queryone(
                "SELECT * FROM users WHERE userid = ? and gsbrcd = ?",
                (userid, gsbrcd)
            )
            r = self.get_dict(row)

        profileid = None  # Default, user doesn't exist
        if r is not None:
            # md5 = hashlib.md5()
            # md5.update(password)

            # if r['password'] == md5.hexdigest():
            #     profileid = r['profileid']  # Valid password

            if r['enabled'] == 1 and r['gsbrcd'] == gsbrcd:
                profileid = r['profileid']  # Valid password

        return profileid

    def create_user(self, userid, password, email, uniquenick, gsbrcd,
                    console, csnum, cfc, bssid, devname, birth, gameid,
                    macadr):
        if not self.check_user_exists(userid, gsbrcd):
            profileid = self.get_next_free_profileid()

            # Always 11??? Is this important? Not to be confused with dwc_pid.
            # The three games I found it in (Tetris DS, Advance Wars - Days of
            # Ruin, and Animal Crossing: Wild World) all use \pid\11.
            pid = "11"
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
            # TODO: Replace with something stronger later, although it's
            # overkill for the NDS.
            md5 = hashlib.md5()
            md5.update(password)
            password = md5.hexdigest()

            with Transaction(self.conn) as tx:
                q = "INSERT INTO users VALUES" \
                    " (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                tx.nonquery(q, (profileid, str(userid), password, gsbrcd,
                                email, uniquenick, pid, lon, lat, loc,
                                firstname, lastname, stat, partnerid,
                                console, csnum, cfc, bssid, devname, birth,
                                gameid, enabled, zipcode, aim))

            return profileid
        return None

    def import_user(self, profileid, uniquenick, firstname, lastname, email,
                    gsbrcd, gameid, console):
        if not self.check_profile_exists(profileid):
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

            with Transaction(self.conn) as tx:
                q = "INSERT INTO users VALUES" \
                    " (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                tx.nonquery(q, (profileid, str(userid), password, gsbrcd,
                                email, uniquenick, pid, lon, lat, loc,
                                firstname, lastname, stat, partnerid,
                                console, csnum, cfc, bssid, devname, birth,
                                gameid, enabled, zipcode, aim))

            return profileid

    def get_user_list(self):
        with Transaction(self.conn) as tx:
            rows = tx.queryall("SELECT * FROM users")

        return [self.get_dict(row) for row in rows]

    def save_pending_message(self, sourceid, targetid, msg):
        with Transaction(self.conn) as tx:
            tx.nonquery("INSERT INTO pending_messages VALUES (?,?,?)",
                        (sourceid, targetid, msg))

    def get_pending_messages(self, profileid):
        with Transaction(self.conn) as tx:
            rows = tx.queryall(
                "SELECT * FROM pending_messages WHERE targetid = ?",
                (profileid,)
            )

        return [self.get_dict(row) for row in rows]

    def update_profile(self, profileid, field):
        """Found profile id associated with session key.

        Start replacing each field one by one.
        TODO: Optimize this so it's done all in one update.
        TODO: Check if other values than firstname/lastname are set using this
        """
        if field[0] in ["firstname", "lastname"]:
            with Transaction(self.conn) as tx:
                q = "UPDATE users SET \"%s\" = ? WHERE profileid = ?"
                tx.nonquery(q % field[0], (field[1], profileid))

    # Session functions
    # TODO: Cache session keys so we don't have to query the database every
    # time we get a profile id.
    def get_profileid_from_session_key(self, session_key):
        with Transaction(self.conn) as tx:
            row = tx.queryone(
                "SELECT profileid FROM sessions WHERE session = ?",
                (session_key,)
            )
            r = self.get_dict(row)

        profileid = -1  # Default, invalid session key
        if r is not None:
            profileid = r['profileid']

        return profileid

    def get_profileid_from_loginticket(self, loginticket):
        with Transaction(self.conn) as tx:
            row = tx.queryone(
                "SELECT profileid FROM sessions WHERE loginticket = ?",
                (loginticket,)
            )

        profileid = -1
        if row:
            profileid = int(row[0])

        return profileid

    def get_profile_from_session_key(self, session_key):
        profileid = self.get_profileid_from_session_key(session_key)

        profile = {}
        if profileid:
            with Transaction(self.conn) as tx:
                row = tx.queryone(
                    "SELECT profileid FROM sessions WHERE session = ?",
                    (session_key,)
                )
                profile = self.get_dict(row)

        return profile

    def generate_session_key(self, min_size):
        """Generate session key.

        TODO: There's probably a better way to do this.
        The point is preventing duplicate session keys.
        """
        while True:
            with Transaction(self.conn) as tx:
                session_key = utils.generate_random_number_str(min_size)
                row = tx.queryone(
                    "SELECT COUNT(*) FROM sessions WHERE session = ?",
                    (session_key,)
                )
                count = int(row[0])
                if not count:
                    return session_key

    def delete_session(self, profileid):
        with Transaction(self.conn) as tx:
            tx.nonquery(
                "DELETE FROM sessions WHERE profileid = ?",
                (profileid,)
            )

    def create_session(self, profileid, loginticket):
        if profileid is not None and not self.check_profile_exists(profileid):
            return None

        # Remove any old sessions associated with this user id
        self.delete_session(profileid)

        # Create new session
        session_key = self.generate_session_key(8)
        with Transaction(self.conn) as tx:
            tx.nonquery(
                "INSERT INTO sessions VALUES (?, ?, ?)",
                (session_key, profileid, loginticket)
            )

        return session_key

    def get_session_list(self, profileid=None):
        with Transaction(self.conn) as tx:
            if profileid is not None:
                r = tx.queryall(
                    "SELECT * FROM sessions WHERE profileid = ?",
                    (profileid,)
                )
            else:
                r = tx.queryall("SELECT * FROM sessions")

        return [self.get_dict(row) for row in r]

    # nas server functions
    def get_nas_login(self, authtoken):
        with Transaction(self.conn) as tx:
            row = tx.queryone(
                "SELECT data FROM nas_logins WHERE authtoken = ?",
                (authtoken,)
            )
            r = self.get_dict(row)

        if r is None:
            return None
        else:
            return json.loads(r["data"])

    def get_nas_login_from_userid(self, userid):
        with Transaction(self.conn) as tx:
            row = tx.queryone(
                "SELECT data FROM nas_logins WHERE userid = ?",
                (userid,)
            )
            r = self.get_dict(row)

        if r is None:
            return None
        else:
            return json.loads(r["data"])

    def is_banned(self, postdata):
        with Transaction(self.conn) as tx:
            row = tx.queryone(
                "SELECT COUNT(*) FROM banned WHERE gameid = ? AND ipaddr = ?",
                (postdata['gamecd'][:-1], postdata['ipaddr'])
            )
        return int(row[0]) > 0

    def pending(self, postdata):
        with Transaction(self.conn) as tx:
            row = tx.queryone(
                "SELECT COUNT(*) FROM pending WHERE macadr = ?",
                (postdata['macadr'],)
            )
            return int(row[0]) > 0

    def registered(self, postdata):
        with Transaction(self.conn) as tx:
            row = tx.queryone(
                "SELECT COUNT(*) FROM registered WHERE macadr = ?",
                (postdata['macadr'],)
            )
            return int(row[0]) > 0

    def get_next_available_userid(self):
        with Transaction(self.conn) as tx:
            row = tx.queryone("SELECT max(userid) AS maxuser FROM users")
            r = self.get_dict(row)
        if r is None or r['maxuser'] is None:
            # Because all zeroes means Dolphin. Don't wanna get confused
            # during debugging later.
            return '0000000000002'
        else:
            userid = str(int(r['maxuser']) + 1)
            while len(userid) < 13:
                userid = "0" + userid
            return userid

    def generate_authtoken(self, userid, data):
        """Generate authentication token.

        Since the auth token passed back to the game will be random, we can
        make it small enough that there should never be a crash due to the
        size of the token.
        ^ real authtoken is 80 + 3 bytes though and I want to figure out
        what's causing the 52200 so I'm matching everything as closely as
        possible to the real thing.
        """
        size = 80

        # TODO: Another one of those questionable dupe-preventations
        while True:
            with Transaction(self.conn) as tx:
                authtoken = "NDS" + utils.generate_random_str(size)
                row = tx.queryone(
                    "SELECT COUNT(*) FROM nas_logins WHERE authtoken = ?",
                    (authtoken,)
                )
                count = int(row[0])
                if not count:
                    break

        with Transaction(self.conn) as tx:
            row = tx.queryone(
                "SELECT * FROM nas_logins WHERE userid = ?",
                (userid,)
            )
            r = self.get_dict(row)

        if "devname" in data:
            data["devname"] = gs_utils.base64_encode(data["devname"])
        if "ingamesn" in data:
            data["ingamesn"] = gs_utils.base64_encode(data["ingamesn"])

        data = json.dumps(data)

        with Transaction(self.conn) as tx:
            if r is None:  # no row, add it
                tx.nonquery(
                    "INSERT INTO nas_logins VALUES (?, ?, ?)",
                    (userid, authtoken, data)
                )
            else:
                tx.nonquery(
                    "UPDATE nas_logins SET authtoken = ?, data = ?"
                    " WHERE userid = ?",
                    (authtoken, data, userid)
                )

        return authtoken

    # Buddy functions
    def add_buddy(self, userProfileId, buddyProfileId):
        now = int(time.time())

        # status == 0 -> not authorized
        with Transaction(self.conn) as tx:
            tx.nonquery(
                "INSERT INTO buddies VALUES (?, ?, ?, ?, ?, ?, ?)",
                (userProfileId, buddyProfileId, now, 0, 0, "", 0)
            )

    def auth_buddy(self, userProfileId, buddyProfileId):
        # status == 1 -> authorized
        with Transaction(self.conn) as tx:
            tx.nonquery(
                "UPDATE buddies SET status = ?"
                " WHERE userProfileId = ? AND buddyProfileId = ?",
                (1, userProfileId, buddyProfileId)
            )

    def block_buddy(self, userProfileId, buddyProfileId):
        with Transaction(self.conn) as tx:
            tx.nonquery(
                "UPDATE buddies SET blocked = ?"
                " WHERE userProfileId = ? AND buddyProfileId = ?",
                (1, userProfileId, buddyProfileId)
            )

    def unblock_buddy(self, userProfileId, buddyProfileId):
        with Transaction(self.conn) as tx:
            tx.nonquery(
                "UPDATE buddies SET blocked = ?"
                " WHERE userProfileId = ? AND buddyProfileId = ?",
                (0, userProfileId, buddyProfileId)
            )

    def get_buddy(self, userProfileId, buddyProfileId):
        if userProfileId and buddyProfileId:
            with Transaction(self.conn) as tx:
                row = tx.queryone(
                    "SELECT * FROM buddies"
                    " WHERE userProfileId = ? AND buddyProfileId = ?",
                    (userProfileId, buddyProfileId)
                )
                return self.get_dict(row)
        return {}

    def delete_buddy(self, userProfileId, buddyProfileId):
        with Transaction(self.conn) as tx:
            tx.nonquery(
                "DELETE FROM buddies"
                " WHERE userProfileId = ? AND buddyProfileId = ?",
                (userProfileId, buddyProfileId)
            )

    def get_buddy_list(self, userProfileId):
        with Transaction(self.conn) as tx:
            rows = tx.queryall(
                "SELECT * FROM buddies"
                " WHERE userProfileId = ? AND blocked = 0",
                (userProfileId,)
            )

        return [self.get_dict(row) for row in rows]

    def get_blocked_list(self, userProfileId):
        with Transaction(self.conn) as tx:
            rows = tx.queryall(
                "SELECT * FROM buddies"
                " WHERE userProfileId = ? AND blocked = 1",
                (userProfileId,)
            )

        return [self.get_dict(row) for row in rows]

    def get_pending_buddy_requests(self, userProfileId):
        with Transaction(self.conn) as tx:
            rows = tx.queryall(
                "SELECT * FROM buddies"
                " WHERE buddyProfileId = ? AND status = 0",
                (userProfileId,)
            )

        return [self.get_dict(row) for row in rows]

    def buddy_need_auth_message(self, userProfileId):
        with Transaction(self.conn) as tx:
            rows = tx.queryall(
                "SELECT * FROM buddies"
                " WHERE buddyProfileId = ? AND status = 1 AND notified = 0",
                (userProfileId,)
            )

        return [self.get_dict(row) for row in rows]

    def buddy_sent_auth_message(self, userProfileId, buddyProfileId):
        with Transaction(self.conn) as tx:
            tx.nonquery(
                "UPDATE buddies SET notified = ?"
                " WHERE userProfileId = ? AND buddyProfileId = ?",
                (1, userProfileId, buddyProfileId)
            )

    # Gamestats-related functions
    def pd_insert(self, profileid, dindex, ptype, data):
        with Transaction(self.conn) as tx:
            row = tx.queryone(
                "SELECT COUNT(*) FROM gamestat_profile"
                " WHERE profileid = ? AND dindex = ? AND ptype = ?",
                (profileid, dindex, ptype)
            )
            count = int(row[0])
            if count > 0:
                tx.nonquery(
                    "UPDATE gamestat_profile SET data = ?"
                    " WHERE profileid = ? AND dindex = ? AND ptype = ?",
                    (data, profileid, dindex, ptype)
                )
            else:
                tx.nonquery(
                    "INSERT INTO gamestat_profile"
                    " (profileid, dindex, ptype, data) VALUES(?,?,?,?)",
                    (profileid, dindex, ptype, data)
                )

    def pd_get(self, profileid, dindex, ptype):
        with Transaction(self.conn) as tx:
            row = tx.queryone(
                "SELECT * FROM gamestat_profile"
                " WHERE profileid = ? AND dindex = ? AND ptype = ?",
                (profileid, dindex, ptype)
            )
        return self.get_dict(row)
