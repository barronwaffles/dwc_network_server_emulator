#    DWC Network Server Emulator
#    Copyright (C) 2014 polaris-
#    Copyright (C) 2014 ToadKing
#    Copyright (C) 2014 AdmiralCurtiss
#    Copyright (C) 2014 msoucy
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

import base64
import json
import logging
import time
import urlparse
import BaseHTTPServer
import SocketServer
import threading
import os
import random
import traceback

import gamespy.gs_database as gs_database
import gamespy.gs_utility as gs_utils
import other.utils as utils

logger_output_to_console = True
logger_output_to_file = True
logger_name = "NasServer"
logger_filename = "nas_server.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

# if a game from this list requests a file listing, the server will return that only one exists and return a random one
# this is used for Mystery Gift distribution on Generation 4 Pokemon games
gamecodes_return_random_file = ['ADAD', 'ADAE', 'ADAF', 'ADAI', 'ADAJ', 'ADAK', 'ADAS', 'CPUD', 'CPUE', 'CPUF', 'CPUI', 'CPUJ', 'CPUK', 'CPUS', 'IPGD', 'IPGE', 'IPGF', 'IPGI', 'IPGJ', 'IPGK', 'IPGS']

#address = ("0.0.0.0", 80)
address = ("127.0.0.1", 9000)

class NasServer(object):
    def start(self):
        httpd = NasHTTPServer((address[0], address[1]), NasHTTPServerHandler)
        t = threading.Thread(target=httpd.serve_forever)
        t.daemon = True
        t.start()
        logger.log(logging.INFO, "Now listening for connections on %s:%d...", address[0], address[1])
        httpd.serve_forever()

class NasHTTPServer(SocketServer.ThreadingMixIn,BaseHTTPServer.HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        #self.db = gs_database.GamespyDatabase()
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)

class NasHTTPServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def version_string(self):
        return "Nintendo Wii (http)"

    def do_GET(self):
        self.server = lambda:None
        self.server.db = gs_database.GamespyDatabase()

        try:
            # conntest server
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("X-Organization", "Nintendo")
            self.send_header("Server", "BigIP")
            self.end_headers()
            self.wfile.write("ok")
        except:
            logger.log(logging.ERROR, "Unknown exception: %s" % traceback.format_exc())

    def do_POST(self):
        self.server = lambda:None
        self.server.db = gs_database.GamespyDatabase()

        try:
            length = int(self.headers['content-length'])
            post = self.str_to_dict(self.rfile.read(length))
            if self.client_address[0] == '127.0.0.1':
                client_address = (self.headers.get('x-forwarded-for', self.client_address[0]), self.client_address[1])
            else:
                client_address = self.client_address

            post['ipaddr'] = client_address[0]

            if self.path == "/ac":
                logger.log(logging.DEBUG, "Request to %s from %s", self.path, client_address)
                logger.log(logging.DEBUG, post)
                ret = {
                    "datetime": time.strftime("%Y%m%d%H%M%S"),
                    "retry": "0"
                }
                action = post["action"]
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.send_header("NODE", "wifiappe1")

                if action == "acctcreate":
                    # TODO: test for duplicate accounts
                    if self.server.db.is_banned(post):
                        logger.log(logging.DEBUG, "acctcreate denied for banned user "+str(post))
                        ret = {
                            "datetime": time.strftime("%Y%m%d%H%M%S"),
                            "returncd": "3913",
                            "locator": "gamespy.com",
                            "retry": "1",
                            "reason": "User banned."
                        }
                    else:
                        ret["returncd"] = "002"
                        ret['userid'] = self.server.db.get_next_available_userid()

                        logger.log(logging.DEBUG, "acctcreate response to %s", client_address)
                        logger.log(logging.DEBUG, ret)

                    ret = self.dict_to_str(ret)

                elif action == "login":
                    if self.server.db.is_banned(post):
                        logger.log(logging.DEBUG, "login denied for banned user "+str(post))
                        ret = {
                            "datetime": time.strftime("%Y%m%d%H%M%S"),
                            "returncd": "3914",
                            "locator": "gamespy.com",
                            "retry": "1",
                            "reason": "User banned."
                        }
                    else:
                        challenge = utils.generate_random_str(8)
                        post["challenge"] = challenge
                        
                        authtoken = self.server.db.generate_authtoken(post["userid"], post)
                        ret.update({
                            "returncd": "001",
                            "locator": "gamespy.com",
                            "challenge": challenge,
                            "token": authtoken,
                        })

                        logger.log(logging.DEBUG, "login response to %s", client_address)
                        logger.log(logging.DEBUG, ret)

                    ret = self.dict_to_str(ret)

                elif action == "SVCLOC" or action == "svcloc": # Get service based on service id number
                    ret["returncd"] = "007"
                    ret["statusdata"] = "Y"
                    authtoken = self.server.db.generate_authtoken(post["userid"], post)

                    if 'svc' in post:
                        if post["svc"] in ("9000", "9001"): # DLC host = 9000
                            ret["svchost"] = self.headers['host'] # in case the client's DNS isn't redirecting dls1.nintendowifi.net

                            # Brawl has 2 host headers which Apache chokes on, so only return the first one or else it won't work
                            ret["svchost"] = ret["svchost"].split(',')[0]

                            if post["svc"] == 9000:
                                ret["token"] = authtoken
                            else:
                                ret["servicetoken"] = authtoken
                        elif post["svc"] == "0000": # Pokemon requests this for some things
                            ret["servicetoken"] = authtoken
                            ret["svchost"] = "n/a"

                    logger.log(logging.DEBUG, "svcloc response to %s", client_address)
                    logger.log(logging.DEBUG, ret)

                    ret = self.dict_to_str(ret)
                else:
                    logger.log(logging.WARNING, "Unknown action request %s from %s!", self.path, client_address)


            elif self.path == "/pr":
                logger.log(logging.DEBUG, "Request to %s from %s", self.path, client_address)
                logger.log(logging.DEBUG, post)
                words = len(post["words"].split('\t'))
                wordsret = "0" * words
                ret = {
                    "prwords": wordsret,
                    "returncd": "000",
                    "datetime": time.strftime("%Y%m%d%H%M%S")
                }

                for l in "ACEJKP":
                    ret["prwords"+l] = wordsret

                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.send_header("NODE", "wifiappe1")

                logger.log(logging.DEBUG, "pr response to %s", client_address)
                logger.log(logging.DEBUG, ret)

                ret = self.dict_to_str(ret)

            elif self.path == "/download":
                logger.log(logging.DEBUG, "Request to %s from %s", self.path, client_address)
                logger.log(logging.DEBUG, post)

                action = post["action"]

                ret = ""
                dlcdir = os.path.abspath('dlc')
                dlcpath = os.path.abspath("dlc/" + post["gamecd"])
                dlc_contenttype = False

                if os.path.commonprefix([dlcdir, dlcpath]) != dlcdir:
                    logging.log(logging.WARNING, 'Attempted directory traversal attack "%s", cancelling.', dlcpath)
                    self.send_response(403)
                    return

                def safeloadfi(fn, mode='rb'):
                    '''
                    safeloadfi : string -> string

                    Safely load contents of a file, given a filename, and closing the file afterward
                    '''
                    with open(os.path.join(dlcpath, fn), mode) as fi:
                        return fi.read()

                if action == "count":
                    if post["gamecd"] in gamecodes_return_random_file:
                        ret = "1"
                    else:
                        count = 0

                        if os.path.exists(dlcpath):
                            count = len(os.listdir(dlcpath))

                            if os.path.isfile(dlcpath + "/_list.txt"):
                                attr1 = post.get("attr1", None)
                                attr2 = post.get("attr2", None)
                                attr3 = post.get("attr3", None)

                                dlcfi = safeloadfi("_list.txt")
                                lst = self.filter_list(dlcfi, attr1, attr2, attr3)
                                count = self.get_file_count(lst)

                        ret = "%d" % count

                if action == "list":
                    num = post.get("num", None)
                    offset = post.get("offset", None)

                    if num != None:
                        num = int(num)

                    if offset != None:
                        offset = int(offset)

                    attr1 = post.get("attr1", None)
                    attr2 = post.get("attr2", None)
                    attr3 = post.get("attr3", None)

                    if os.path.exists(dlcpath):
                        # Look for a list file first.
                        # If the list file exists, send the entire thing back to the client.
                        if os.path.isfile(os.path.join(dlcpath, "_list.txt")):
                            if post["gamecd"].startswith("IRA") and attr1.startswith("MYSTERY"):
                                # Pokemon BW Mystery Gifts, until we have a better solution for that
                                ret = self.filter_list(safeloadfi("_list.txt"), attr1, attr2, attr3)
                                ret = self.filter_list_g5_mystery_gift(ret, post["rhgamecd"])
                                ret = self.filter_list_by_date(ret, post["token"])
                            elif post["gamecd"] in gamecodes_return_random_file:
                                # Pokemon Gen 4 Mystery Gifts, same here
                                ret = self.filter_list(safeloadfi("_list.txt"), attr1, attr2, attr3)
                                ret = self.filter_list_by_date(ret, post["token"])
                            else:
                                # default case for most games
                                ret = self.filter_list(safeloadfi("_list.txt"), attr1, attr2, attr3, num, offset)

                if action == "contents":
                    # Get only the base filename just in case there is a path involved somewhere in the filename string.
                    dlc_contenttype = True
                    contents = os.path.basename(post["contents"])
                    ret = safeloadfi(contents)

                self.send_response(200)

                if dlc_contenttype == True:
                    self.send_header("Content-type", "application/x-dsdl")
                    self.send_header("Content-Disposition", "attachment; filename=\"" + post["contents"] + "\"")
                else:
                    self.send_header("Content-type", "text/plain")

                self.send_header("X-DLS-Host", "http://127.0.0.1/")

                logger.log(logging.DEBUG, "download response to %s", client_address)

                #if dlc_contenttype == False:
                #    logger.log(logging.DEBUG, ret)
            else:
                self.send_response(404)
                logger.log(logging.WARNING, "Unknown path request %s from %s!", self.path, client_address)
                return

            self.send_header("Content-Length", str(len(ret)))
            self.end_headers()
            self.wfile.write(ret)
        except:
            logger.log(logging.ERROR, "Unknown exception: %s" % traceback.format_exc())

    def str_to_dict(self, s):
        ret = urlparse.parse_qs(s)

        for k, v in ret.iteritems():
            try:
                # I'm not sure about the replacement for '-', but it'll at least let it be decoded.
                # For the most part it's not important since it's mostly used for the devname/ingamesn fields.
                ret[k] = base64.b64decode( urlparse.unquote( v[0] ).replace("*", "=").replace("?", "/").replace(">","+").replace("-","/") )
            except TypeError:
                print "Could not decode following string: ret[%s] = %s" % (k, v[0])
                print "url: %s" % s
                ret[k] = v[0] # If you don't assign it like this it'll be a list, which breaks other code.

        return ret

    def dict_to_str(self, dict):
        for k, v in dict.iteritems():
            dict[k] = base64.b64encode(v).replace("=", "*")

        # nas(wii).nintendowifi.net has a URL query-like format but does not use encoding for special characters
        return "&".join("{!s}={!s}".format(k, v) for k, v in dict.items()) + "\r\n"
    
    # custom selection for generation 5 mystery gifts, so that the random or data-based selection still works properly
    def filter_list_g5_mystery_gift(self, data, rhgamecd):
        if rhgamecd[2] == 'A':
            filterBit = 0x100000
        elif rhgamecd[2] == 'B':
            filterBit = 0x200000
        elif rhgamecd[2] == 'D':
            filterBit = 0x400000
        elif rhgamecd[2] == 'E':
            filterBit = 0x800000
        else:
            # unknown game, can't filter
            return data
        
        output = []
        for line in data.splitlines():
            lineBits = int(line.split('\t')[3], 16)
            if lineBits & filterBit == filterBit:
                output.append(line)
        return '\r\n'.join(output) + '\r\n'

    def filter_list_by_date(self, data, token):
        # allow user to control which file to receive by setting the local date
        # selected file will be the one at index (day of year) mod (file count)
        try:
            userData = self.server.db.get_nas_login(token)
            date = time.strptime(userData['devtime'], '%y%m%d%H%M%S')
            files = data.splitlines()
            ret = files[(int(date.tm_yday) - 1) % len(files)] + '\r\n'
        except:
            ret = self.filter_list_random_files(data, 1)
        return ret
        
    def filter_list_random_files(self, data, count):
        # Get [count] random files from the filelist
        samples = random.sample(data.splitlines(), count)
        return '\r\n'.join(samples) + '\r\n'

    def filter_list(self, data, attr1 = None, attr2 = None, attr3 = None, num = None, offset = None):
        if attr1 == None and attr2 == None and attr3 == None and num == None and offset == None:
            # Nothing to filter, just return the input data
            return data

        # Filter the list based on the attribute fields
        nc = lambda a, b: (a is None or a == b)
        attrs = lambda data: (len(data) == 6 and nc(attr1, data[2]) and nc(attr2, data[3]) and nc(attr3, data[4]))
        output = filter(lambda line: attrs(line.split("\t")), data.splitlines())

        if offset != None:
            output = output[offset:]

        if num != None:
            output = output[:num]

        # if nothing matches, at least return a newline; Pokemon BW at least expects this and will error without it
        return '\r\n'.join(output) + '\r\n'

    def get_file_count(self, data):
        return sum(1 for line in data.splitlines() if line)

if __name__ == "__main__":
    nas = NasServer()
    nas.start()
