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
logger_name = "NintendoNasServer"
logger_filename = "nintendo_nas_server.log"
logger = utils.create_logger(
    logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

# if a game from this list requests a file listing, the server will return that only one exists and return a random one
# this is used for Mystery Gift distribution on Generation 4 Pokemon games
gamecodes_return_random_file = [
    'ADAD', 'ADAE', 'ADAF', 'ADAI', 'ADAJ', 'ADAK', 'ADAS',
    'CPUD', 'CPUE', 'CPUF', 'CPUI', 'CPUJ', 'CPUK', 'CPUS',
    'IPGD', 'IPGE', 'IPGF', 'IPGI', 'IPGJ', 'IPGK', 'IPGS',
]

#address = ("0.0.0.0", 80)
address = ("127.0.0.1", 9000)


class NintendoNasServer(object):

    def start(self):
        httpd = NintendoNasHTTPServer(
            (address[0], address[1]), NintendoNasHTTPServerHandler)
        logger.info("Now listening for connections on %s:%d...", address[0], address[1])
        httpd.serve_forever()


class NintendoNasHTTPServer(BaseHTTPServer.HTTPServer):

    def __init__(self, server_address, RequestHandlerClass):
        self.db = gs_database.GamespyDatabase()
        BaseHTTPServer.HTTPServer.__init__(
            self, server_address, RequestHandlerClass)


class NintendoNasHTTPServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    def do_POST(self):
        length = int(self.headers['content-length'])
        post = self.str_to_dict(self.rfile.read(length))

        if self.path == "/ac":
            logger.debug("Request to %s from %s", self.path, self.client_address)
            logger.debug(post)
            ret = {
                "datetime": time.strftime("%Y%m%d%H%M%S"),
                    "retry": "0",
            }
            action = post["action"]
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.send_header("Server", "Nintendo Wii (http)")
            self.send_header("NODE", "wifiappe3")
            self.end_headers()

            if action == "acctcreate":
                # TODO: test for duplicate accounts
                ret["returncd"] = "002"

                logger.debug("acctcreate response to %s", self.client_address)
                logger.debug(ret)

                self.wfile.write(self.dict_to_str(ret))

            elif action == "login":
                challenge = utils.generate_random_str(8)
                authtoken = self.server.db.generate_authtoken(
                    post["userid"], post)
                ret.update({
                    "returncd": "001",
                    "locator": "gamespy.com",
                    "challenge": challenge,
                    "token": authtoken,
                })

                post.update({
                    "challenge": challenge,
                })

                logger.debug("login response to %s", self.client_address)
                logger.debug(ret)

                self.wfile.write(self.dict_to_str(ret))

            # Get service based on service id number
            elif action == "SVCLOC" or action == "svcloc":
                ret.update({
                    "returncd": "007",
                    "statusdata": "Y",
                })
                authtoken = self.server.db.generate_authtoken(
                    post["userid"], post)

                if 'svc' in post:
                    # DLC host = 9000
                    if post["svc"] in ("9000", "9001"):
                        # in case the client's DNS isn't redirecting
                        # dls1.nintendowifi.net

                        # Brawl has 2 host headers which Apache chokes on, so
                        # only return the first one or else it won't work
                        ret["svchost"] = self.headers["host"].split(",")[0]
                        ret["token" if post["svc"] == 9000 else "servicetoken"] = authtoken
                    # Pokemon requests this for some things
                    elif post["svc"] == "0000":
                        ret.update({
                            "svchost": "n/a",
                            "servicetoken": authtoken
                        })

                logger.debug("svcloc response to %s", self.client_address)
                logger.debug(ret)

                self.wfile.write(self.dict_to_str(ret))

        elif self.path == "/pr":
            logger.debug("Request to %s from %s", self.path, self.client_address)
            logger.debug(post)
            ret = {
                "returncd": "000",
                "datetime": time.strftime("%Y%m%d%H%M%S"),
            }

            words = "0" * len(post["words"].split('\t'))
            for name in ("prwords", "prwordsA", "prwordsC", "prwordsE", "prwordsJ", "prwordsK", "prwordsP"):
                ret[name] = words

            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.send_header("Server", "Nintendo Wii (http)")
            self.send_header("NODE", "wifiappe3")
            self.end_headers()

            logger.debug("pr response to %s", self.client_address)
            logger.debug(ret)

            self.wfile.write(self.dict_to_str(ret))

        elif self.path == "/download":
            logger.debug("Request to %s from %s", self.path, self.client_address)
            logger.debug(post)

            action = post["action"]

            ret = ""
            dlcpath = "dlc/" + post["gamecd"]
            dlc_contenttype = False

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
                            list = open(dlcpath + "/_list.txt", "rb").read()
                            list = self.filter_list(list, attr1, attr2, attr3)

                            count = self.get_file_count(list)

                    ret = "%d" % count

            if action == "list":
                num = int(post["num"])
                offset = int(post["offset"])

                attr1 = post.get("attr1", None)
                attr2 = post.get("attr2", None)
                attr3 = post.get("attr3", None)

                if os.path.exists(dlcpath):
                    # Look for a list file first.
                    # If the list file exists, send the entire thing back to
                    # the client.
                    if os.path.isfile(dlcpath + "/_list.txt"):
                        ret = open(dlcpath + "/_list.txt", "rb").read()
                        ret = self.filter_list(ret, attr1, attr2, attr3)

                        if post["gamecd"] in gamecodes_return_random_file:
                            ret = self.filter_list_random_files(ret, 1)

            if action == "contents":
                # Get only the base filename just in case there is a path
                # involved somewhere in the filename string.
                dlc_contenttype = True
                contents = os.path.basename(post["contents"])

                if os.path.isfile(dlcpath + "/" + contents):
                    ret = open(dlcpath + "/" + contents, "rb").read()

            self.send_response(200)

            if dlc_contenttype == True:
                self.send_header("Content-Length", str(len(ret)))
                self.send_header("Content-type", "application/x-dsdl")
                self.send_header(
                    "Content-Disposition", "attachment; filename=\"" + post["contents"] + "\"")
            else:
                self.send_header("Content-type", "text/plain")

            self.send_header("X-DLS-Host", "http://127.0.0.1/")
            self.end_headers()

            logger.debug("download response to %s", self.client_address)

            # if dlc_contenttype == False:
            #    logger.debug(ret)

            self.wfile.write(ret)

    def str_to_dict(self, str):
        ret = urlparse.parse_qs(str)

        for k, v in ret.iteritems():
            try:
                ret[k] = base64.b64decode(v[0].replace("*", "="))
            except TypeError:
                logger.error("Could not decode following string: ret[%s] = %s" % (k, v[0]))
                logger.error("url: %s" % str)

        return ret

    def dict_to_str(self, dict):
        for k, v in dict.iteritems():
            dict[k] = base64.b64encode(v).replace("=", "*")

        # nas(wii).nintendowifi.net has a URL query-like format but does not
        # use encoding for special characters
        return "&".join("{!s}={!s}".format(k, v) for k, v in dict.items())

    def filter_list_random_files(self, data, count):
        # Get [count] random files from the filelist
        lines = data.splitlines()
        samples = random.sample(lines, count)
        return '\r\n'.join(samples) + '\r\n'

    def filter_list(self, data, attr1=None, attr2=None, attr3=None):
        if attr1 == None and attr2 == None and attr3 == None:
            # Nothing to filter, just return the input data
            return data

        # Filter the list based on the attribute fields
        output = ""

        for line in data.splitlines():
            s = line.split('\t')

            if len(s) == 6:
                data = {d: s[i]
                        for i, d in enumerate('filename', 'desc', 'attr1', 'attr2', 'attr3', 'filesize')}
                if (data['attr1'] == attr1) and (data['attr2'] == attr2) and (data['attr3'] == attr3):
                    output += line + '\r\n'

        # if nothing matches, at least return a newline; Pokemon BW at least
        # expects this and will error without it
        return output or '\r\n'

    def get_file_count(self, data):
        return sum(1 for line in data.splitlines() if line)

if __name__ == "__main__":
    nas = NintendoNasServer()
    nas.start()
