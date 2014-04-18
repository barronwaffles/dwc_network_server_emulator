from gamespy_player_search_server import GameSpyPlayerSearchServer
from gamespy_profile_server import GameSpyProfileServer
from gamespy_backend_server import GameSpyBackendServer
from gamespy_natneg_server import GameSpyNatNegServer
from gamespy_qr_server import GameSpyQRServer
from gamespy_server_browser_server import GameSpyServerBrowserServer
from gamespy_gamestats_server import GameSpyGamestatsServer
from nintendo_nas_server import NintendoNasServer

import gamespy.gs_database as gs_database

import threading

def start_backend_server():
    backend_server = GameSpyBackendServer()
    backend_server.start()

def start_qr_server():
    qr_server = GameSpyQRServer()
    qr_server.start()

def start_profile_server():
    profile_server = GameSpyProfileServer()
    profile_server.start()

def start_player_search_server():
    player_search_server = GameSpyPlayerSearchServer()
    player_search_server.start()

def start_gamestats_server():
    gamestats_server = GameSpyGamestatsServer()
    gamestats_server.start()

def start_server_browser_server():
    server_browser_server = GameSpyServerBrowserServer()
    server_browser_server.start()

def start_natneg_server():
    natneg_server = GameSpyNatNegServer()
    natneg_server.start()

def start_nas_server():
    nas_server = NintendoNasServer()
    nas_server.start()

if __name__ == "__main__":
    # Let database initialize before starting any servers.
    # This fixes any conflicts where two servers find an uninitialized database at the same time and both try to
    # initialize it.
    database = gs_database.GamespyDatabase()

    backend_server_thread = threading.Thread(target=start_backend_server)
    backend_server_thread.start()

    qr_server_thread = threading.Thread(target=start_qr_server)
    qr_server_thread.start()

    profile_server_thread = threading.Thread(target=start_profile_server)
    profile_server_thread.start()

    player_search_server_thread = threading.Thread(target=start_player_search_server)
    player_search_server_thread.start()

    player_gamestats_thread = threading.Thread(target=start_gamestats_server)
    player_gamestats_thread.start()

    #server_browser_server_thread = threading.Thread(target=start_server_browser_server)
    #server_browser_server_thread.start()

    natneg_server_thread = threading.Thread(target=start_natneg_server)
    natneg_server_thread.start()

    nas_server_thread = threading.Thread(target=start_nas_server)
    nas_server_thread.start()
