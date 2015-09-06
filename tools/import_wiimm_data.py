"""Import the profile and friend data collected from the GameSpy servers by Wiimm

Put all *-nick and *-fc files to be imported into t into the data folder and then run this program to import them
into the database.

This may take some time to import all of the data on bigger files if you check if each entry is already in the database.
"""

import glob
import sys

sys.path.append('../')
import gamespy.gs_database as gs_database

db = gs_database.GamespyDatabase()

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

nicks = {}
#"CREATE TABLE users (profileid INT, userid TEXT, password TEXT, gsbrcd TEXT, email TEXT, uniquenick TEXT, pid TEXT, lon TEXT, lat TEXT, loc TEXT, firstname TEXT, lastname TEXT, stat TEXT, partnerid TEXT, console INT, csnum TEXT, cfc TEXT, bssid TEXT, devname TEXT, birth TEXT, sig TEXT)"
for nickfile in glob.glob("data/*-nick"):
    conn = db.conn
    c = conn.cursor()

    print "Parsing %s..." % nickfile

    cnt = 0
    for line in open(nickfile):
        s = line.lstrip().split(' ')

        if s[0] not in nicks:
            nicks[s[0]] = 1
            profileid = int(s[0])
            uniquenick = s[1]

            # Uncomment to check if the user exists before inserting, but it slows down things greatly.
            #if db.check_profile_exists(profileid) is not None:
            #    pass

            firstname = s[2]
            if firstname == "-":
                firstname = ""

            lastname = s[2]
            if lastname == "-":
                lastname = ""

            email = s[3]
            gsbrcd = uniquenick[9:]
            gameid = gsbrcd[:4]

            console = 0
            if firstname[:4] == "Wii:":
                console = 1

            if cnt == 0:
                conn.execute("begin")

            #print "Importing %d %s %s %s %s %s %s %d" % (profileid, uniquenick, firstname, lastname, email, gsbrcd, gameid, console)
            q = "INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            c.execute(q, [profileid, str(userid), password, gsbrcd, email, uniquenick, pid, lon, lat, loc, firstname, lastname, stat, partnerid, console, csnum, cfc, bssid, devname, birth, gameid])

            cnt += 1
            if cnt >= 50000:
                print "%d nicks inserted..." % len(nicks)
                conn.commit()
                cnt = 0
    conn.commit()
    c.close()
nicks = {}

#"CREATE TABLE buddies (userProfileId INT, buddyProfileId INT, time INT, status INT, notified INT, gameid TEXT)"
fcs = {}

status = 1 # Assume everyone has already accepted everyone else
notified = 1 # Assume that everyone has already been sent the notification
time = 0

for fcfiles in glob.glob("data/*-fc"):
    conn = db.conn
    c = conn.cursor()

    print "Parsing %s..." % fcfiles

    cnt = 0
    for line in open(fcfiles):
        s = line.split(' ')
        s = [x for x in s if x] # Remove any blank elements

        if s[1] not in fcs:
            fcs[s[1]] = 1

            userProfileId = int(s[1])
            gameid = s[2]

            if cnt == 0:
                conn.execute("begin")

            for friend in s[4:]:
                friend = friend.strip()

                if not friend or friend == '':
                    continue

                buddyProfileId = int(friend)

                q = "INSERT INTO buddies VALUES (?,?,?,?,?,?)"
                c.execute(q, [userProfileId, buddyProfileId, time, status, notified, gameid])

                cnt += 1

            if cnt >= 50000:
                print "%d buddies inserted..." % len(fcs)
                conn.commit()
                cnt = 0

    conn.commit()
    c.close()
fcs = {}