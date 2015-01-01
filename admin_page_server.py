#Make sure you change the password to something else and don't commit it to public github!
admin_username = "admin"
admin_password = "opensesame"

from twisted.web import server, resource
from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning
import base64
import codecs 
import sqlite3
import json
import time
import datetime
import logging
import other.utils as utils
import gamespy
import gamespy.gs_utility as gs_utils

logger_output_to_console = True
logger_output_to_file = True
logger_name = "AdminPage"
logger_filename = "admin_page.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)


class AdminPage(resource.Resource):
    isLeaf = True

    def __init__(self,adminpage):
        self.adminpage = adminpage

    def is_authorized(self, request):
        is_auth = False
        response_code = 401
        error_message = "Authorization required!"
        address = request.getClientIP()
        try:
            expected_auth = base64.encodestring(admin_username+":"+admin_password).strip()
            actual_auth = request.getAllHeaders()['authorization'].replace("Basic ","").strip()
            if actual_auth == expected_auth:
                if actual_auth == 'YWRtaW46b3BlbnNlc2FtZQ==':
                    error_message = ( 'You must change the default login info'
                    '<a href="http://%20:%20@'+request.getHeader('host')+'">[LOG OUT]</a>' )
                    response_code = 500
                else:
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

    def render_GET(self, request):
        if not self.is_authorized(request):
            return ""
        if request.path != "/banhammer":
            request.setResponseCode(500)
            return "wrong url path"
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
        responsedata = ("<html><meta charset='utf-8'><table border='1'>\r\n"
            "<title>altwfc admin page</title>"
            '<a href="http://%20:%20@'+request.getHeader('host')+'">[CLICK HERE TO LOG OUT]</a>'
            "<tr><td>ingamesn or devname</td><td>gameid</td>"
            "<td>Enabled</td><td>newest dwc_pid</td>"
            "<td>gsbrcd</td><td>userid</td></tr>\r\n")
        for row in dbconn.cursor().execute(sqlstatement):
            dwc_pid = str(row[0])
            enabled = str(row[1])
            nasdata = json.loads(row[2])
            gameid = str(row[3])
            is_console = int(str(row[4]))
            userid = str(row[5])
            gsbrcd = str(nasdata['gsbrcd'])
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
            if enabled == "1":
                responsedata += ("<td><form action='disableuser' method='POST'>"
                "<input type='hidden' name='userid' value='"+userid+"'>"
                "<input type='hidden' name='gameid' value='"+gameid+"'>"
                "<input type='hidden' name='ingamesn' value='"+ingamesn+"'>"
                "<input type='submit' value='Ban'></form></td>")
            else:
                responsedata += ("<td><form action='enableuser' method='POST'>"
                "<input type='hidden' name='userid' value='"+userid+"'>"
                "<input type='hidden' name='gameid' value='"+gameid+"'>"
                "<input type='hidden' name='ingamesn' value='"+ingamesn+"'>"
                "<input type='submit' value='----- unban -----'></form></td>")
        responsedata += "</tr></table></html>" 
        dbconn.close()
        request.setHeader("Content-Type", "text/html; charset=utf-8")
        return responsedata.encode('utf-8')

    def render_POST(self, request):
        if not self.is_authorized(request):
            return ""
        if request.path != "/enableuser" and request.path != "/disableuser":
            request.setResponseCode(500)
            return "wrong url path"
        address = request.getClientIP()
        responsedata = ""
        userid = request.args['userid'][0]
        gameid = request.args['gameid'][0].upper()
        ingamesn = request.args['ingamesn'][0]

        if not userid.isdigit() or not gameid.isalnum():
            logger.log(logging.INFO,address+" Bad data "+userid+" "+gameid)
            return "Bad data"

        dbconn = sqlite3.connect('gpcm.db')
        if request.path == "/enableuser":
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
        return responsedata


class AdminPageServer(object):
    def start(self):
        site = server.Site(AdminPage(self))
        reactor.listenTCP(9009, site)
        try:
            if reactor.running == False:
                reactor.run(installSignalHandlers=0)
        except ReactorAlreadyRunning:
            pass

if __name__ == "__main__":
    AdminPageServer().start()

