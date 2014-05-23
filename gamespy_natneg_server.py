# Server emulator for *.available.gs.nintendowifi.net and *.master.gs.nintendowifi.net
# Query and Reporting: http://docs.poweredbygamespy.com/wiki/Query_and_Reporting_Overview

import logging
import socket
import ctypes
import gamespy.gs_utility as gs_utils
import other.utils as utils

from multiprocessing.managers import BaseManager

# Logger settings
logger_output_to_console = True
logger_output_to_file = True
logger_name = "GameSpyNatNegServer"
logger_filename = "gamespy_natneg_server.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

class GameSpyServerDatabase(BaseManager):
    pass

GameSpyServerDatabase.register("get_server_list")
GameSpyServerDatabase.register("modify_server_list")
GameSpyServerDatabase.register("find_servers")
GameSpyServerDatabase.register("find_server_by_address")
GameSpyServerDatabase.register("find_server_by_local_address")
GameSpyServerDatabase.register("add_natneg_server")
GameSpyServerDatabase.register("get_natneg_server")
GameSpyServerDatabase.register("delete_natneg_server")

def first(gen):
    try: return next(gen)
    except StopIteration: return None

class GameSpyNatNegServer(object):
    def __init__(self):
        self.session_list = {}
        self.secret_key_list = gs_utils.generate_secret_keys("gslist.cfg")

        manager_address = ("127.0.0.1", 27500)
        manager_password = ""
        self.server_manager = GameSpyServerDatabase(address = manager_address, authkey= manager_password)
        self.server_manager.connect()

    def start(self):
        # Start natneg server
        address = ('0.0.0.0', 27901)  # accessible to outside connections (use this if you don't know what you're doing)

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(address)

        logger.info("Server is now listening on %s:%s..." % (address[0], address[1]))

        while True:
            recv_data, addr = s.recvfrom(2048)

            logger.debug("Connection from %s:%d..." % (addr[0], addr[1]))
            logger.debug(utils.pretty_print_hex(recv_data))

            # Make sure it's a legal packet
            if recv_data[0:6] != bytearray([0xfd, 0xfc, 0x1e, 0x66, 0x6a, 0xb2]):
                continue

            session_id_raw = recv_data[8:12]
            session_id = util.get_int(session_id_raw, 0)

            # Handle commands
            if recv_data[7] == '\x00':
                logger.debug("Received initialization from %s:%s..." % (addr[0], addr[1]))

                output = bytearray(recv_data[0:14])
                # Checked with Tetris DS, Mario Kart DS, and Metroid Prime Hunters, and this seems to be the standard response to 0x00
                output += bytearray([0xff, 0xff, 0x6d, 0x16, 0xb5, 0x7d, 0xea ])
                output[7] = 0x01 # Initialization response
                s.sendto(output, addr)

                # Try to connect to the server
                gameid = utils.get_string(recv_data, 0x16)
                client_id = "%02x" % ord(recv_data[13])

                localip_raw = recv_data[15:19]
                localip_int_le = utils.get_int(recv_data, 15)
                localip_int_be = utils.get_int_be(recv_data, 15)
                localip = '.'.join(["%d" % ord(x) for x in localip_raw])
                localport_raw = recv_data[19:21]
                localport = utils.get_short_be(localport_raw, 0)
                localaddr = (localip, localport, localip_int_le, localip_int_be)

                self.session_list.setdefault(gameid, {})
                self.session_list[gameid].setdefault(session_id, {})
                self.session_list[gameid][session_id].setdefault(client_id, {
                    'connected': False,
                    'addr': '',
                    'localaddr': None,
                    'serveraddr': None,
                    'gameid': None
                })

                clientsession = self.session_list[gameid][session_id][client_id]

                clientsession['gameid'] = utils.get_string(recv_data[21:], 0)
                clientsession['addr'] = addr
                clientsession['localaddr'] = localaddr
                clients = len(self.session_list[gameid][session_id])

                for client in self.session_list[gameid][session_id]:
                    csess = self.session_list[gameid][session_id][client]
                    if csess['connected'] == False: # and csess['localaddr'][1] != 0:
                        if client == client_id:
                            continue

                        #if csess['serveraddr'] == None:
                        serveraddr = self.get_server_info(gameid, session_id, client)
                        if serveraddr is None:
                            serveraddr = self.get_server_info_alt(gameid, session_id, client)

                        csess['serveraddr'] = serveraddr
                        logger.debug("Found server from local ip/port: %s from %d" % (serveraddr, session_id))

                        publicport = csess['addr'][1]
                        if csess['localaddr'][1] != 0:
                            publicport = csess['localaddr'][1]

                        if csess['serveraddr'] is not None:
                            publicport = int(csess['serveraddr']['publicport'])

                        # Send to requesting client
                        output = bytearray(recv_data[0:12])
                        output += bytearray([int(x) for x in csess['addr'][0].split('.')])
                        output += utils.get_bytes_from_short_be(publicport)

                        output += bytearray([0x42, 0x00]) # Unknown, always seems to be \x42\x00
                        output[7] = 0x05
                        #s.sendto(output, (clientsession['addr']))
                        s.sendto(output, (clientsession['addr'][0], clientsession['addr'][1]))

                        logger.debug("Sent connection request to {0[0]}:{0[1]}...".format(clientsession['addr']))
                        logger.debug(utils.pretty_print_hex(output))

                        # Send to other client
                        #if clientsession['serveraddr'] == None:
                        serveraddr = self.get_server_info(gameid, session_id, client_id)
                        if serveraddr == None:
                            serveraddr = self.get_server_info_alt(gameid, session_id, client)

                        clientsession['serveraddr'] = serveraddr
                        logger.debug("Found server 2 from local ip/port: %s from %d" % (serveraddr, session_id))

                        publicport = clientsession['addr'][1]
                        if clientsession['localaddr'][1] != 0:
                            publicport = clientsession['localaddr'][1]

                        if clientsession['serveraddr'] != None:
                            publicport = int(clientsession['serveraddr']['publicport'])

                        output = bytearray(recv_data[0:12])
                        output += bytearray([int(x) for x in clientsession['addr'][0].split('.')])
                        output += utils.get_bytes_from_short_be(publicport)

                        output += bytearray([0x42, 0x00]) # Unknown, always seems to be \x42\x00
                        output[7] = 0x05
                        #s.sendto(output, (csess['addr']))
                        s.sendto(output, (csess['addr'][0], csess['addr'][1]))

                        logger.debug("Sent connection request to {0[0]}:{0[1]}...".format(csess['addr']))
                        logger.debug(utils.pretty_print_hex(output))

            elif recv_data[7] == '\x06': # Was able to connect
                client_id = "%02x" % ord(recv_data[13])
                logger.debug("Received connected command from %s:%s..." % (addr[0], addr[1]))

                if gameid not in self.session_list:
                    continue
                elif session_id not in self.session_list[gameid]:
                    continue
                elif client_id not in self.session_list[gameid][session_id]:
                    continue

                self.session_list[gameid][session_id][client_id]['connected'] = True

            elif recv_data[7] == '\x0a': # Address check. Note: UNTESTED!
                client_id = "%02x" % ord(recv_data[13])
                logger.debug("Received address check command from %s:%s..." % (addr[0], addr[1]))

                output = bytearray(recv_data[0:15])
                output += bytearray([int(x) for x in addr[0].split('.')])
                output += utils.get_bytes_from_short_be(addr[1])
                output += bytearray(recv_data[len(output):])

                output[7] = 0x0b
                s.sendto(output, addr)

                logger.debug("Sent address check response to {0[0]}:{0[1]}...".format(self.session_list[gameid][session_id][client]['addr']))
                logger.debug(utils.pretty_print_hex(output))

            elif recv_data[7] == '\x0c': # Natify
                port_type = "%02x" % ord(recv_data[12])
                logger.debug("Received natify command from %s:%s..." % (addr[0], addr[1]))

                output = bytearray(recv_data)
                output[7] = 0x02 # ERT Test
                s.sendto(output, addr)

                logger.debug("Sent natify response to {0[0]}:{0[1]}...".format(self.session_list[gameid][session_id][client]['addr']))
                logger.debug(utils.pretty_print_hex(output))

            elif recv_data[7] == '\x0d':
                client_id = "%02x" % ord(recv_data[13])
                logger.debug("Received report command from %s:%s..." % (addr[0], addr[1]))
                logger.debug(utils.pretty_print_hex(recv_data))

                output = bytearray(recv_data)
                output[7] = 0x0e # Report response
                s.sendto(recv_data, addr)

            else: # Was able to connect
                logger.debug("Received unknown command %02x from %s:%s..." % (ord(recv_data[7]), addr[0], addr[1]))

    def get_server_info(self, gameid, session_id, client_id):
        server_info = None
        servers = self.server_manager.get_natneg_server(session_id)._getvalue()

        if servers is None:
            return None

        console = 0 # 0 == Wii, 1 == DS
        ipstr = self.session_list[gameid][session_id][client_id]['addr'][0]
        getint = lambda value: [get_int_be, get_int][console]

        ip = str(ctypes.c_int32(getint(bytearray([int(x) for x in ipstr.split('.')]), 0)).value)
        console = not console

        server_info = first(server for server in servers if server['publicip'] == ip)

        if server_info is None:
            ip = str(ctypes.c_int32(getint(bytearray([int(x) for x in ipstr.split('.')]), 0)).value)
            server_info = first(server for server in servers if server['publicip'] == ip)

        return server_info

    def get_server_info_alt(self, gameid, session_id, client_id):
        console = 0 # 0 == Wii, 1 == DS
        clientsession = self.session_list[gameid][session_id][client_id]
        ipstr = clientsession['addr'][0]
        getint = lambda value: [get_int_be, get_int][console]

        ip = str(ctypes.c_int32(getint(bytearray([int(x) for x in ipstr.split('.')]), 0)).value)
        console = not console

        serveraddr = self.server_manager.find_server_by_local_address(ip, clientsession['localaddr'], clientsession['gameid'])._getvalue()

        if serveraddr is None:
            ip = str(ctypes_c_int32(getint(bytearray([int(x) for x in ipstr.split('.')]), 0)).value)
            console = not console

            serveraddr = self.server_manager.find_server_by_local_address(ip, clientsession['localaddr'], clientsession['gameid'])._getvalue()

        return serveraddr

if __name__ == "__main__":
    natneg_server = GameSpyNatNegServer()
    natneg_server.start()
