import base64
import json
import logging
import time
import urlparse
import BaseHTTPServer
import os
import random

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
        logger.log(logging.INFO, "Now listening for connections on %s:%d...", address[0], address[1])
        httpd.serve_forever()

class NasHTTPServer(BaseHTTPServer.HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        self.db = gs_database.GamespyDatabase()
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)

class NasHTTPServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def version_string(self):
        return "Nintendo Wii (http)"

    def do_GET(self):
        # conntest server
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("X-Organization", "Nintendo")
        self.send_header("Server", "BigIP")
        self.end_headers()
        self.wfile.write("ok")

    def do_POST(self):
        length = int(self.headers['content-length'])
        post = self.str_to_dict(self.rfile.read(length))
        ret = ''

        if self.path == "/ac":
            logger.log(logging.DEBUG, "Request to %s from %s", self.path, self.client_address)
            logger.log(logging.DEBUG, post)
            ret = {}
            ret["datetime"] = time.strftime("%Y%m%d%H%M%S")
            ret["retry"] = "0"
            action = post["action"]
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.send_header("NODE", "wifiappe1")

            if action == "acctcreate":
                # TODO: test for duplicate accounts
                ret["returncd"] = "002"

                logger.log(logging.DEBUG, "acctcreate response to %s", self.client_address)
                logger.log(logging.DEBUG, ret)

                ret = self.dict_to_str(ret)

            elif action == "login":
                ret["returncd"] = "001"
                ret["locator"] = "gamespy.com"
                challenge = utils.generate_random_str(8)
                ret["challenge"] = challenge
                post["challenge"] = challenge
                authtoken = self.server.db.generate_authtoken(post["userid"], post)
                ret["token"] = authtoken

                logger.log(logging.DEBUG, "login response to %s", self.client_address)
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

                logger.log(logging.DEBUG, "svcloc response to %s", self.client_address)
                logger.log(logging.DEBUG, ret)

                ret = self.dict_to_str(ret)
            else:
                logger.log(logging.WARNING, "Unknown action request %s from %s!", self.path, self.client_address)
                ret = ''


        elif self.path == "/pr":
            logger.log(logging.DEBUG, "Request to %s from %s", self.path, self.client_address)
            logger.log(logging.DEBUG, post)
            ret = {}

            words = len(post["words"].split('\t'))
            wordsret = "0" * words
            ret["prwords"] = wordsret
            ret["prwordsA"] = wordsret
            ret["prwordsC"] = wordsret
            ret["prwordsE"] = wordsret
            ret["prwordsJ"] = wordsret
            ret["prwordsK"] = wordsret
            ret["prwordsP"] = wordsret
            ret["returncd"] = "000"
            ret["datetime"] = time.strftime("%Y%m%d%H%M%S")

            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.send_header("NODE", "wifiappe1")

            logger.log(logging.DEBUG, "pr response to %s", self.client_address)
            logger.log(logging.DEBUG, ret)

            ret = self.dict_to_str(ret)

        elif self.path == "/download":
            logger.log(logging.DEBUG, "Request to %s from %s", self.path, self.client_address)
            logger.log(logging.DEBUG, post)

            action = post["action"]

            ret = ""
            dlcpath = "dlc/" + post["gamecd"]
            dlc_contenttype = False

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
                            attr1 = None
                            if "attr1" in post:
                                attr1 = post["attr1"]
                            attr2 = None
                            if "attr2" in post:
                                attr2 = post["attr2"]
                            attr3 = None
                            if "attr3" in post:
                                attr3 = post["attr3"]

                            lst = safeloadfi("_list.txt")
                            lst = self.filter_list(dlcfi.read(), attr1, attr2, attr3)
                            count = self.get_file_count(lst)

                    ret = "%d" % count

            if action == "list":
                num = int(post["num"])
                offset = int(post["offset"])

                attr1 = None
                if "attr1" in post:
                    attr1 = post["attr1"]
                attr2 = None
                if "attr2" in post:
                    attr2 = post["attr2"]
                attr3 = None
                if "attr3" in post:
                    attr3 = post["attr3"]

                if os.path.exists(dlcpath):
                    # Look for a list file first.
                    # If the list file exists, send the entire thing back to the client.
                    if os.path.isfile(os.path.join(dlcpath, "_list.txt")):
                        ret = self.filter_list(safeloadfi("_list.txt"), attr1, attr2, attr3)

                        if post["gamecd"] in gamecodes_return_random_file:
                            ret = self.filter_list_random_files(ret, 1)

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

            logger.log(logging.DEBUG, "download response to %s", self.client_address)

            #if dlc_contenttype == False:
            #    logger.log(logging.DEBUG, ret)
        else:
            logger.log(logging.WARNING, "Unknown path request %s from %s!", self.path, self.client_address)

        self.send_header("Content-Length", str(len(ret)))
        self.end_headers()
        self.wfile.write(ret)

    def str_to_dict(self, str):
        ret = urlparse.parse_qs(str)

        for k, v in ret.iteritems():
            try:
                # I'm not sure about the replacement for '-', but it'll at least let it be decoded.
                # For the most part it's not important since it's mostly used for the devname/ingamesn fields.
                ret[k] = base64.b64decode(v[0].replace("*", "=").replace("?", "/").replace(">","+").replace("-","/"))
            except TypeError:
                print "Could not decode following string: ret[%s] = %s" % (k, v[0])
                print "url: %s" % str
                ret[k] = v[0] # If you don't assign it like this it'll be a list, which breaks other code.

        return ret

    def dict_to_str(self, dict):
        for k, v in dict.iteritems():
            dict[k] = base64.b64encode(v).replace("=", "*")

        # nas(wii).nintendowifi.net has a URL query-like format but does not use encoding for special characters
        return "&".join("{!s}={!s}".format(k, v) for k, v in dict.items())

    def filter_list_random_files(self, data, count):
        # Get [count] random files from the filelist
        samples = random.sample(data.splitlines(), count)
        return '\r\n'.join(samples) + '\r\n'

    def filter_list(self, data, attr1 = None, attr2 = None, attr3 = None):
        if attr1 == None and attr2 == None and attr3 == None:
            # Nothing to filter, just return the input data
            return data

        # Filter the list based on the attribute fields
        output = []

        for line in data.splitlines():
            s = line.split('\t')

            if len(s) == 6:
                data = {}
                data['filename'] = s[0]
                data['desc'] = s[1]
                data['attr1'] = s[2]
                data['attr2'] = s[3]
                data['attr3'] = s[4]
                data['filesize'] = s[5]

                matched = True
                if attr1 != None:
                    if data['attr1'] != attr1:
                        matched = False
                if attr2 != None:
                    if data['attr2'] != attr2:
                        matched = False
                if attr3 != None:
                    if data['attr3'] != attr3:
                        matched = False

                if matched == True:
                    output.append(line)

        # if nothing matches, at least return a newline; Pokemon BW at least expects this and will error without it
        return '\r\n'.join(output) + '\r\n'

    def get_file_count(self, data):
        return sum(1 for line in data.splitlines() if line)

if __name__ == "__main__":
    nas = NasServer()
    nas.start()
