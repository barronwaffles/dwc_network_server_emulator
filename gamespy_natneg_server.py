#    DWC Network Server Emulator
#    Copyright (C) 2014 polaris-
#    Copyright (C) 2014 ToadKing
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
#
# Server emulator for *.available.gs.nintendowifi.net and *.master.gs.nintendowifi.net
# Query and Reporting: http://docs.poweredbygamespy.com/wiki/Query_and_Reporting_Overview

import logging
import socket
import struct
import threading
import time
import Queue
import gamespy.gs_utility as gs_utils
import other.utils as utils
import traceback

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
        self.natneg_preinit_session = {}
        self.secret_key_list = gs_utils.generate_secret_keys("gslist.cfg")

        self.server_manager = GameSpyServerDatabase(address=("127.0.0.1", 27500), authkey="")
        self.server_manager.connect()

    def start(self):
        try:
            # Start natneg server
            address = ('0.0.0.0', 27901)  # accessible to outside connections (use this if you don't know what you're doing)

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind(address)

            self.write_queue = Queue.Queue()

            logger.log(logging.INFO, "Server is now listening on %s:%s..." % (address[0], address[1]))
            threading.Thread(target=self.write_queue_worker).start()

            while True:
                recv_data, addr = self.socket.recvfrom(2048)

                self.handle_packet(recv_data, addr)
        except:
            logger.log(logging.ERROR, "Unknown exception: %s" % traceback.format_exc())

    def write_queue_send(self, data, address):
        time.sleep(0.05)
        self.socket.sendto(data, address)

    def write_queue_worker(self):
        while True:
            data, address = self.write_queue.get()
            threading.Thread(target=self.write_queue_send, args=(data, address)).start()
            self.write_queue.task_done()

    def handle_packet(self, recv_data, addr):
        logger.log(logging.DEBUG, "Connection from %s:%d..." % (addr[0], addr[1]))
        logger.log(logging.DEBUG, utils.pretty_print_hex(recv_data))

        # Make sure it's a legal packet
        if recv_data[0:6] != bytearray([0xfd, 0xfc, 0x1e, 0x66, 0x6a, 0xb2]):
            return

        session_id = struct.unpack("<I", recv_data[8:12])[0]
        session_id_raw = recv_data[8:12]

        # Handle commands
        if recv_data[7] == '\x00':
            logger.log(logging.DEBUG, "Received initialization from %s:%s..." % (addr[0], addr[1]))

            output = bytearray(recv_data[0:14])
            output += bytearray([0xff, 0xff, 0x6d, 0x16, 0xb5, 0x7d, 0xea ]) # Checked with Tetris DS, Mario Kart DS, and Metroid Prime Hunters, and this seems to be the standard response to 0x00
            output[7] = 0x01 # Initialization response
            self.write_queue.put((output, addr))

            # Try to connect to the server
            gameid = utils.get_string(recv_data, 0x15)
            client_id = "%02x" % ord(recv_data[13])

            localip_raw = recv_data[15:19]
            localip_int_le = utils.get_ip(recv_data, 15)
            localip_int_be = utils.get_ip(recv_data, 15, True)
            localip = '.'.join(["%d" % ord(x) for x in localip_raw])
            localport_raw = recv_data[19:21]
            localport = utils.get_short(localport_raw, 0, True)
            localaddr = (localip, localport, localip_int_le, localip_int_be)

            self.session_list.setdefault(session_id, {}).setdefault(client_id, {
                'connected': False,
                'addr': '',
                'localaddr': None,
                'serveraddr': None,
                'gameid': None
            })

            self.session_list[session_id][client_id]['gameid'] = gameid
            self.session_list[session_id][client_id]['addr'] = addr
            self.session_list[session_id][client_id]['localaddr'] = localaddr
            clients = len(self.session_list[session_id])

            for client in self.session_list[session_id]:
                if self.session_list[session_id][client]['connected'] == False: # and self.session_list[session_id][client]['localaddr'][1] != 0:
                    if client == client_id:
                        continue

                    #if self.session_list[session_id][client]['serveraddr'] == None:
                    serveraddr = self.get_server_info(gameid, session_id, client)
                    if serveraddr == None:
                        serveraddr = self.get_server_info_alt(gameid, session_id, client)

                    self.session_list[session_id][client]['serveraddr'] = serveraddr
                    logger.log(logging.DEBUG, "Found server from local ip/port: %s from %d" % (serveraddr, session_id))

                    publicport = self.session_list[session_id][client]['addr'][1]
                    if self.session_list[session_id][client]['localaddr'][1] != 0:
                        publicport = self.session_list[session_id][client]['localaddr'][1]

                    if self.session_list[session_id][client]['serveraddr'] != None:
                        publicport = int(self.session_list[session_id][client]['serveraddr']['publicport'])

                    # Send to requesting client
                    output = bytearray(recv_data[0:12])
                    output += bytearray([int(x) for x in self.session_list[session_id][client]['addr'][0].split('.')])
                    output += utils.get_bytes_from_short(publicport, True)

                    output += bytearray([0x42, 0x00]) # Unknown, always seems to be \x42\x00
                    output[7] = 0x05
                    #self.write_queue.put((output, (self.session_list[session_id][client_id]['addr'])))
                    self.write_queue.put((output, (self.session_list[session_id][client_id]['addr'][0], self.session_list[session_id][client_id]['addr'][1])))

                    logger.log(logging.DEBUG, "Sent connection request to %s:%d..." % (self.session_list[session_id][client_id]['addr'][0], self.session_list[session_id][client_id]['addr'][1]))
                    logger.log(logging.DEBUG, utils.pretty_print_hex(output))

                    # Send to other client
                    #if self.session_list[session_id][client_id]['serveraddr'] == None:
                    serveraddr = self.get_server_info(gameid, session_id, client_id)
                    if serveraddr == None:
                        serveraddr = self.get_server_info_alt(gameid, session_id, client_id)

                    self.session_list[session_id][client_id]['serveraddr'] = serveraddr
                    logger.log(logging.DEBUG, "Found server 2 from local ip/port: %s from %d" % (serveraddr, session_id))

                    publicport = self.session_list[session_id][client_id]['addr'][1]
                    if self.session_list[session_id][client_id]['localaddr'][1] != 0:
                        publicport = self.session_list[session_id][client_id]['localaddr'][1]

                    if self.session_list[session_id][client_id]['serveraddr'] != None:
                        publicport = int(self.session_list[session_id][client_id]['serveraddr']['publicport'])

                    output = bytearray(recv_data[0:12])
                    output += bytearray([int(x) for x in self.session_list[session_id][client_id]['addr'][0].split('.')])
                    output += utils.get_bytes_from_short(publicport, True)

                    output += bytearray([0x42, 0x00]) # Unknown, always seems to be \x42\x00
                    output[7] = 0x05
                    #self.write_queue.put((output, (self.session_list[session_id][client]['addr'])))
                    self.write_queue.put((output, (self.session_list[session_id][client]['addr'][0], self.session_list[session_id][client]['addr'][1])))

                    logger.log(logging.DEBUG, "Sent connection request to %s:%d..." % (self.session_list[session_id][client]['addr'][0], self.session_list[session_id][client]['addr'][1]))
                    logger.log(logging.DEBUG, utils.pretty_print_hex(output))

        elif recv_data[7] == '\x06': # Was able to connect
            client_id = "%02x" % ord(recv_data[13])
            logger.log(logging.DEBUG, "Received connected command from %s:%s..." % (addr[0], addr[1]))

            if session_id in self.session_list and client_id in self.session_list[session_id]:
                self.session_list[session_id][client_id]['connected'] = True

        elif recv_data[7] == '\x0a': # Address check. Note: UNTESTED!
            client_id = "%02x" % ord(recv_data[13])
            logger.log(logging.DEBUG, "Received address check command from %s:%s..." % (addr[0], addr[1]))

            output = bytearray(recv_data[0:15])
            output += bytearray([int(x) for x in addr[0].split('.')])
            output += utils.get_bytes_from_short(addr[1], True)
            output += bytearray(recv_data[len(output):])

            output[7] = 0x0b
            self.write_queue.put((output, addr))

            logger.log(logging.DEBUG, "Sent address check response to %s:%d..." % (addr[0], addr[1]))
            logger.log(logging.DEBUG, utils.pretty_print_hex(output))

        elif recv_data[7] == '\x0c': # Natify
            port_type = "%02x" % ord(recv_data[12])
            logger.log(logging.DEBUG, "Received natify command from %s:%s..." % (addr[0], addr[1]))

            output = bytearray(recv_data)
            output[7] = 0x02 # ERT Test
            self.write_queue.put((output, addr))

            logger.log(logging.DEBUG, "Sent natify response to %s:%d..." % (addr[0], addr[1]))
            logger.log(logging.DEBUG, utils.pretty_print_hex(output))

        elif recv_data[7] == '\x0d': # Report
            logger.log(logging.DEBUG, "Received report command from %s:%s..." % (addr[0], addr[1]))
            logger.log(logging.DEBUG, utils.pretty_print_hex(recv_data))

            # Report response
            output = bytearray(recv_data[:21])
            output[7] = 0x0e # Report response
            output[14] = 0 # Clear byte to match real server's response
            self.write_queue.put((output, addr))

        elif recv_data[7] == '\x0f':
            # Natneg v4 command thanks to Pipian.
            # Only seems to be used in very few DS games (namely, Pokemon Black/White/Black 2/White 2).
            logger.log(logging.DEBUG, "Received pre-init command from %s:%s..." % (addr[0], addr[1]))
            logger.log(logging.DEBUG, utils.pretty_print_hex(recv_data))

            session = utils.get_int(recv_data[-4:], 0)

            # Report response
            output = bytearray(recv_data[:-4]) + bytearray([0, 0, 0, 0])
            output[7] = 0x10 # Pre-init response

            if session == 0:
                # What's the correct behavior when session == 0?
                output[13] = 2
            elif session in self.natneg_preinit_session:
                # Should this be sent to both clients or just the one that connected most recently?
                # I can't tell from a one sided packet capture of Pokemon.
                # For the time being, send to both clients just in case.
                output[13] = 2
                self.write_queue.put((output, self.natneg_preinit_session[session]))

                output[12] = (1, 0)[output[12]] # Swap the index
                del self.natneg_preinit_session[session]
            else:
                output[13] = 0
                self.natneg_preinit_session[session] = addr

            self.write_queue.put((output, addr))

        else: # Was able to connect
            logger.log(logging.DEBUG, "Received unknown command %02x from %s:%s..." % (ord(recv_data[7]), addr[0], addr[1]))

    def get_server_info(self, gameid, session_id, client_id):
        server_info = None
        servers = self.server_manager.get_natneg_server(session_id)._getvalue()

        if servers == None:
            return None

        console = False
        ipstr = self.session_list[session_id][client_id]['addr'][0]

        ip = str(utils.get_ip(bytearray([int(x) for x in ipstr.split('.')]), 0, console))
        console = not console

        server_info = next((s for s in servers if s['publicip'] == ip), None)

        if server_info == None:
            ip = str(utils.get_ip(bytearray([int(x) for x in ipstr.split('.')]), 0, console))

            server_info = next((s for s in servers if s['publicip'] == ip), None)

        return server_info

    def get_server_info_alt(self, gameid, session_id, client_id):
        console = False
        ipstr = self.session_list[session_id][client_id]['addr'][0]

        ip = str(utils.get_ip(bytearray([int(x) for x in ipstr.split('.')]), 0, console))
        console = not console

        serveraddr = self.server_manager.find_server_by_local_address(ip, self.session_list[session_id][client_id]['localaddr'], self.session_list[session_id][client_id]['gameid'])._getvalue()

        if serveraddr == None:
            ip = str(utils.get_ip(bytearray([int(x) for x in ipstr.split('.')]), 0, console))

            serveraddr = self.server_manager.find_server_by_local_address(ip, self.session_list[session_id][client_id]['localaddr'],
                                                                              self.session_list[session_id][client_id]['gameid'])._getvalue()

        return serveraddr

if __name__ == "__main__":
    natneg_server = GameSpyNatNegServer()
    natneg_server.start()
