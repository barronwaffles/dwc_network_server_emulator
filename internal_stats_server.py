from twisted.web import server, resource
from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning
from multiprocessing.managers import BaseManager
import time
import datetime
from contextlib import contextmanager


class GameSpyServerDatabase(BaseManager):
    pass

GameSpyServerDatabase.register("get_server_list")

class StatsPage(resource.Resource):
    isLeaf = True

    def __init__(self, stats):
        self.stats = stats

    def render_GET(self, request):

        output = ""
        def put(s):
            output += str(s)

        @contextmanager
        def tag(name, **kwargs):
            put("<" + name)
            for arg in kwargs:
                put(" %s='%s'" % (arg, kwargs[arg]))
            put(">")
            yield
            put("</%s>" % name)

        server_list = stats.get_server_list()

        with tag("html"):
            with tag("table", border="1"):
                with tag("tr"):
                    with tag("td"): put("Game ID")
                    with tag("td"): put("# Players")
                if server_list != None:
                    for game in server_list:
                        if len(server_list[game]) == 0:
                            continue
                        with tag("tr"):
                            with tag("td"): put(game)
                            with tag("td") with tag("center"): put(len(server_list[game]))

            put("<br>")
            with tag("i"): put("Last updated: %s" % (stats.get_last_update_time())
            put("<br>")

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

    def get_server_list(self):
        if self.next_update == 0 or self.next_update - time.time() <= 0:
            self.last_update = time.time()
            self.next_update = time.time() + self.seconds_per_update
            self.server_list = self.server_manager.get_server_list()._getvalue()

            print self.server_list

        return self.server_list

    def get_last_update_time(self):
        return str(datetime.datetime.fromtimestamp(self.last_update))

if __name__ == "__main__":
    stats = InternalStatsServer()
    stats.start()
