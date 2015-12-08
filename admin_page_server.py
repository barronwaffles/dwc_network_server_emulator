"""DWC Network Server Emulator

    Copyright (C) 2014 SMTDDR
    Copyright (C) 2014 kyle95wm
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

from twisted.web import server, resource
from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning
import base64
import codecs
import sqlite3
import collections
import json
import os.path
import logging

import other.utils as utils
import gamespy.gs_utility as gs_utils
import dwc_config

logger = dwc_config.get_logger('AdminPage')
_, port = dwc_config.get_ip_port('AdminPage')


# Example of adminpageconf.json
#
# {"username":"admin","password":"opensesame"}
#
# NOTE: Must use double-quotes or json module will fail
# NOTE2: Do not check the .json file into public git!

adminpageconf = None
admin_username = None
admin_password = None

if os.path.exists('adminpageconf.json'):
    try:
        adminpageconf = json.loads(file('adminpageconf.json').read().strip())
        admin_username = str(adminpageconf['username'])
        admin_password = str(adminpageconf['password'])
    except Exception as e:
        logger.log(logging.WARNING,
                   "Couldn't read adminpageconf.json. "
                   "Admin page will not be available.")
        logger.log(logging.WARNING, str(e))
        adminpageconf = None
        admin_username = None
        admin_password = None
else:
    logger.log(logging.INFO,
               "adminpageconf.json not found. "
               "Admin page will not be available.")


class AdminPage(resource.Resource):
    isLeaf = True

    def __init__(self, adminpage):
        self.adminpage = adminpage

    def get_header(self, title=None):
        if not title:
            title = 'AltWfc Admin Page'
        s = """
        <html>
        <head>
            <title>%s</title>
        </head>
        <body>
            <p>
                %s | %s | %s
            </p>
        """ % (title,
               '<a href="/banhammer">All Users</a>',
               '<a href="/consoles">Consoles</a>',
               '<a href="/banlist">Active Bans</a>')
        return s

    def get_footer(self):
        s = """
        </body>
        </html>
        """
        return s

    def is_authorized(self, request):
        is_auth = False
        response_code = 401
        error_message = "Authorization required!"
        address = request.getClientIP()
        try:
            expected_auth = base64.encodestring(
                admin_username + ":" + admin_password
            ).strip()
            actual_auth = request.getAllHeaders()['authorization'] \
                .replace("Basic ", "") \
                .strip()
            if actual_auth == expected_auth:
                logger.log(logging.INFO, "%s Auth Success", address)
                is_auth = True
        except Exception as e:
            logger.log(logging.INFO, "%s Auth Error: %s", address, str(e))
        if not is_auth:
            logger.log(logging.INFO, "%s Auth Failure", address)
            request.setResponseCode(response_code)
            request.setHeader('WWW-Authenticate', 'Basic realm="ALTWFC"')
            request.write(error_message)
        return is_auth

    def update_banlist(self, request):
        address = request.getClientIP()
        dbconn = sqlite3.connect('gpcm.db')
        gameid = request.args['gameid'][0].upper().strip()
        ipaddr = request.args['ipaddr'][0].strip()
        actiontype = request.args['action'][0]
        if not gameid.isalnum():
            request.setResponseCode(500)
            logger.log(logging.INFO,
                       "%s Bad data %s %s",
                       address, gameid, ipaddr)
            return "Bad data"

        # This strips the region identifier from game IDs, not sure if this
        # actually always accurate but limited testing suggests it is
        if len(gameid) > 3:
            gameid = gameid[:-1]

        if actiontype == 'ban':
            dbconn.cursor().execute(
                'INSERT INTO banned VALUES(?,?)',
                (gameid, ipaddr)
            )
            responsedata = "Added gameid=%s, ipaddr=%s" % (gameid, ipaddr)
        else:
            dbconn.cursor().execute(
                'DELETE FROM banned WHERE gameid=? AND ipaddr=?',
                (gameid, ipaddr)
            )
            responsedata = "Removed gameid=%s, ipaddr=%s" % (gameid, ipaddr)
        dbconn.commit()
        dbconn.close()
        logger.log(logging.INFO, "%s %s", address, responsedata)
        request.setHeader("Content-Type", "text/html; charset=utf-8")

        referer = request.getHeader('referer')
        if not referer:
            referer = "/banhammer"
        request.setHeader("Location", referer)

        request.setResponseCode(303)
        return responsedata

    def update_consolelist(self, request):
        address = request.getClientIP()
        dbconn = sqlite3.connect('gpcm.db')
        macadr = request.args['macadr'][0].strip()
        actiontype = request.args['action'][0]
        if not macadr.isalnum():
            request.setResponseCode(500)
            logger.log(logging.INFO, "%s Bad data %s", address, macadr)
            return "Bad data"
        if actiontype == 'add':
            dbconn.cursor().execute(
                'INSERT INTO pending VALUES(?)',
                (macadr,)
            )
            dbconn.cursor().execute(
                'INSERT INTO registered VALUES(?)',
                (macadr,)
            )
            responsedata = "Added macadr=%s" % (macadr)
        elif actiontype == 'activate':
            dbconn.cursor().execute(
                'INSERT INTO registered VALUES(?)',
                (macadr,)
            )
            responsedata = "Activated console belonging to %s" % (macadr)
        else:
            dbconn.cursor().execute(
                'DELETE FROM pending WHERE macadr=?',
                (macadr,)
            )
            dbconn.cursor().execute(
                'DELETE FROM registered WHERE macadr=?',
                (macadr,)
            )
            responsedata = "Removed macadr=%s" % (macadr)
        dbconn.commit()
        dbconn.close()
        logger.log(logging.INFO, "%s %s", address, responsedata)
        request.setHeader("Content-Type", "text/html; charset=utf-8")
        request.setHeader("Location", "/consoles")
        referer = request.getHeader('referer')
        request.setResponseCode(303)
        if not referer:
            referer = "/banhammer"
        request.setHeader("Location", referer)

        request.setResponseCode(303)
        return responsedata

    def render_banlist(self, request):
        address = request.getClientIP()
        dbconn = sqlite3.connect('gpcm.db')
        logger.log(logging.INFO, "%s Viewed banlist", address)
        responsedata = """
        <a href="http://%%20:%%20@%s">[CLICK HERE TO LOG OUT]</a>
        <table border='1'>
        <tr>
            <td>gameid</td>
            <td>ipAddr</td>
        </tr>""" % (request.getHeader('host'))

        for row in dbconn.cursor().execute("SELECT * FROM banned"):
            gameid = str(row[0])
            ipaddr = str(row[1])
            # TODO: Use .format()/positional arguments
            responsedata += """
            <tr>
                <td>%s</td>
                <td>%s</td>
                <td>
                <form action='updatebanlist' method='POST'>
                    <input type='hidden' name='gameid' value='%s'>
                    <input type='hidden' name='ipaddr' value='%s'>
                    <input type='hidden' name='action' value='unban'>
                    <input type='submit' value='----- UNBAN -----'>
                </form>
                </td>
            </tr>""" % (gameid, ipaddr, gameid, ipaddr)

        responsedata += "</table>"
        dbconn.close()
        request.setHeader("Content-Type", "text/html; charset=utf-8")
        return responsedata

    def render_not_available(self, request):
        request.setResponseCode(403)
        request.setHeader('WWW-Authenticate', 'Basic realm="ALTWFC"')
        request.write('No admin credentials set. Admin page is not available.')

    def render_blacklist(self, request):
        sqlstatement = """
        SELECT users.profileid, enabled, data, users.gameid, console,
               users.userid
        FROM nas_logins
        INNER JOIN users
        ON users.userid = nas_logins.userid
        INNER JOIN (
            SELECT max(profileid) newestpid, userid, gameid, devname
            FROM users
            GROUP BY userid, gameid
        ) ij
        ON ij.userid = users.userid
        AND users.profileid = ij.newestpid
        ORDER BY users.gameid"""
        dbconn = sqlite3.connect('gpcm.db')
        banned_list = []
        for row in dbconn.cursor().execute("SELECT * FROM BANNED"):
            banned_list.append(str(row[0])+":"+str(row[1]))
        responsedata = """
        <a href="http://%%20:%%20@%s">[CLICK HERE TO LOG OUT]</a>
        <br><br>
        <table border='1'>"
        <tr>
            <td>ingamesn or devname</td>
            <td>gameid</td>
            <td>Enabled</td>
            <td>newest dwc_pid</td>"
            <td>gsbrcd</td>
            <td>userid</td>
            <td>ipAddr</td>
        </tr>""" % request.getHeader('host')

        for row in dbconn.cursor().execute(sqlstatement):
            dwc_pid = str(row[0])
            enabled = str(row[1])
            nasdata = collections.defaultdict(lambda: '', json.loads(row[2]))
            gameid = str(row[3])
            is_console = int(str(row[4]))
            userid = str(row[5])
            gsbrcd = str(nasdata['gsbrcd'])
            ipaddr = str(nasdata['ipaddr'])
            ingamesn = ''
            if 'ingamesn' in nasdata:
                ingamesn = str(nasdata['ingamesn'])
            elif 'devname' in nasdata:
                ingamesn = str(nasdata['devname'])
            if ingamesn:
                ingamesn = gs_utils.base64_decode(ingamesn)
                if is_console:
                    ingamesn = codecs.utf_16_be_decode(ingamesn)[0]
                else:
                    ingamesn = codecs.utf_16_le_decode(ingamesn)[0]
            else:
                ingamesn = '[NOT AVAILABLE]'
            responsedata += """
            <tr>
                <td>%s</td>
                <td>%s</td>
                <td>%s</td>
                <td>%s</td>
                <td>%s</td>
                <td>%s</td>
                <td>%s</td>
            """ % (ingamesn,
                   gameid,
                   enabled,
                   dwc_pid,
                   gsbrcd,
                   userid,
                   ipaddr)
            if gameid[:-1] + ":" + ipaddr in banned_list:
                responsedata += """
                    <td>
                    <form action='updatebanlist' method='POST'>
                        <input type='hidden' name='gameid' value='%s'>
                        <input type='hidden' name='ipaddr' value='%s'>
                        <input type='hidden' name='action' value='unban'>
                        <input type='submit' value='----- unban -----'>
                    </form>
                    </td>
                </tr>""" % (gameid, ipaddr)
            else:
                responsedata += """
                    <td>
                    <form action='updatebanlist' method='POST'>
                        <input type='hidden' name='gameid' value='%s'>
                        <input type='hidden' name='ipaddr' value='%s'>
                        <input type='hidden' name='action' value='ban'>
                        <input type='submit' value='Ban'>
                    </form>
                    </td>
                </tr>
                """ % (gameid, ipaddr)

        responsedata += "</table>"
        dbconn.close()
        request.setHeader("Content-Type", "text/html; charset=utf-8")
        return responsedata.encode('utf-8')

    def enable_disable_user(self, request, enable=True):
        address = request.getClientIP()
        responsedata = ""
        userid = request.args['userid'][0]
        gameid = request.args['gameid'][0].upper()
        ingamesn = request.args['ingamesn'][0]

        if not userid.isdigit() or not gameid.isalnum():
            logger.log(logging.INFO,
                       "%s Bad data %s %s",
                       address, userid, gameid)
            return "Bad data"

        dbconn = sqlite3.connect('gpcm.db')
        if enable:
            dbconn.cursor().execute(
                'UPDATE users SET enabled=1 '
                'WHERE gameid=? AND userid=?',
                (gameid, userid)
            )
            responsedata = "Enabled %s with gameid=%s, userid=%s" % \
                           (ingamesn, gameid, userid)
        else:
            dbconn.cursor().execute(
                'UPDATE users SET enabled=0 '
                'WHERE gameid=? AND userid=?',
                (gameid, userid)
            )
            responsedata = "Disabled %s with gameid=%s, userid=%s" % \
                           (ingamesn, gameid, userid)
        dbconn.commit()
        dbconn.close()
        logger.log(logging.INFO, "%s %s", address, responsedata)
        request.setHeader("Content-Type", "text/html; charset=utf-8")
        request.setHeader("Location", "/banhammer")
        request.setResponseCode(303)
        return responsedata

    def render_consolelist(self, request):
        address = request.getClientIP()
        dbconn = sqlite3.connect('gpcm.db')
        active_list = []
        for row in dbconn.cursor().execute("SELECT * FROM REGISTERED"):
            active_list.append(str(row[0]))
        logger.log(logging.INFO, "%s Viewed console list", address)
        responsedata = (
            '<a href="http://%20:%20@' + request.getHeader('host') +
            '">[CLICK HERE TO LOG OUT]</a>'
            "<form action='updateconsolelist' method='POST'>"
            "macadr:<input type='text' name='macadr'>\r\n"
            "<input type='hidden' name='action' value='add'>\r\n"
            "<input type='submit' value='Register and activate console'>"
            "</form>\r\n"
            "<table border='1'>"
            "<tr><td>macadr</td></tr>\r\n"
        )
        for row in dbconn.cursor().execute("SELECT * FROM pending"):
            macadr = str(row[0])
            if macadr in active_list:
                responsedata += """
                <tr>
                    <td>%s</td>
                    <td>
                    <form action='updateconsolelist' method='POST'>
                        <input type='hidden' name='macadr' value='%s'>
                        <input type='hidden' name='action' value='remove'>
                        <input type='submit' value='Un-register console'>
                    </form>
                    </td>
                </tr>""" % (macadr, macadr)
            else:
                responsedata += """
                <tr>
                    <td>%s</td>
                    <td>
                    <form action='updateconsolelist' method='POST'>
                        <input type='hidden' name='macadr' value='%s'>
                        <input type='hidden' name='action' value='activate'>
                        <input type='submit' value='Activate console'>
                    </form>
                    </td>
                </tr>""" % (macadr, macadr)
        responsedata += "</table>"
        dbconn.close()
        request.setHeader("Content-Type", "text/html; charset=utf-8")
        return responsedata

    def render_GET(self, request):
        if not adminpageconf:
            self.render_not_available(request)
            return ""
        if not self.is_authorized(request):
            return ""

        title = None
        response = ''
        if request.path == "/banlist":
            title = 'AltWfc Banned Users'
            response = self.render_banlist(request)
        elif request.path == "/banhammer":
            title = 'AltWfc Users'
            response = self.render_blacklist(request)
        elif request.path == "/consoles":
            title = "AltWfc Console List"
            response = self.render_consolelist(request)
        return self.get_header(title) + response + self.get_footer()

    def render_POST(self, request):
        if not adminpageconf:
            self.render_not_available(request)
            return ""
        if not self.is_authorized(request):
            return ""

        if request.path == "/updatebanlist":
            return self.update_banlist(request)
        if request.path == "/updateconsolelist":
            return self.update_consolelist(request)
        else:
            return self.get_header() + self.get_footer()


class AdminPageServer(object):
    def start(self):
        site = server.Site(AdminPage(self))
        reactor.listenTCP(port, site)
        logger.log(logging.INFO,
                   "Now listening for connections on port %d...",
                   port)
        try:
            if not reactor.running:
                reactor.run(installSignalHandlers=0)
        except ReactorAlreadyRunning:
            pass


if __name__ == "__main__":
    AdminPageServer().start()
