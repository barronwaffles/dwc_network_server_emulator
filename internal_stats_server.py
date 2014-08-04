#    DWC Network Server Emulator
#    Copyright (C) 2014 polaris-
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

from twisted.web import server, resource
from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning
from multiprocessing.managers import BaseManager
import time
import datetime
import json
import logging
import other.utils as utils

logger_output_to_console = True
logger_output_to_file = True
logger_name = "InternalStatsServer"
logger_filename = "internal_stats_server.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

class GameSpyServerDatabase(BaseManager):
    pass

GameSpyServerDatabase.register("get_server_list")

class StatsPage(resource.Resource):
    isLeaf = True

    def __init__(self, stats):
        self.stats = stats

    def render_GET(self, request):
        raw = False
        force_update = False

        if '/'.join(request.postpath) == "json":
            raw = True
            force_update = True

        server_list = self.stats.get_server_list(force_update)

        if raw == True:
            # List of keys to be removed
            restricted = [ "publicip", "__session__", "localip0", "localip1" ]

            # Filter out certain fields before displaying raw data
            if server_list != None:
                for game in server_list:
                    for server in server_list[game]:
                        for r in restricted:
                            if r in server:
                                server.pop(r, None)

            output = json.dumps(server_list)

        else:
            output = "<html>"
            output += "<table border='1'>"
            output += "<tr>"
            output += "<td>Game ID</td><td># Players</td>"
            output += "</tr>"

            if server_list != None:
                for game in server_list:
                    if not server_list[game]:
                        continue

                    output += "<tr>"
                    output += "<td>" + game + "</td>"
                    output += "<td><center>%d</center></td>" % (len(server_list[game]))
                    output += "</tr>"

            output += "</table>"

            output += "<br>"
            output += "<i>Last updated: %s</i><br>" % (self.stats.get_last_update_time())
            output += "</html>"

        return output

class InternalStatsServer(object):
    def __init__(self):
        self.last_update = 0
        self.next_update = 0
        self.server_list = None
        self.seconds_per_update = 60 # The number of seconds to wait before updating the server list

    def start(self):
        manager_address = ("127.0.0.1", 27500)
        manager_password = ""
        self.server_manager = GameSpyServerDatabase(address = manager_address, authkey= manager_password)
        self.server_manager.connect()

        site = server.Site(StatsPage(self))
        reactor.listenTCP(9001, site)

        try:
            if reactor.running == False:
                reactor.run(installSignalHandlers=0)
        except ReactorAlreadyRunning:
            pass

    def get_server_list(self, force_update = False):
        if force_update == True or self.next_update == 0 or self.next_update - time.time() <= 0:
            self.last_update = time.time()
            self.next_update = time.time() + self.seconds_per_update
            self.server_list = self.server_manager.get_server_list()._getvalue()

            logger.log(logging.DEBUG, self.server_list)

        return self.server_list

    def get_last_update_time(self):
        return str(datetime.datetime.fromtimestamp(self.last_update))

if __name__ == "__main__":
    stats = InternalStatsServer()
    stats.start()
