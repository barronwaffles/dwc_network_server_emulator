"""DWC Network Server Emulator

    Copyright (C) 2014 polaris-
    Copyright (C) 2014 ToadKing
    Copyright (C) 2014 AdmiralCurtiss
    Copyright (C) 2014 msoucy
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

import logging
import time
import urlparse
import BaseHTTPServer
import SocketServer
import os
import traceback

from gamespy import gs_database
from other import dlc, utils
import dwc_config

logger = dwc_config.get_logger('NasServer')


class NasHTTPServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def version_string(self):
        return "Nintendo Wii (http)"

    def do_GET(self):
        """Handle GET request."""
        try:
            # conntest server
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("X-Organization", "Nintendo")
            self.send_header("Server", "BigIP")
            self.end_headers()
            self.wfile.write("ok")
        except:
            logger.log(logging.ERROR, "Exception occurred on GET request!")
            logger.log(logging.ERROR, "%s", traceback.format_exc())

    def do_POST(self):
        self.server = lambda: None
        self.server.db = gs_database.GamespyDatabase()

        try:
            length = int(self.headers['content-length'])
            post = utils.qs_to_dict(self.rfile.read(length))
            if self.client_address[0] == '127.0.0.1':
                client_address = (
                    self.headers.get('x-forwarded-for',
                                     self.client_address[0]),
                    self.client_address[1]
                )
            else:
                client_address = self.client_address

            post['ipaddr'] = client_address[0]

            if self.path == "/ac":
                logger.log(logging.DEBUG, "Request to %s from %s",
                           self.path, client_address)
                logger.log(logging.DEBUG, "%s", post)
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
                        logger.log(logging.DEBUG,
                                   "acctcreate denied for banned user %s",
                                   str(post))
                        ret = {
                            "datetime": time.strftime("%Y%m%d%H%M%S"),
                            "returncd": "3913",
                            "locator": "gamespy.com",
                            "retry": "1",
                            "reason": "User banned."
                        }
                    else:
                        ret["returncd"] = "002"
                        ret['userid'] = \
                            self.server.db.get_next_available_userid()

                        logger.log(logging.DEBUG,
                                   "acctcreate response to %s",
                                   client_address)
                        logger.log(logging.DEBUG, "%s", ret)

                    ret = utils.dict_to_qs(ret)

                elif action == "login":
                    if self.server.db.is_banned(post):
                        logger.log(logging.DEBUG,
                                   "login denied for banned user %s",
                                   str(post))
                        ret = {
                            "datetime": time.strftime("%Y%m%d%H%M%S"),
                            "returncd": "3914",
                            "locator": "gamespy.com",
                            "retry": "1",
                            "reason": "User banned."
                        }
                    # Un-comment these lines to enable console registration
                    # feature
                    # elif not self.server.db.pending(post):
                    #     logger.log(logging.DEBUG,
                    #                "Login denied - Unknown console %s",
                    #                post)
                    #     ret = {
                    #         "datetime": time.strftime("%Y%m%d%H%M%S"),
                    #         "returncd": "3921",
                    #         "locator": "gamespy.com",
                    #         "retry": "1",
                    #     }
                    # elif not self.server.db.registered(post):
                    #     logger.log(logging.DEBUG,
                    #                "Login denied - console pending %s",
                    #                post)
                    #     ret = {
                    #         "datetime": time.strftime("%Y%m%d%H%M%S"),
                    #         "returncd": "3888",
                    #         "locator": "gamespy.com",
                    #         "retry": "1",
                    #     }
                    else:
                        challenge = utils.generate_random_str(8)
                        post["challenge"] = challenge

                        authtoken = self.server.db.generate_authtoken(
                            post["userid"],
                            post
                        )
                        ret.update({
                            "returncd": "001",
                            "locator": "gamespy.com",
                            "challenge": challenge,
                            "token": authtoken,
                        })

                        logger.log(logging.DEBUG, "login response to %s",
                                   client_address)
                        logger.log(logging.DEBUG, "%s", ret)

                    ret = utils.dict_to_qs(ret)

                elif action == "SVCLOC" or action == "svcloc":
                    # Get service based on service id number
                    ret["returncd"] = "007"
                    ret["statusdata"] = "Y"
                    authtoken = self.server.db.generate_authtoken(
                        post["userid"],
                        post
                    )

                    if 'svc' in post:
                        if post["svc"] in ("9000", "9001"):
                            # DLC host = 9000
                            # In case the client's DNS isn't redirecting to
                            # dls1.nintendowifi.net
                            ret["svchost"] = self.headers['host']

                            # Brawl has 2 host headers which Apache chokes
                            # on, so only return the first one or else it
                            # won't work
                            ret["svchost"] = ret["svchost"].split(',')[0]

                            if post["svc"] == 9000:
                                ret["token"] = authtoken
                            else:
                                ret["servicetoken"] = authtoken
                        elif post["svc"] == "0000":
                            # Pokemon requests this for some things
                            ret["servicetoken"] = authtoken
                            ret["svchost"] = "n/a"
                        else:
                            # Empty svc - Fix Error Code 24101 (Boom Street)
                            ret["svchost"] = "n/a"
                            ret["servicetoken"] = authtoken

                    logger.log(logging.DEBUG, "svcloc response to %s",
                               client_address)
                    logger.log(logging.DEBUG, "%s", ret)

                    ret = utils.dict_to_qs(ret)
                else:
                    logger.log(logging.WARNING,
                               "Unknown action request %s from %s!",
                               self.path, client_address)

            elif self.path == "/pr":
                logger.log(logging.DEBUG, "Request to %s from %s",
                           self.path, client_address)
                logger.log(logging.DEBUG, "%s", post)
                words = len(post["words"].split('\t'))
                wordsret = "0" * words
                ret = {
                    "prwords": wordsret,
                    "returncd": "000",
                    "datetime": time.strftime("%Y%m%d%H%M%S")
                }

                for l in "ACEJKP":
                    ret["prwords" + l] = wordsret

                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.send_header("NODE", "wifiappe1")

                logger.log(logging.DEBUG, "pr response to %s", client_address)
                logger.log(logging.DEBUG, "%s", ret)

                ret = utils.dict_to_qs(ret)

            elif self.path == "/download":
                logger.log(logging.DEBUG, "Request to %s from %s",
                           self.path, client_address)
                logger.log(logging.DEBUG, "%s", post)

                action = post["action"]

                ret = ""
                dlcdir = os.path.abspath('dlc')
                dlcpath = os.path.abspath("dlc/" + post["gamecd"])
                dlc_contenttype = False

                if os.path.commonprefix([dlcdir, dlcpath]) != dlcdir:
                    logging.log(logging.WARNING,
                                'Attempted directory traversal attack "%s",'
                                ' cancelling.', dlcpath)
                    self.send_response(403)
                    return

                if action == "count":
                    ret = dlc.download_count(dlc_path, post)

                if action == "list":
                    ret = dlc.download_list(dlc_path, post)

                if action == "contents":
                    ret = dlc.download_contents(dlc_path, post)
                    dlc_contenttype = True

                self.send_response(200)

                if dlc_contenttype is True:
                    self.send_header("Content-type", "application/x-dsdl")
                    self.send_header("Content-Disposition",
                                     "attachment; filename=\"" +
                                     post["contents"] + "\"")
                else:
                    self.send_header("Content-type", "text/plain")

                self.send_header("X-DLS-Host", "http://127.0.0.1/")

                logger.log(logging.DEBUG, "download response to %s",
                           client_address)

                # if dlc_contenttype is False:
                #     logger.log(logging.DEBUG, "%s", ret)
            else:
                self.send_response(404)
                logger.log(logging.WARNING,
                           "Unknown path request %s from %s!",
                           self.path, client_address)
                return

            self.send_header("Content-Length", str(len(ret)))
            self.end_headers()
            self.wfile.write(ret)
        except:
            logger.log(logging.ERROR, "Unknown exception: %s",
                       traceback.format_exc())


class NasHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """Threading HTTP server."""
    pass


class NasServer(object):
    def start(self):
        address = dwc_config.get_ip_port('NasServer')
        httpd = NasHTTPServer(address, NasHTTPServerHandler)
        logger.log(logging.INFO, "Now listening for connections on %s:%d...",
                   *address)
        httpd.serve_forever()


if __name__ == "__main__":
    nas = NasServer()
    nas.start()
