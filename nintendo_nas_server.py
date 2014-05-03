import base64
import json
import logging
import time
import urlparse
import BaseHTTPServer
import os

import gamespy.gs_database as gs_database
import gamespy.gs_utility as gs_utils
import other.utils as utils

logger_output_to_console = True
logger_output_to_file = True
logger_name = "NintendoNasServer"
logger_filename = "nintendo_nas_server.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

#address = ("0.0.0.0", 80)
address = ("127.0.0.1", 9000)

class NintendoNasServer(object):
    def start(self):
        httpd = NintendoNasHTTPServer((address[0], address[1]), NintendoNasHTTPServerHandler)
        logger.log(logging.INFO, "Now listening for connections on %s:%d...", address[0], address[1])
        httpd.serve_forever()

class NintendoNasHTTPServer(BaseHTTPServer.HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        self.db = gs_database.GamespyDatabase()
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)

class NintendoNasHTTPServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/ac":
            length = int(self.headers['content-length'])
            post = self.str_to_dict(self.rfile.read(length))

            logger.log(logging.DEBUG, "Request to %s from %s", self.path, self.client_address)
            logger.log(logging.DEBUG, post)
            ret = {}
            ret["datetime"] = time.strftime("%Y%m%d%H%M%S")
            ret["retry"] = "0"
            action = post["action"]
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.send_header("Server", "Nintendo Wii (http)")
            self.send_header("NODE", "wifiappe3")
            self.end_headers()

            if action == "acctcreate":
                # TODO: test for duplicate accounts
                ret["returncd"] = "002"

                logger.log(logging.DEBUG, "acctcreate response to %s", self.client_address)
                logger.log(logging.DEBUG, ret)

                self.wfile.write(self.dict_to_str(ret))

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

                self.wfile.write(self.dict_to_str(ret))

        elif self.path == "/pr":
            length = int(self.headers['content-length'])
            post = self.str_to_dict(self.rfile.read(length))

            logger.log(logging.DEBUG, "Request to %s from %s", self.path, self.client_address)
            logger.log(logging.DEBUG, post)

            # TODO?: implement bad word detection

            self.wfile.write("0")

        elif self.path == "/download":
            length = int(self.headers['content-length'])
            post = self.str_to_dict(self.rfile.read(length))

            logger.log(logging.DEBUG, "Request to %s from %s", self.path, self.client_address)
            logger.log(logging.DEBUG, post)

            action = post["action"]

            # TODO: Cache all DLC information in a database instead of querying the folder.
            ret = ""
            dlcpath = "dlc/" + post["rhgamecd"]
            dlc_contenttype = False

            if action == "count":
                count = 0

                if os.path.exists(dlcpath):
                    count = len(os.listdir(dlcpath))

                ret = "%d" % count

            if action == "list":
                num = int(post["num"])
                offset = int(post["offset"])

                if os.path.exists(dlcpath):
                    filelist = os.listdir(dlcpath)

                    if offset + num <= len(filelist):
                        for file in filelist[offset:offset+num]:
                            filesize = os.path.getsize(dlcpath + "/" + file)
                            ret += "%s\t\t\t\t%d\r\n" % (file, filesize)

            if action == "contents":
                # Get only the base filename just in case there is a path involved somewhere in the filename string.
                dlc_contenttype = True
                contents = os.path.basename(post["contents"])

                if os.path.isfile(dlcpath + "/" + contents):
                    ret = open(dlcpath + "/" + contents, "rb").read()

            self.send_response(200)

            if dlc_contenttype == True:
                self.send_header("Content-type", "application/x-dsdl")
                self.send_header("Content-Disposition", "attachment; filename=\"" + post["contents"] + "\"")
            else:
                self.send_header("Content-type", "text/plain")

            self.send_header("X-DLS-Host", "http://127.0.0.1/")
            self.end_headers()

            logger.log(logging.DEBUG, "download response to %s", self.client_address)
            
            if dlc_contenttype == False:
                logger.log(logging.DEBUG, ret)

            self.wfile.write(ret)

    def str_to_dict(self, str):
        ret = urlparse.parse_qs(str)

        for k, v in ret.iteritems():
            ret[k] = base64.b64decode(v[0].replace("*", "="))

        return ret

    def dict_to_str(self, dict):
        for k, v in dict.iteritems():
            dict[k] = base64.b64encode(v).replace("=", "*")

        # nas(wii).nintendowifi.net has a URL query-like format but does not use encoding for special characters
        return "&".join("{!s}={!s}".format(k, v) for k, v in dict.items())

if __name__ == "__main__":
    nas = NintendoNasServer()
    nas.start()
