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
try:
    adminpageconf = file('adminpageconf.json').read().strip()
except Exception,e:
    logger.log(logging.INFO,"ERROR reading adminpageconf.json: "+str(e))
    logger.log(logging.INFO," *** WARN: adminpageconf.json could not be read. Creating one with default values")
    adminpageconf = '{"username":"admin","password":"opensesame"}'
    fd = open('adminpageconf.json','w')
    fd.write(adminpageconf)
    fd.close()
adminpageconf = json.loads(adminpageconf)
admin_username = str(adminpageconf['username']) 
admin_password = str(adminpageconf['password']) 

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
                    error_message = ( 'You must change the default values in adminpageconf.json'
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
        if actiontype == 'ban':
            dbconn.cursor().execute('insert into banned values(?,?)',(gameid[:-1],ipaddr))
            responsedata = "Added gameid=%s, ipaddr=%s" %  (gameid[:-1],ipaddr)
        else:
            dbconn.cursor().execute('delete from banned where gameid=? and ipaddr=?',(gameid[:-1],ipaddr))
            responsedata = "Removed gameid=%s, ipaddr=%s" %  (gameid[:-1],ipaddr)
        dbconn.commit()
        dbconn.close()
        logger.log(logging.INFO,address+" "+responsedata)
        request.setHeader("Content-Type", "text/html; charset=utf-8")
        return responsedata

    def render_banlist(self, request):
        address = request.getClientIP()
        dbconn = sqlite3.connect('gpcm.db')
        logger.log(logging.INFO,address+" Viewed banlist")
        responsedata = ("<html><meta charset='utf-8'>\r\n"
            "<title>altwfc admin page - banList</title>"
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
        responsedata += "</table></html>" 
        dbconn.close()
        request.setHeader("Content-Type", "text/html; charset=utf-8")
        return responsedata

    def render_GET(self, request):
        if not self.is_authorized(request):
            return ""
        if request.path == "/banlist":
            return self.render_banlist(request)
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
        banned_list = []
        for row in dbconn.cursor().execute("SELECT * FROM BANNED"):
            banned_list.append(str(row[0])+":"+str(row[1]))
        responsedata = ("<html><meta charset='utf-8'>\r\n"
            "<title>altwfc admin page</title>"
            '<a href="http://%20:%20@'+request.getHeader('host')+'">[CLICK HERE TO LOG OUT]</a>'
            "<br><br>"
            '<a href="http://'+request.getHeader('host')+'/banlist">BanList</a>'
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
        responsedata += "</table></html>" 
        dbconn.close()
        request.setHeader("Content-Type", "text/html; charset=utf-8")
        return responsedata.encode('utf-8')

    def render_POST(self, request):
        if not self.is_authorized(request):
            return ""
        if request.path == "/updatebanlist":
            return self.update_banlist(request)
        request.setResponseCode(500)
        return "wrong url path"

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
