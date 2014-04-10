import sqlite3
import hashlib
import itertools
import other.utils as utils
import time

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
            c.execute('''CREATE TABLE users (profileid INT, userid TEXT, password TEXT, gsbrcd TEXT, email TEXT, uniquenick TEXT, pid TEXT, lon TEXT, lat TEXT, loc TEXT, firstname TEXT, lastname TEXT, stat TEXT, partnerid TEXT, console INT, csnum TEXT, cfc TEXT, bssid TEXT, devname TEXT, birth TEXT, sig TEXT)''')
            c.execute('''CREATE TABLE sessions (session TEXT, profileid INT)''')
            c.execute('''CREATE TABLE buddies (userProfileId INT, buddyProfileId INT, time INT, status INT, notified INT)''')
            self.conn.commit()

    def get_dict(self, row):
        if row == None:
            return None

        return dict(itertools.izip(row.keys(), row))

    # User functions
    def get_next_free_profileid(self):
        # TODO: Make profile ids start at 1 for each game?
        c = self.conn.cursor()
        c.execute("SELECT max(profileid) FROM users")

        r = self.get_dict(c.fetchone())

        profileid = 1 # Cannot be 0 or else it freezes the game.
        if r != None and r['max(profileid)'] != None:
            profileid = int(r['max(profileid)']) + 1

        c.close()

        return profileid

    def check_user_exists(self, userid, gsbrcd):
        c = self.conn.cursor()
        c.execute("SELECT * FROM users WHERE userid = ? and gsbrcd = ?", [userid, gsbrcd])

        r = self.get_dict(c.fetchone())

        valid_user = False  # Default, user doesn't exist
        if r != None:
            valid_user = True  # Valid password

        c.close()
        return valid_user

    def check_profile_exists(self, profileid):
        c = self.conn.cursor()
        c.execute("SELECT * FROM users WHERE profileid = ?", [profileid])

        r = self.get_dict(c.fetchone())

        valid_profile = False  # Default, user doesn't exist
        if r != None:
            valid_profile = True  # Valid password

        c.close()
        return valid_profile

    def get_profile_from_profileid(self, profileid):
        profile = {}
        if profileid != None:
            c = self.conn.cursor()
            c.execute("SELECT * FROM users WHERE profileid = ?", [profileid])

            profile = self.get_dict(c.fetchone())

        c.close()
        return profile

    def perform_login(self, userid, password, gsbrcd):
        c = self.conn.cursor()
        c.execute("SELECT * FROM users WHERE userid = ? and gsbrcd = ?", [userid, gsbrcd])

        r = self.get_dict(c.fetchone())

        profileid = None  # Default, user doesn't exist
        if r != None:
            md5 = hashlib.md5()
            md5.update(password)

            if r['password'] == md5.hexdigest():
                profileid = r['profileid']  # Valid password

        c.close()
        return profileid

    def create_user(self, userid, password, email, uniquenick, gsbrcd, console, csnum, cfc, bssid, devname, birth):
        if self.check_user_exists(userid, gsbrcd) == 0:
            profileid = self.get_next_free_profileid()

            pid = "11"  # Always 11??? Is this important? Not to be confused with dwc_pid.
                        # The three games I found it in (Tetris DS, Advance Wars - Days of Ruin, and
                        # Animal Crossing: Wild World) all use \pid\11.
            lon = "0.000000"  # Always 0.000000?
            lat = "0.000000"  # Always 0.000000?
            loc = ""  # Always blank?
            firstname = ""
            lastname = ""
            stat = ""
            partnerid = ""
            sig = utils.generate_random_hex_str(32)

            # Hash password before entering it into the database.
            # For now I'm using a very simple MD5 hash.
            # TODO: Replace with something stronger later, although it's overkill for the NDS.
            md5 = hashlib.md5()
            md5.update(password)
            password = md5.hexdigest()

            c = self.conn.cursor()
            c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      [profileid, str(userid), password, gsbrcd, email, uniquenick, pid, lon, lat, loc, firstname, lastname, stat, partnerid, console, csnum, cfc, bssid, devname, birth, sig])
            c.close()

            self.conn.commit()

            return profileid

    def get_user_list(self):
        c = self.conn.cursor()

        users = []
        for row in c.execute("SELECT * FROM users"):
            users.append(self.get_dict(row))

        return users

    def update_profile(self, session_key, field):
        profileid = self.get_profileid_from_session_key(session_key)

        if profileid != -1:
            # Found profile id associated with session key.
            # Start replacing each field one by one.
            # TODO: Optimize this so it's done all in one update.
            # FIXME: Possible security issue due to embedding an unsanitized string directly into the statement.
            c = self.conn.cursor()
            print "UPDATE users SET %s = %s WHERE profileid = %s" % (field[0], field[1], profileid)
            c.execute("UPDATE users SET %s = ? WHERE profileid = ?" % (field[0]), [field[1], profileid])
            self.conn.commit()

    # Session functions
    # TODO: Cache session keys so we don't have to query the database every time we get a profile id.
    def get_profileid_from_session_key(self, session_key):
        c = self.conn.cursor()
        c.execute("SELECT profileid FROM sessions WHERE session = ?", [session_key])

        r = self.get_dict(c.fetchone())

        profileid = -1  # Default, invalid session key
        if r != None:
            profileid = r['profileid']

        c.close()
        return profileid

    def get_profile_from_session_key(self, session_key):
        profileid = self.get_profileid_from_session_key(session_key)

        profile = {}
        if profileid != None:
            c = self.conn.cursor()
            c.execute("SELECT profileid FROM sessions WHERE session = ?", [session_key])

            profile = self.get_dict(c.fetchone())

        c.close()
        return profile

    def generate_session_key(self, min_size):
        session_key = utils.generate_random_number_str(min_size)

        c = self.conn.cursor()
        for r in c.execute("SELECT session FROM sessions WHERE session = ?", [session_key]):
            session_key = utils.generate_random_number_str(min_size)

        return session_key

    def delete_session(self, profileid):
        c = self.conn.cursor()
        c.execute("DELETE FROM sessions WHERE profileid = ?", [profileid])
        self.conn.commit()

    def create_session(self, profileid):
        if profileid != None and self.check_profile_exists(profileid) == False:
            return None

        # Remove any old sessions associated with this user id
        self.delete_session(profileid)

        # Create new session
        session_key = self.generate_session_key(9)

        c = self.conn.cursor()
        c.execute("INSERT INTO sessions VALUES (?, ?)", [session_key, profileid])
        self.conn.commit()

        return session_key

    def get_session_list(self, profileid=None):
        c = self.conn.cursor()

        sessions = []
        if profileid != None:
            r = c.execute("SELECT * FROM sessions WHERE profileid = ?", [profileid])
        else:
            r = c.execute("SELECT * FROM sessions")

        for row in r:
            sessions.append(self.get_dict(row))

        return sessions

    # Buddy functions
    def add_buddy(self, userProfileId, buddyProfileId):
        c = self.conn.cursor()
        now = int(time.time())
        c.execute("INSERT INTO buddies VALUES (?, ?, ?, ?, ?)", [userProfileId, buddyProfileId, now, 0, 0]) # 0 will mean not authorized
        self.conn.commit()

    def auth_buddy(self, userProfileId, buddyProfileId):
        c = self.conn.cursor()
        c.execute("UPDATE buddies SET status = ? WHERE userProfileId = ? AND buddyProfileId = ?", [1, userProfileId, buddyProfileId]) # 1 will mean authorized
        self.conn.commit()

    def get_buddy(self, userProfileId, buddyProfileId):
        profile = {}
        if userProfileId != None and buddyProfileId != None:
            c = self.conn.cursor()
            c.execute("SELECT * FROM buddies WHERE userProfileId = ? AND buddyProfileId = ?", [userProfileId, buddyProfileId])
            profile = self.get_dict(c.fetchone())

        c.close()
        return profile

    def delete_buddy(self, userProfileId, buddyProfileId):
        c = self.conn.cursor()
        c.execute("DELETE FROM buddies WHERE userProfileId = ? AND buddyProfileId = ?", [userProfileId, buddyProfileId])
        self.conn.commit()

    def get_buddy_list(self, userProfileId):
        c = self.conn.cursor()

        users = []
        for row in c.execute("SELECT * FROM buddies WHERE userProfileId = ?", [userProfileId]):
            users.append(self.get_dict(row))

        return users

    def get_pending_buddy_requests(self, userProfileId):
        c = self.conn.cursor()

        users = []
        for row in c.execute("SELECT * FROM buddies WHERE buddyProfileId = ? AND status = 0", [userProfileId]):
            users.append(self.get_dict(row))

        return users

    def buddy_need_auth_message(self, userProfileId):
        c = self.conn.cursor()

        users = []
        for row in c.execute("SELECT * FROM buddies WHERE buddyProfileId = ? AND status = 1 AND notified = 0", [userProfileId]):
            users.append(self.get_dict(row))

        return users

    def buddy_sent_auth_message(self, userProfileId, buddyProfileId):
        c = self.conn.cursor()
        c.execute("UPDATE buddies SET notified = ? WHERE userProfileId = ? AND buddyProfileId = ?", [1, userProfileId, buddyProfileId]) # 1 will mean that the player has been sent the "
        self.conn.commit()
