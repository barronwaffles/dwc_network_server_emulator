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
import BaseHTTPServer
import SocketServer
import traceback

from gamespy import gs_database
from other import utils
import dwc_config

logger = dwc_config.get_logger('NasServer')


def handle_post(handler, addr, post):
    """Handle unknown path."""
    logger.log(logging.WARNING, "Unknown path request %s from %s:%d!",
               handler.path, *addr)
    handler.send_response(404)
    return None


def handle_ac_action(handler, db, addr, post):
    """Handle unknown ac action request."""
    logger.log(logging.WARNING, "Unknown ac action: %s", handler.path)
    return {}


def handle_ac_acctcreate(handler, db, addr, post):
    """Handle ac acctcreate request.

    TODO: Test for duplicate accounts.
    """
    if db.is_banned(post):
        ret = {
            "retry": "1",
            "returncd": "3913",
            "locator": "gamespy.com",
            "reason": "User banned."
        }
        logger.log(logging.DEBUG, "Acctcreate denied for banned user %s",
                   str(post))
    else:
        ret = {
            "retry": "0",
            "returncd": "002",
            "userid": db.get_next_available_userid()
        }
        logger.log(logging.DEBUG, "Acctcreate response to %s:%d", *addr)
        logger.log(logging.DEBUG, "%s", ret)

    return ret


def handle_ac_login(handler, db, addr, post):
    """Handle ac login request."""
    if db.is_banned(post):
        ret = {
            "retry": "1",
            "returncd": "3914",
            "locator": "gamespy.com",
            "reason": "User banned."
        }
        logger.log(logging.DEBUG, "Login denied for banned user %s", str(post))
    # Un-comment these lines to enable console registration feature
    # elif not db.pending(post):
    #     logger.log(logging.DEBUG, "Login denied - Unknown console %s", post)
    #     ret = {
    #         "retry": "1",
    #         "returncd": "3921",
    #         "locator": "gamespy.com",
    #     }
    # elif not db.registered(post):
    #     logger.log(logging.DEBUG, "Login denied - console pending %s", post)
    #     ret = {
    #         "retry": "1",
    #         "returncd": "3888",
    #         "locator": "gamespy.com",
    #     }
    else:
        challenge = utils.generate_random_str(8)
        post["challenge"] = challenge

        authtoken = db.generate_authtoken(post["userid"], post)
        ret = {
            "retry": "0",
            "returncd": "001",
            "locator": "gamespy.com",
            "challenge": challenge,
            "token": authtoken,
        }

        logger.log(logging.DEBUG, "Login response to %s:%d", *addr)
        logger.log(logging.DEBUG, "%s", ret)

    return ret


def handle_ac_svcloc(handler, db, addr, post):
    """Handle ac svcloc request."""
    # Get service based on service id number
    ret = {
        "retry": "0",
        "returncd": "007",
        "statusdata": "Y"
    }
    authtoken = db.generate_authtoken(post["userid"], post)

    if 'svc' in post:
        if post["svc"] in ("9000", "9001"):
            # DLC host = 9000
            # In case the client's DNS isn't redirecting to
            # dls1.nintendowifi.net
            # NB: NAS config overrides this if set
            svchost = dwc_config.get_svchost('NasServer')
            ret["svchost"] = svchost if svchost else handler.headers['host']

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

    logger.log(logging.DEBUG, "Svcloc response to %s:%d", *addr)
    logger.log(logging.DEBUG, "%s", ret)

    return ret


def handle_ac(handler, addr, post):
    """Handle ac POST request."""
    logger.log(logging.DEBUG, "Ac request to %s from %s:%d",
               handler.path, *addr)
    logger.log(logging.DEBUG, "%s", post)

    action = str(post["action"]).lower()
    command = handler.ac_actions.get(action, handle_ac_action)
    ret = command(handler, gs_database.GamespyDatabase(), addr, post)

    ret.update({"datetime": time.strftime("%Y%m%d%H%M%S")})
    handler.send_response(200)
    handler.send_header("Content-type", "text/plain")
    handler.send_header("NODE", "wifiappe1")

    return utils.dict_to_qs(ret)


def handle_pr(handler, addr, post):
    """Handle pr POST request."""
    logger.log(logging.DEBUG, "Pr request to %s from %s:%d",
               handler.path, *addr)
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

    handler.send_response(200)
    handler.send_header("Content-type", "text/plain")
    handler.send_header("NODE", "wifiappe1")

    logger.log(logging.DEBUG, "Pr response to %s:%d", *addr)
    logger.log(logging.DEBUG, "%s", ret)

    return utils.dict_to_qs(ret)


class NasHTTPServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """Nintendo NAS server handler."""

    post_paths = {
        "/ac": handle_ac,
        "/pr": handle_pr,
    }

    ac_actions = {
        "acctcreate": handle_ac_acctcreate,
        "login": handle_ac_login,
        "svcloc": handle_ac_svcloc,
    }

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
        try:
            length = int(self.headers['content-length'])
            post = utils.qs_to_dict(self.rfile.read(length))
            client_address = (
                self.headers.get('x-forwarded-for', self.client_address[0]),
                self.client_address[1]
            )
            post['ipaddr'] = client_address[0]

            command = self.post_paths.get(self.path, handle_post)
            ret = command(self, client_address, post)

            if ret is not None:
                self.send_header("Content-Length", str(len(ret)))
                self.end_headers()
                self.wfile.write(ret)
        except:
            logger.log(logging.ERROR, "Exception occurred on POST request!")
            logger.log(logging.ERROR, "%s", traceback.format_exc())


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
