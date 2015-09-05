"""DWC Network Server Emulator

    Copyright (C) 2014 polaris-
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
import traceback

from twisted.internet.protocol import Factory
from twisted.internet.endpoints import serverFromString
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning

import gamespy.gs_database as gs_database
import gamespy.gs_query as gs_query
import other.utils as utils
import dwc_config

logger = dwc_config.get_logger('GameSpyPlayerSearchServer')
address = dwc_config.get_ip_port('GameSpyPlayerSearchServer')


class GameSpyPlayerSearchServer(object):
    def __init__(self):
        pass

    def start(self):
        endpoint_search = serverFromString(
            reactor,
            "tcp:%d:interface=%s" % (address[1], address[0])
        )
        conn_search = endpoint_search.listen(PlayerSearchFactory())

        try:
            if not reactor.running:
                reactor.run(installSignalHandlers=0)
        except ReactorAlreadyRunning:
            pass


class PlayerSearchFactory(Factory):
    def __init__(self):
        logger.log(logging.INFO,
                   "Now listening for player search connections on %s:%d...",
                   address[0], address[1])

    def buildProtocol(self, address):
        return PlayerSearch(address)


class PlayerSearch(LineReceiver):
    def __init__(self, address):
        self.setRawMode()
        self.db = gs_database.GamespyDatabase()

        self.address = address
        self.leftover = ""

    def connectionMade(self):
        pass

    def connectionLost(self, reason):
        pass

    def rawDataReceived(self, data):
        try:
            logger.log(logging.DEBUG, "SEARCH RESPONSE: %s", data)

            data = self.leftover + data
            commands, self.leftover = gs_query.parse_gamespy_message(data)

            for data_parsed in commands:
                print data_parsed

                if data_parsed['__cmd__'] == "otherslist":
                    self.perform_otherslist(data_parsed)
                else:
                    logger.log(logging.DEBUG,
                               "Found unknown search command, don't know"
                               " how to handle '%s'.",
                               data_parsed['__cmd__'])
        except:
            logger.log(logging.ERROR,
                       "Unknown exception: %s",
                       traceback.format_exc())

    def perform_otherslist(self, data_parsed):
        """Reference: http://wiki.tockdom.com/wiki/MKWii_Network_Protocol/Server/gpsp.gs.nintendowifi.net

        Example from: filtered-mkw-log-2014-01-01-ct1310.eth
        \otherslist\\o\146376154\uniquenick\2m0isbjmvRMCJ2i5321j
        \o\192817284\uniquenick\1jhggtmghRMCJ2jrsh23
        \o\302594991\uniquenick\7dkjp51v5RMCJ2nr3vs9
        \o\368031897\uniquenick\1v7p3qmkpRMCJ1o8f56p
        \o\447214276\uniquenick\7dkt0p6gtRMCJ2ljh72h
        \o\449615791\uniquenick\4puvrm1g4RMCJ00ho3v1
        \o\460250854\uniquenick\4rik5l1u1RMCJ0tc3fii
        \o\456284963\uniquenick\1unitvi86RMCJ1b10u02
        \o\453830866\uniquenick\7de3q52dbRMCJ2877ss2
        \o\450197498\uniquenick\3qtutr1ikRMCJ38gem1n
        \o\444241868\uniquenick\67tp53bs9RMCJ1abs7ej
        \o\420030955\uniquenick\5blesqia3RMCJ322bbd6
        \o\394609454\uniquenick\0hddp7mq2RMCJ30uv7r7
        \o\369478991\uniquenick\59de9c2bhRMCJ0re0fii
        \o\362755626\uniquenick\5tte2lif7RMCJ0cscgtg
        \o\350951571\uniquenick\7aeummjlaRMCJ3li4ls2
        \o\350740680\uniquenick\484uiqhr4RMCJ18opoj0
        \o\349855648\uniquenick\5blesqia3RMCJ1c245dn
        \o\324078642\uniquenick\62go5gpt0RMCJ0v0uhc9
        \o\304111337\uniquenick\4lcg6ampvRMCJ1gjre51
        \o\301273266\uniquenick\1dhdpjhn8RMCJ2da6f9h
        \o\193178453\uniquenick\3pcgu0299RMCJ3nhu50f
        \o\187210028\uniquenick\3tau15a9lRMCJ2ar247h
        \o\461622261\uniquenick\59epddrnkRMCJ1t2ge7l
        \oldone\\final\
        """
        msg_d = [
            ('__cmd__', "otherslist"),
            ('__cmd_val__', ""),
        ]

        if "numopids" in data_parsed and "opids" in data_parsed:
            numopids = int(data_parsed['numopids'])
            opids = data_parsed['opids'].split('|')
            if len(opids) != numopids and int(opids[0]):
                logger.log(logging.ERROR,
                           "Unexpected number of opids, got %d, expected %d.",
                           len(opids), numopids)

            # Return all uniquenicks despite any unexpected/missing opids
            # We can do better than that, I think...
            for opid in opids:
                profile = self.db.get_profile_from_profileid(opid)

                msg_d.append(('o', opid))
                if profile is not None:
                    msg_d.append(('uniquenick', profile['uniquenick']))
                else:
                    msg_d.append(('uniquenick', ''))

        msg_d.append(('oldone', ""))
        msg = gs_query.create_gamespy_message(msg_d)

        logger.log(logging.DEBUG, "SENDING: %s", msg)
        self.transport.write(bytes(msg))


if __name__ == "__main__":
    gsps = GameSpyPlayerSearchServer()
    gsps.start()
