from gamespy_player_search_server import GameSpyPlayerSearchServer
from gamespy_profile_server import GameSpyProfileServer
from gamespy_backend_server import GameSpyBackendServer
from gamespy_natneg_server import GameSpyNatNegServer
from gamespy_qr_server import GameSpyQRServer
from gamespy_server_browser_server import GameSpyServerBrowserServer
from gamespy_gamestats_server import GameSpyGamestatsServer
from nintendo_nas_server import NintendoNasServer
from internal_stats_server import InternalStatsServer

import gamespy.gs_database as gs_database

import threading


if __name__ == "__main__":
    # Let database initialize before starting any servers.
    # This fixes any conflicts where two servers find an uninitialized database at the same time and both try to
    # initialize it.
    database = gs_database.GamespyDatabase()

    server_list = [
        GameSpyBackendServer,
        GameSpyQRServer,
        GameSpyProfileServer,
        GameSpyPlayerSearchServer,
        GameSpyGamestatsServer,
        #GameSpyServerBrowserServer,
        GameSpyNatNegServer,
        NintendoNasServer,
        #InternalStatsServer,
    ]

    def start_server(server):
        return lambda: server().start()

    def server_thread(server):
        return threading.Thread(target=start_server(server))

    for server in server_list:
        server_thread(server).start()
