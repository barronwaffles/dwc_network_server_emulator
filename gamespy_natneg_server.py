# Server emulator for *.available.gs.nintendowifi.net and *.master.gs.nintendowifi.net
# Query and Reporting: http://docs.poweredbygamespy.com/wiki/Query_and_Reporting_Overview

import logging
import socket
import ctypes
import struct
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

        logger.log(logging.INFO, "Server is now listening on %s:%s..." % (address[0], address[1]))

        while 1:
            recv_data, addr = s.recvfrom(2048)

            logger.log(logging.DEBUG, "Connection from %s:%d..." % (addr[0], addr[1]))
            logger.log(logging.DEBUG, utils.pretty_print_hex(recv_data))

            # Make sure it's a legal packet
            if recv_data[0:6] != bytearray([0xfd, 0xfc, 0x1e, 0x66, 0x6a, 0xb2]):
                continue

            session_id = struct.unpack("<I", recv_data[8:12])[0]
            session_id_raw = recv_data[8:12]

            # Handle commands
            if recv_data[7] == '\x00':
                logger.log(logging.DEBUG, "Received initialization from %s:%s..." % (addr[0], addr[1]))

                output = bytearray(recv_data[0:14])
                output += bytearray([0xff, 0xff, 0x6d, 0x16, 0xb5, 0x7d, 0xea ]) # Checked with Tetris DS, Mario Kart DS, and Metroid Prime Hunters, and this seems to be the standard response to 0x00
                output[7] = 0x01 # Initialization response
                s.sendto(output, addr)

                # Try to connect to the server
                gameid = utils.get_string(recv_data, 0x16)
                client_id = "%02x" % ord(recv_data[13])

                localip_raw = recv_data[15:19]
                localip = '.'.join(["%d" % ord(x) for x in localip_raw])
                localport_raw = recv_data[19:21]
                localport = utils.get_short_be(localport_raw, 0)
                localaddr = (localip, localport)

                if gameid not in self.session_list:
                    self.session_list[gameid] = {}
                if session_id not in self.session_list[gameid]:
                    self.session_list[gameid][session_id] = {}
                if client_id not in self.session_list[gameid][session_id]:
                    self.session_list[gameid][session_id][client_id] = { 'connected': False, 'addr': '', 'localaddr': None, 'serveraddr': None, 'gameid': None }

                self.session_list[gameid][session_id][client_id]['gameid'] = utils.get_string(recv_data[21:], 0)
                self.session_list[gameid][session_id][client_id]['addr'] = addr
                self.session_list[gameid][session_id][client_id]['localaddr'] = localaddr
                clients = len(self.session_list[gameid][session_id])

                for client in self.session_list[gameid][session_id]:
                    if self.session_list[gameid][session_id][client]['connected'] == False: # and self.session_list[gameid][session_id][client]['localaddr'][1] != 0:
                        if client == client_id:
                            continue

                        #if self.session_list[gameid][session_id][client]['serveraddr'] == None:
                        serveraddr = self.get_server_info(gameid, session_id, client)
                        self.session_list[gameid][session_id][client]['serveraddr'] = serveraddr
                        logger.log(logging.DEBUG, "Found server from local ip/port: %s from %d" % (serveraddr, session_id))

                        publicport = self.session_list[gameid][session_id][client]['addr'][1]
                        if self.session_list[gameid][session_id][client]['localaddr'][1] != 0:
                            publicport = self.session_list[gameid][session_id][client]['localaddr'][1]

                        if self.session_list[gameid][session_id][client]['serveraddr'] != None:
                            publicport = int(self.session_list[gameid][session_id][client]['serveraddr']['publicport'])

                        # Send to requesting client
                        output = bytearray(recv_data[0:12])
                        output += bytearray([int(x) for x in self.session_list[gameid][session_id][client]['addr'][0].split('.')])
                        output += utils.get_bytes_from_short_be(publicport)

                        output += bytearray([0x42, 0x00]) # Unknown, always seems to be \x42\x00
                        output[7] = 0x05
                        #s.sendto(output, (self.session_list[gameid][session_id][client_id]['addr']))
                        s.sendto(output, (self.session_list[gameid][session_id][client_id]['addr'][0], self.session_list[gameid][session_id][client_id]['addr'][1]))

                        logger.log(logging.DEBUG, "Sent connection request to %s:%d..." % (self.session_list[gameid][session_id][client_id]['addr'][0], self.session_list[gameid][session_id][client_id]['addr'][1]))
                        logger.log(logging.DEBUG, utils.pretty_print_hex(output))

                        # Send to other client
                        #if self.session_list[gameid][session_id][client_id]['serveraddr'] == None:
                        serveraddr = self.get_server_info(gameid, session_id, client_id)
                        self.session_list[gameid][session_id][client_id]['serveraddr'] = serveraddr
                        logger.log(logging.DEBUG, "Found server 2 from local ip/port: %s from %d" % (serveraddr, session_id))

                        publicport = self.session_list[gameid][session_id][client_id]['addr'][1]
                        if self.session_list[gameid][session_id][client_id]['localaddr'][1] != 0:
                            publicport = self.session_list[gameid][session_id][client_id]['localaddr'][1]

                        if self.session_list[gameid][session_id][client_id]['serveraddr'] != None:
                            publicport = int(self.session_list[gameid][session_id][client_id]['serveraddr']['publicport'])

                        output = bytearray(recv_data[0:12])
                        output += bytearray([int(x) for x in self.session_list[gameid][session_id][client_id]['addr'][0].split('.')])
                        output += utils.get_bytes_from_short_be(publicport)

                        output += bytearray([0x42, 0x00]) # Unknown, always seems to be \x42\x00
                        output[7] = 0x05
                        #s.sendto(output, (self.session_list[gameid][session_id][client]['addr']))
                        s.sendto(output, (self.session_list[gameid][session_id][client]['addr'][0], self.session_list[gameid][session_id][client]['addr'][1]))

                        logger.log(logging.DEBUG, "Sent connection request to %s:%d..." % (self.session_list[gameid][session_id][client]['addr'][0], self.session_list[gameid][session_id][client]['addr'][1]))
                        logger.log(logging.DEBUG, utils.pretty_print_hex(output))

            elif recv_data[7] == '\x06': # Was able to connect
                client_id = "%02x" % ord(recv_data[13])
                logger.log(logging.DEBUG, "Received connected command from %s:%s..." % (addr[0], addr[1]))

                if gameid not in self.session_list:
                    pass
                if session_id not in self.session_list[gameid]:
                    pass
                if client_id not in self.session_list[gameid][session_id]:
                    pass

                self.session_list[gameid][session_id][client_id]['connected'] = True

            elif recv_data[7] == '\x0a': # Address check. Note: UNTESTED!
                client_id = "%02x" % ord(recv_data[13])
                logger.log(logging.DEBUG, "Received address check command from %s:%s..." % (addr[0], addr[1]))

                output = bytearray(recv_data[0:15])
                output += bytearray([int(x) for x in addr[0].split('.')])
                output += utils.get_bytes_from_short_be(addr[1])
                output += bytearray(recv_data[len(output):])

                output[7] = 0x0b
                s.sendto(output, addr)

                logger.log(logging.DEBUG, "Sent address check response to %s:%d..." % (self.session_list[gameid][session_id][client]['addr'][0], self.session_list[gameid][session_id][client]['addr'][1]))
                logger.log(logging.DEBUG, utils.pretty_print_hex(output))

            elif recv_data[7] == '\x0d':
                client_id = "%02x" % ord(recv_data[13])
                logger.log(logging.DEBUG, "Received report command from %s:%s..." % (addr[0], addr[1]))
                logger.log(logging.DEBUG, utils.pretty_print_hex(recv_data))

                output = bytearray(recv_data)
                output[7] = 0x0e # Report response
                s.sendto(recv_data, addr)

            else: # Was able to connect
                logger.log(logging.DEBUG, "Received unknown command %02x from %s:%s..." % (ord(recv_data[7]), addr[0], addr[1]))

    def get_server_info(self, gameid, session_id, client_id):
        server_info = None
        servers = self.server_manager.get_natneg_server(session_id)._getvalue()

        if servers == None:
            return None

        console = 0
        ipstr = self.session_list[gameid][session_id][client_id]['addr'][0]

        if console != 0:
            ip = str(ctypes.c_int32(utils.get_int_be(bytearray([int(x) for x in ipstr.split('.')]), 0)).value) # Wii
            console = 0
        else:
            ip = str(ctypes.c_int32(utils.get_int(bytearray([int(x) for x in ipstr.split('.')]), 0)).value) # DS
            console = 1

        for server in servers:
            if server['publicip'] == ip:
                server_info = server
                break

        if server_info == None:
            if console != 0:
                ip = str(ctypes.c_int32(utils.get_int_be(bytearray([int(x) for x in ipstr.split('.')]), 0)).value) # Wii
            else:
                ip = str(ctypes.c_int32(utils.get_int(bytearray([int(x) for x in ipstr.split('.')]), 0)).value) # DS

            for server in servers:
                if server['publicip'] == ip:
                    server_info = server
                    break

        return server_info

        # console = 0
        # ipstr = self.session_list[gameid][session_id][client_id]['addr'][0]
        #
        # if console != 0:
        #     ip = str(ctypes.c_int32(utils.get_int_be(bytearray([int(x) for x in ipstr.split('.')]), 0)).value) # Wii
        #     console = 0
        # else:
        #     ip = str(ctypes.c_int32(utils.get_int(bytearray([int(x) for x in ipstr.split('.')]), 0)).value) # DS
        #     console = 1
        #
        # serveraddr = self.server_manager.find_server_by_local_address(ip, self.session_list[gameid][session_id][client_id]['localaddr'][0], self.session_list[gameid][session_id][client_id]['localaddr'][1], self.session_list[gameid][session_id][client_id]['gameid'])._getvalue()
        #
        # if serveraddr == None:
        #     if console != 0:
        #         ip = str(ctypes.c_int32(utils.get_int_be(bytearray([int(x) for x in ipstr.split('.')]), 0)).value) # Wii
        #         console = 0
        #     else:
        #         ip = str(ctypes.c_int32(utils.get_int(bytearray([int(x) for x in ipstr.split('.')]), 0)).value) # DS
        #         console = 1
        #
        #     serveraddr = self.server_manager.find_server_by_local_address(ip, self.session_list[gameid][session_id][client_id]['localaddr'][0], self.session_list[gameid][session_id][client_id]['localaddr'][1], self.session_list[gameid][session_id][client_id]['gameid'])._getvalue()
        #
        # return serveraddr

if __name__ == "__main__":
    natneg_server = GameSpyNatNegServer()
    natneg_server.start()