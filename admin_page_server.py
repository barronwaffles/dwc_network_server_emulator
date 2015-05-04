#    DWC Network Server Emulator
#    Copyright (C) 2014 SMTDDR
#    Copyright (C) 2014 kyle95wm
#    Copyright (C) 2014 AdmiralCurtiss
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

from twisted.web import server, resource
from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning
import base64
import codecs 
import sqlite3
import collections
import json
import time
import datetime
import os.path
import logging
import other.utils as utils
import gamespy
import gamespy.gs_utility as gs_utils

logger_output_to_console = True
logger_output_to_file = True
logger_name = "AdminPage"
logger_filename = "admin_page.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)


#Example of adminpageconf.json
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
        logger.log(logging.WARNING, "Couldn't read adminpageconf.json. Admin page will not be available.")
        logger.log(logging.WARNING, str(e))
        adminpageconf = None
        admin_username = None
        admin_password = None
else:
    logger.log(logging.INFO, "adminpageconf.json not found. Admin page will not be available.")
    

class AdminPage(resource.Resource):
    isLeaf = True

    def __init__(self,adminpage):
        self.adminpage = adminpage

    def get_header(self, title = None):
        if not title:
            title = 'AltWfc Admin Page'
        s = (
        '<html>'
        '<head>'
            '<title>' + title + '</title>'
        '</head>'
        '<body>'
            '<p>'
                '<a href="/banhammer">All Users</a> | '
                '<a href="/banlist">Active Bans</a> '
            '</p>'
        )
        return s
    
    def get_footer(self):
        s = (
        '</body>'
        '</html>'
        )
        return s

    def is_authorized(self, request):
        is_auth = False
        response_code = 401
        error_message = "Authorization required!"
        address = request.getClientIP()
        try:
            expected_auth = base64.encodestring(admin_username+":"+admin_password).strip()
            actual_auth = request.getAllHeaders()['authorization'].replace("Basic ","").strip()
            if actual_auth == expected_auth:
                logger.log(logging.INFO,address+" Auth Success")
                is_auth = True
        except Exception,e:
                logger.log(logging.INFO,address+" Auth Error: "+str(e))
        if not is_auth:
            logger.log(logging.INFO,address+" Auth Failure")
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
            logger.log(logging.INFO,address+" Bad data "+gameid+" "+ipaddr)
            return "Bad data"
            
        # this strips the region identifier from game IDs, not sure if this actually always accurate but limited testing suggests it is
        if len(gameid) > 3:
            gameid = gameid[:-1]
            
        if actiontype == 'ban':
            dbconn.cursor().execute('insert into banned values(?,?)',(gameid,ipaddr))
            responsedata = "Added gameid=%s, ipaddr=%s" %  (gameid,ipaddr)
        else:
            dbconn.cursor().execute('delete from banned where gameid=? and ipaddr=?',(gameid,ipaddr))
            responsedata = "Removed gameid=%s, ipaddr=%s" %  (gameid,ipaddr)
        dbconn.commit()
        dbconn.close()
        logger.log(logging.INFO,address+" "+responsedata)
        request.setHeader("Content-Type", "text/html; charset=utf-8")
        
        referer = request.getHeader('referer')
        if not referer:
            referer = "/banhammer"
        request.setHeader("Location", referer)
        
        request.setResponseCode(303)
        return responsedata

    def render_banlist(self, request):
        address = request.getClientIP()
        dbconn = sqlite3.connect('gpcm.db')
        logger.log(logging.INFO,address+" Viewed banlist")
        responsedata = (""
            '<a href="http://%20:%20@'+request.getHeader('host')+'">[CLICK HERE TO LOG OUT]</a>'
            "<table border='1'>"
            "<tr><td>gameid</td><td>ipAddr</td></tr>\r\n")
        for row in dbconn.cursor().execute("select * from banned"):
            gameid = str(row[0])
            ipaddr = str(row[1])
            responsedata += ("<tr><td>"+gameid+"</td><td>"+ipaddr+"</td>"
                "<td><form action='updatebanlist' method='POST'>"
                "<input type='hidden' name='gameid' value='"+gameid+"'>"
                "<input type='hidden' name='ipaddr' value='"+ipaddr+"'>"
                "<input type='hidden' name='action' value='unban'>\r\n"
                "<input type='submit' value='----- UNBAN -----'></form></td></tr>\r\n")
        responsedata += "</table>" 
        dbconn.close()
        request.setHeader("Content-Type", "text/html; charset=utf-8")
        return responsedata
        
    def render_not_available(self, request):
        request.setResponseCode(403)
        request.setHeader('WWW-Authenticate', 'Basic realm="ALTWFC"')
        request.write('No admin credentials set. Admin page is not available.')
    
    def render_blacklist(self, request):
        sqlstatement = (''
            'select users.profileid,enabled,data,users.gameid,console,users.userid '
            'from nas_logins '
            'inner join users '
            'on users.userid = nas_logins.userid '
            'inner join ( '
            '    select max(profileid) newestpid, userid, gameid, devname '
            '    from users '
            '    group by userid,gameid) '
            'ij on ij.userid = users.userid and '
            'users.profileid = ij.newestpid '
            'order by users.gameid '
            '') 
        dbconn = sqlite3.connect('gpcm.db')
        banned_list = []
        for row in dbconn.cursor().execute("SELECT * FROM BANNED"):
            banned_list.append(str(row[0])+":"+str(row[1]))
        responsedata = (""
            '<a href="http://%20:%20@'+request.getHeader('host')+'">[CLICK HERE TO LOG OUT]</a>'
            "<br><br>"
            "<table border='1'>" 
            "<tr><td>ingamesn or devname</td><td>gameid</td>"
            "<td>Enabled</td><td>newest dwc_pid</td>"
            "<td>gsbrcd</td><td>userid</td><td>ipAddr</td></tr>\r\n")
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
            responsedata += "<tr>"
            responsedata += "<td>"+ingamesn+"</td>"
            responsedata += "<td>"+gameid+"</td>"
            responsedata += "<td>"+enabled+"</td>"
            responsedata += "<td>"+dwc_pid+"</td>"
            responsedata += "<td>"+gsbrcd+"</td>"
            responsedata += "<td>"+userid+"</td>"
            responsedata += "<td>"+ipaddr+"</td>"
            if gameid[:-1]+":"+ipaddr in banned_list:
                responsedata += ("<td><form action='updatebanlist' method='POST'>"
                "<input type='hidden' name='gameid' value='"+gameid+"'>"
                "<input type='hidden' name='ipaddr' value='"+ipaddr+"'>"
                "<input type='hidden' name='action' value='unban'>"
                "<input type='submit' value='----- unban -----'></form></td></tr>")
            else:
                responsedata += ("<td><form action='updatebanlist' method='POST'>"
                "<input type='hidden' name='gameid' value='"+gameid+"'>"
                "<input type='hidden' name='ipaddr' value='"+ipaddr+"'>"
                "<input type='hidden' name='action' value='ban'>"
                "<input type='submit' value='Ban'></form></td></tr>")
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
            logger.log(logging.INFO,address+" Bad data "+userid+" "+gameid)
            return "Bad data"

        dbconn = sqlite3.connect('gpcm.db')
        if enable:
            dbconn.cursor().execute('update users set enabled=1 '
            'where gameid=? and userid=?',(gameid,userid))
            responsedata = "Enabled %s with gameid=%s, userid=%s" % \
            (ingamesn,gameid,userid)
        else:
            dbconn.cursor().execute('update users set enabled=0 '
            'where gameid=? and userid=?',(gameid,userid))
            responsedata = "Disabled %s with gameid=%s, userid=%s" % \
            (ingamesn,gameid,userid)
        dbconn.commit()
        dbconn.close()
        logger.log(logging.INFO,address+" "+responsedata)
        request.setHeader("Content-Type", "text/html; charset=utf-8")
        request.setHeader("Location", "/banhammer")
        request.setResponseCode(303)
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
        
        return self.get_header(title) + response + self.get_footer()

    def render_POST(self, request):
        if not adminpageconf:
            self.render_not_available(request)
            return ""
        if not self.is_authorized(request):
            return ""
        
        if request.path == "/updatebanlist":
            return self.update_banlist(request)
        else:
            return self.get_header() + self.get_footer()

port = 9009
class AdminPageServer(object):
    def start(self):
        site = server.Site(AdminPage(self))
        reactor.listenTCP(port, site)
        logger.log(logging.INFO, "Now listening for connections on port %d...", port)
        try:
            if reactor.running == False:
                reactor.run(installSignalHandlers=0)
        except ReactorAlreadyRunning:
            pass

if __name__ == "__main__":
    AdminPageServer().start()
