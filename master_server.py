#    DWC Network Server Emulator
#    Copyright (C) 2014 polaris-
#    Copyright (C) 2014 ToadKing
#    Copyright (C) 2014 AdmiralCurtiss
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

from gamespy_player_search_server import GameSpyPlayerSearchServer
from gamespy_profile_server import GameSpyProfileServer
from gamespy_backend_server import GameSpyBackendServer
from gamespy_natneg_server import GameSpyNatNegServer
from gamespy_qr_server import GameSpyQRServer
from gamespy_server_browser_server import GameSpyServerBrowserServer
from gamespy_gamestats_server import GameSpyGamestatsServer
from nas_server import NasServer
from internal_stats_server import InternalStatsServer
from admin_page_server import AdminPageServer
from storage_server import StorageServer
from gamestats_server_http import GameStatsServer

import gamespy.gs_database as gs_database

import threading


if __name__ == "__main__":
    # Let database initialize before starting any servers.
    # This fixes any conflicts where two servers find an uninitialized database at the same time and both try to
    # initialize it.
    db = gs_database.GamespyDatabase()
    db.initialize_database()
    db.close()
    
    servers = [
        GameSpyBackendServer,
        GameSpyQRServer,
        GameSpyProfileServer,
        GameSpyPlayerSearchServer,
        GameSpyGamestatsServer,
        #GameSpyServerBrowserServer,
        GameSpyNatNegServer,
        NasServer,
        InternalStatsServer,
        AdminPageServer,
        StorageServer,
        GameStatsServer,
    ]
    for server in servers:
        threading.Thread(target=server().start).start()
