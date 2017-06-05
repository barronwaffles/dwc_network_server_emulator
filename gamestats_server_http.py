"""DWC Network Server Emulator

    Copyright (C) 2014 polaris-
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

 TODO: Seperate gamestats.gs.nintendowifi.net
       and gamestats2.gs.nintendowifi.net
 TODO: Move gamestats list to database?
"""

import logging
import urlparse
import BaseHTTPServer
import traceback
import os
import hashlib
import base64

import gamespy.gs_database as gs_database
import gamespy.gs_utility as gs_utils
import other.utils as utils
import dwc_config

logger = dwc_config.get_logger('GameStatsServerHttp')
address = dwc_config.get_ip_port('GameStatsServerHttp')


class GameStatsBase(object):
    def do_GET(self, conn, key, append_hash, append_text=""):
        try:
            conn.send_response(200)
            conn.send_header("Content-type", "text/html")
            conn.send_header("Server", "Microsoft-IIS/6.0")
            conn.send_header("Server", "GSTPRDSTATSWEB2")
            conn.send_header("X-Powered-By", "ASP.NET")
            conn.end_headers()

            params = conn.str_to_dict(conn.path)
            ret = ""
            if "hash" not in params:
                # The token is used in combination with the game's secret key.
                # The format of the hash parameter sent from the client is
                # sha1(secret_key + token).
                token = utils.generate_random_str(32)
                ret = token
            else:
                # Handle data (generic response for now)
                ret += append_text

                if append_hash:
                    h = hashlib.sha1()
                    h.update(key + base64.urlsafe_b64encode(ret) + key)
                    ret += h.hexdigest()

            conn.wfile.write(ret)
        except:
            logger.log(logging.ERROR,
                       "Unknown exception: %s",
                       traceback.format_exc())

    def do_POST(self, conn, key):
        try:
            conn.send_response(200)
            conn.send_header("Content-type", "text/html")
            conn.send_header("Server", "Microsoft-IIS/6.0")
            conn.send_header("Server", "GSTPRDSTATSWEB2")
            conn.send_header("X-Powered-By", "ASP.NET")
            conn.end_headers()
            conn.wfile.write("")

        except:
            logger.log(logging.ERROR,
                       "Unknown exception: %s",
                       traceback.format_exc())


class GameStatsVersion1(GameStatsBase):
    def do_GET(self, conn, key):
        super(self.__class__, self).do_GET(conn, key, False, "")


class GameStatsVersion2(GameStatsBase):
    def do_GET(self, conn, key):
        super(self.__class__, self).do_GET(conn, key, True, "")


class GameStatsVersion3(GameStatsBase):
    def do_GET(self, conn, key):
        super(self.__class__, self).do_GET(conn, key, True, "done")


class GameStatsServer(object):
    def start(self):
        httpd = GameStatsHTTPServer((address[0], address[1]),
                                    GameStatsHTTPServerHandler)
        logger.log(logging.INFO,
                   "Now listening for connections on %s:%d...",
                   address[0], address[1])
        httpd.serve_forever()


class GameStatsHTTPServer(BaseHTTPServer.HTTPServer):
    gamestats_list = [
        GameStatsBase,
        GameStatsVersion1,
        GameStatsVersion2,
        GameStatsVersion3
    ]

    def __init__(self, server_address, RequestHandlerClass):
        # self.db = gs_database.GamespyDatabase()
        self.gamelist = self.parse_key_file()

        BaseHTTPServer.HTTPServer.__init__(self, server_address,
                                           RequestHandlerClass)

    def parse_key_file(self, filename="gamestats.cfg"):
        gamelist = {}

        with open(filename) as config_file:
            for line in config_file.readlines():
                line, sep, comment = line.partition("#")

                # Skip whitespaces (i.e. ' ', '\t', '\n')
                s = line.split(None)

                if len(s) != 3:
                    continue

                gamestats = self.gamestats_list[0]
                if int(s[1]) < len(self.gamestats_list):
                    gamestats = self.gamestats_list[int(s[1])]

                gamelist[s[0]] = {'key': s[2], 'class': gamestats}

        return gamelist


class GameStatsHTTPServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def version_string(self):
        return "Nintendo Wii (http)"

    def do_GET(self):
        gameid = self.path.lstrip("/")
        if '/' in gameid:
            gameid = gameid[:gameid.index('/')]

        # logger.log(logging.DEBUG, "Request for '%s': %s", gameid, self.path)
        if gameid in self.server.gamelist:
            game = self.server.gamelist[gameid]['class']()
            game.do_GET(self, self.server.gamelist[gameid]['key'])
        else:
            logger.log(logging.DEBUG,
                       "WARNING: Could not find '%s' in gamestats list",
                       gameid)
            default = GameStatsBase()
            default.do_GET(self, "", False, "")

    def do_POST(self):
        pass

    def str_to_dict(self, str):
        ret = urlparse.parse_qs(urlparse.urlparse(str).query)

        for k, v in ret.iteritems():
            ret[k] = v[0]

        return ret


if __name__ == "__main__":
    gamestats = GameStatsServer()
    gamestats.start()
