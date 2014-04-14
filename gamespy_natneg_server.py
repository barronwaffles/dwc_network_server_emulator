# Server emulator for *.available.gs.nintendowifi.net and *.master.gs.nintendowifi.net
# Query and Reporting: http://docs.poweredbygamespy.com/wiki/Query_and_Reporting_Overview

import logging
import socket
import struct
import gamespy.gs_utility as gs_utils
import other.utils as utils

# Logger settings
logger_output_to_console = True
logger_output_to_file = True
logger_name = "GameSpyNatNegServer"
logger_filename = "gamespy_natneg_server.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

class GameSpyNatNegServer(object):
    def __init__(self):
        self.session_list = {}
        self.secret_key_list = gs_utils.generate_secret_keys("gslist.cfg")

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

                if gameid not in self.session_list:
                    self.session_list[gameid] = {}
                if session_id not in self.session_list[gameid]:
                    self.session_list[gameid][session_id] = {}
                if client_id not in self.session_list[gameid][session_id]:
                    self.session_list[gameid][session_id][client_id] = { 'connected': False, 'addr': '' }

                self.session_list[gameid][session_id][client_id]['addr'] = addr
                clients = len(self.session_list[gameid][session_id])

                if self.session_list[gameid][session_id][client_id]['connected'] == False:
                    for client in self.session_list[gameid][session_id]:
                        if client == client_id:
                            continue

                        # Send to requesting client
                        output = bytearray(recv_data[0:12])
                        output += bytearray([int(x) for x in self.session_list[gameid][session_id][client]['addr'][0].split('.')])
                        output += utils.get_bytes_from_short_be(self.session_list[gameid][session_id][client]['addr'][1])

                        output += bytearray([0x42, 0x00]) # Unknown, always seems to be \x42\x00
                        output[7] = 0x05
                        s.sendto(output, (self.session_list[gameid][session_id][client_id]['addr']))

                        logger.log(logging.DEBUG, "Sent connection request to %s:%d..." % (self.session_list[gameid][session_id][client_id]['addr'][0], self.session_list[gameid][session_id][client_id]['addr'][1]))
                        logger.log(logging.DEBUG, utils.pretty_print_hex(output))
                        logger.log(logging.DEBUG, "")

                        # Send to other client
                        output = bytearray(recv_data[0:12])
                        output += bytearray([int(x) for x in self.session_list[gameid][session_id][client_id]['addr'][0].split('.')])
                        output += utils.get_bytes_from_short_be(self.session_list[gameid][session_id][client_id]['addr'][1])

                        output += bytearray([0x42, 0x00]) # Unknown, always seems to be \x42\x00
                        output[7] = 0x05
                        s.sendto(output, (self.session_list[gameid][session_id][client]['addr']))

                        logger.log(logging.DEBUG, "Sent connection request to %s:%d..." % (self.session_list[gameid][session_id][client]['addr'][0], self.session_list[gameid][session_id][client]['addr'][1]))
                        logger.log(logging.DEBUG, utils.pretty_print_hex(output))
                        logger.log(logging.DEBUG, "")

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

            elif recv_data[7] == '\x0d':
                client_id = "%02x" % ord(recv_data[13])
                logger.log(logging.DEBUG, "Received report command from %s:%s..." % (addr[0], addr[1]))
                logger.log(logging.DEBUG, utils.pretty_print_hex(recv_data))

                output = bytearray(recv_data)
                output[7] = 0x0e # Report response
                s.sendto(recv_data, addr)

            else: # Was able to connect
                logger.log(logging.DEBUG, "Received unknown command %02x from %s:%s..." % (ord(recv_data[7]), addr[0], addr[1]))

if __name__ == "__main__":
    natneg_server = GameSpyNatNegServer()
    natneg_server.start()