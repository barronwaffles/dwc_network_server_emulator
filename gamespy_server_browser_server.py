# I found an open source implemention of this exact server I'm trying to emulate here: https://github.com/sfcspanky/Openspy-Core/blob/master/serverbrowsing/
# Use as reference later.

import logging
import socket
import ctypes
import traceback

from twisted.internet.protocol import Factory
from twisted.internet.endpoints import serverFromString
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning

import gamespy.gs_utility as gs_utils
import other.utils as utils

from multiprocessing.managers import BaseManager

class ServerListFlags:
    UNSOLICITED_UDP_FLAG = 1
    PRIVATE_IP_FLAG = 2
    CONNECT_NEGOTIATE_FLAG = 4
    ICMP_IP_FLAG = 8
    NONSTANDARD_PORT_FLAG = 16
    NONSTANDARD_PRIVATE_PORT_FLAG = 32
    HAS_KEYS_FLAG = 64
    HAS_FULL_RULES_FLAG = 128

# Logger settings
logger_output_to_console = True
logger_output_to_file = True
logger_name = "GameSpyServerBrowserServer"
logger_filename = "gamespy_server_browser_server.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

class GameSpyServerDatabase(BaseManager):
    pass

GameSpyServerDatabase.register("get_server_list")
GameSpyServerDatabase.register("modify_server_list")
GameSpyServerDatabase.register("find_servers")
GameSpyServerDatabase.register("find_server_by_address")
GameSpyServerDatabase.register("add_natneg_server")
GameSpyServerDatabase.register("get_natneg_server")
GameSpyServerDatabase.register("delete_natneg_server")

address = ("0.0.0.0", 28910)
class GameSpyServerBrowserServer(object):
    def __init__(self, qr = None):
        self.qr = qr

    def start(self):
        endpoint = serverFromString(reactor, "tcp:%d:interface=%s" % (address[1], address[0]))
        conn = endpoint.listen(SessionFactory(self.qr))

        try:
            if reactor.running == False:
                reactor.run(installSignalHandlers=0)
        except ReactorAlreadyRunning:
            pass



class SessionFactory(Factory):
    def __init__(self, qr):
        logger.log(logging.INFO, "Now listening for connections on %s:%d...", address[0], address[1])
        self.secret_key_list = gs_utils.generate_secret_keys("gslist.cfg")

        # TODO: Prune server cache at some point
        self.server_cache = {}
        self.qr = qr

    def buildProtocol(self, address):
        return Session(address, self.secret_key_list, self.server_cache, self.qr)


class Session(LineReceiver):
    def __init__(self, address, secret_key_list, server_cache, qr):
        self.setRawMode() # We're dealing with binary data so set to raw mode
        self.address = address
        self.forward_to_client = False
        self.forward_client = None
        self.header_length = 0
        self.expected_packet_length = 0
        self.forward_packet = None
        self.secret_key_list = secret_key_list # Don't waste time parsing every session, so just accept it from the parent
        self.console = 0
        self.server_cache = server_cache
        self.qr = qr

        manager_address = ("127.0.0.1", 27500)
        manager_password = ""
        self.server_manager = GameSpyServerDatabase(address = manager_address, authkey= manager_password)
        self.server_manager.connect()

    def log(self, level, message):
        logger.log(level, "[%s:%d] %s", self.address.host, self.address.port,message)

    def rawDataReceived(self, data):
        try:
            # First 2 bytes are the packet size.
            #
            # Third byte is the command byte.
            # According to Openspy-Core:
            #   0x00 - Server list request
            #   0x01 - Server info request
            #   0x02 - Send message request
            #   0x03 - Keep alive reply
            #   0x04 - Map loop request (?)
            #   0x05 - Player search request
            #
            # For Tetris DS, at the very least 0x00 and 0x02 need to be implemented.
            if self.forward_to_client:
                if self.forward_packet == None:
                    self.forward_packet = data
                else:
                    self.forward_packet += data

                if self.header_length + len(self.forward_packet) >= self.expected_packet_length:
                    # Is it possible that multiple packets will need to be waited for?
                    # Is it possible that more data will be in the last packet than expected?
                    self.forward_data_to_client(self.forward_packet, self.forward_client)

                    self.forward_to_client = False
                    self.forward_client = None
                    self.header_length = 0
                    self.expected_packet_length = 0
                    self.forward_packet = None
                return

            if data[2] == '\x00': # Server list request
                self.log(logging.DEBUG, "Received server list request from %s:%s..." % (self.address.host, self.address.port))

                # This code is so... not python. The C programmer in me is coming out strong.
                # TODO: Rewrite this section later?
                idx = 3
                list_version = ord(data[idx])
                idx += 1
                encoding_version = ord(data[idx])
                idx += 1
                game_version = utils.get_int(data, idx)
                idx += 4

                query_game = utils.get_string(data, idx)
                idx += len(query_game) + 1
                game_name = utils.get_string(data, idx)
                idx += len(game_name) + 1

                challenge = data[idx:idx+8]
                idx += 8

                filter = utils.get_string(data, idx)
                idx += len(filter) + 1
                fields = utils.get_string(data, idx)
                idx += len(fields) + 1

                options = utils.get_int_be(data, idx)
                idx += 4

                source_ip = 0
                max_servers = 0

                NO_SERVER_LIST = 0x02
                ALTERNATE_SOURCE_IP = 0x08
                LIMIT_RESULT_COUNT = 0x80

                send_ip = False
                if (options & LIMIT_RESULT_COUNT):
                    max_servers = utils.get_int(data, idx)
                elif (options & ALTERNATE_SOURCE_IP):
                    source_ip = utils.get_int(data, idx)
                elif (options & NO_SERVER_LIST):
                    send_ip = True

                if '\\' in fields:
                    fields = [x for x in fields.split('\\') if x and not x.isspace()]

                #print "%02x %02x %08x" % (list_version, encoding_version, game_version)
                #print "%s" % query_game
                #print "%s" % game_name
                #print "%s" % challenge
                #print "%s" % filter
                #print "%s" % fields

                #print "%08x" % options
                #print "%d %08x" % (max_servers, source_ip)

                self.log(logging.DEBUG, "list version: %02x / encoding version: %02x / game version: %08x / query game: %s / game name: %s / challenge: %s / filter: %s / fields: %s / options: %08x / max servers: %d / source ip: %08x" % (list_version, encoding_version, game_version, query_game, game_name, challenge, filter, fields, options, max_servers, source_ip))

                # Requesting ip and port of client, not server
                if filter == "" or fields == "" or send_ip == True:
                    output = bytearray([int(x) for x in self.address.host.split('.')])
                    output += utils.get_bytes_from_short_be(6500) # Does this ever change?

                    enc = gs_utils.EncTypeX()
                    output_enc = enc.encrypt(self.secret_key_list[game_name], challenge, output)

                    self.transport.write(bytes(output_enc))

                    self.log(logging.DEBUG, "Responding with own IP and game port...")
                    self.log(logging.DEBUG, utils.pretty_print_hex(output))
                else:
                    self.find_server(query_game, filter, fields, max_servers, game_name, challenge)



            elif data[2] == '\x02': # Send message request
                packet_len = utils.get_short_be(data, 0)
                dest_addr = '.'.join(["%d" % ord(x) for x in data[3:7]])
                dest_port = utils.get_short_be(data, 7) # What's the pythonic way to do this? unpack?
                dest = (dest_addr, dest_port)

                self.log(logging.DEBUG, "Received send message request from %s:%s to %s:%d... expecting %d byte packet." % (self.address.host, self.address.port, dest_addr, dest_port, packet_len))
                self.log(logging.DEBUG, utils.pretty_print_hex(bytearray(data)))

                if packet_len == len(data):
                    # Contains entire packet, send immediately.
                    self.forward_data_to_client(data[3:], dest)

                    self.forward_to_client = False
                    self.forward_client = None
                    self.header_length = 0
                    self.expected_packet_length = 0
                    self.forward_packet = None
                else:
                    self.forward_to_client = True
                    self.forward_client = dest
                    self.header_length = len(data)
                    self.expected_packet_length = packet_len

            elif data[2] == '\x03': # Keep alive reply
                self.log(logging.DEBUG, "Received keep alive from %s:%s..." % (self.address.host, self.address.port))

            else:
                self.log(logging.DEBUG, "Received unknown command (%02x) from %s:%s..." % (ord(data[2]), self.address.host, self.address.port))
                self.log(logging.DEBUG, utils.pretty_print_hex(bytearray(data)))
                self.log(logging.DEBUG, utils.pretty_print_hex(data))
        except:
            self.log(logging.ERROR, "Unknown exception: %s" % traceback.format_exc())

    def get_game_id(self, data):
        game_id = data[5: -1]
        return game_id

    def get_server_list(self, game, filter, fields, max_count):
        results = self.server_manager.find_servers(game, filter, fields, max_count)
        return results

    def generate_server_list_data(self, address, fields, server_info):
        output = bytearray()

        # Write the address
        output += bytearray([int(x) for x in address.host.split('.')])

        # Write the port
        output += utils.get_bytes_from_short_be(address.port)

        #if len(server_info) > 0:
        if True:
            # Write number of fields that will be returned.
            key_count = len(fields)
            output += utils.get_bytes_from_short(key_count)

            if key_count != len(fields):
                # For some reason we didn't get all of the expected data.
                self.log(logging.WARNING, "key_count[%d] != len(fields)[%d]" % (key_count, len(fields)))
                self.log(logging.WARNING, fields)

            flags_buffer = bytearray()

            # Write the fields
            for field in fields:
                output += bytearray(field) + '\0\0'

            # Start server loop here instead of including all of the fields and stuff again
            flags = 0
            if len(server_info) != 0:
                flags |= ServerListFlags.HAS_KEYS_FLAG

                if "natneg" in server_info:
                    flags |= ServerListFlags.CONNECT_NEGOTIATE_FLAG

                ip = 0
                if self.console != 0:
                    ip = utils.get_bytes_from_int_be(int(server_info['publicip'])) # Wii
                    flags_buffer += ip
                else:
                    ip = utils.get_bytes_from_int(int(server_info['publicip'])) # DS
                    flags_buffer += ip

                flags |= ServerListFlags.NONSTANDARD_PORT_FLAG

                if server_info['publicport'] != "0":
                    flags_buffer += utils.get_bytes_from_short_be(int(server_info['publicport']))
                else:
                    flags_buffer += utils.get_bytes_from_short_be(int(server_info['localport']))

                if "localip0" in server_info:
                    # How to handle multiple localips?
                    flags |= ServerListFlags.PRIVATE_IP_FLAG
                    flags_buffer += bytearray([int(x) for x in server_info['localip0'].split('.')]) #ip

                if "localport" in server_info:
                    flags |= ServerListFlags.NONSTANDARD_PRIVATE_PORT_FLAG
                    flags_buffer += utils.get_bytes_from_short_be(int(server_info['localport']))

                flags |= ServerListFlags.ICMP_IP_FLAG
                flags_buffer += bytearray([int(x) for x in "0.0.0.0".split('.')])

                output += bytearray([flags & 0xff])
                output += flags_buffer

                if (flags & ServerListFlags.HAS_KEYS_FLAG):
                    # Write data for associated fields
                    if 'requested' in server_info:
                        for field in fields:
                            output += '\xff' + bytearray(server_info['requested'][field]) + '\0'

            output += '\0'
            output += utils.get_bytes_from_int(-1)

        return output

    def find_server(self, query_game, filter, fields, max_servers, game_name, challenge):
        # Get dictionary from master server list server.
        self.log(logging.DEBUG, "Searching for server matching '%s' with the fields '%s'" % (filter, fields))

        self.server_list = self.server_manager.find_servers(query_game, filter, fields, max_servers)._getvalue()

        self.log(logging.DEBUG, "Found server(s):")
        self.log(logging.DEBUG, self.server_list)

        if self.server_list == []:
            self.server_list.append({})

        for _server in self.server_list:
            server = _server
            if server and fields and 'requested' in server and server['requested'] == {}:
                # If the requested fields weren't found then don't return a server.
                # This fixes a bug with Mario Kart DS.
                #print "Requested was empty"
                server = {}

            if "__console__" in server:
                self.console = int(server['__console__'])

            # Generate binary server list data
            data = self.generate_server_list_data(self.address, fields, server)
            self.log(logging.DEBUG, utils.pretty_print_hex(data))

            # Encrypt data
            enc = gs_utils.EncTypeX()
            data = enc.encrypt(self.secret_key_list[game_name], challenge, data)

            # Send to client
            self.transport.write(bytes(data))
            self.log(logging.DEBUG, "Sent server list message to %s:%s..." % (self.address.host, self.address.port))

            # if "publicip" in server and "publicport" in server:
            #     self.server_cache[str(server['publicip']) + str(server['publicport'])] = server

    def find_server_in_cache(self, addr, port, console):
        if console != 0:
            ip = str(ctypes.c_int32(utils.get_int_be(bytearray([int(x) for x in addr.split('.')]), 0)).value) # Wii
        else:
            ip = str(ctypes.c_int32(utils.get_int(bytearray([int(x) for x in addr.split('.')]), 0)).value) # DS

        self.log(logging.DEBUG, "IP: %s, Console: %d" % (ip, console))

        # Get server based on ip/port
        # server = None
        # self.log(logging.DEBUG, self.server_cache)
        # self.log(logging.DEBUG, "Searching for: %s %s" % (ip + str(port), addr))
        # if (str(ip) + str(port)) in self.server_cache:
        #     server = self.server_cache[ip + str(port)]
        #     #self.server_cache.pop((publicip + str(self.forward_client[1])))

        server = self.server_manager.find_server_by_address(ip, self.forward_client[1])._getvalue()
        self.log(logging.DEBUG, "find_server_in_cache is returning: %s %s" % (server, ip))

        return server, ip

    def forward_data_to_client(self, data, forward_client):
        # Find session id of server
        # Iterate through the list of servers sent to the client and match by IP and port.
        # Is there a better way to determine this information?
        if self.forward_client == None or len(self.forward_client) != 2:
            return

        server, ip = self.find_server_in_cache(self.forward_client[0], self.forward_client[1], self.console)

        if server == None:
            if self.console == 0:
                server, ip = self.find_server_in_cache(self.forward_client[0], self.forward_client[1], 1) # Try Wii
            elif self.console == 1:
                server, ip = self.find_server_in_cache(self.forward_client[0], self.forward_client[1], 0) # Try DS

        self.log(logging.DEBUG, "find_server_in_cache returned: %s" % server)
        self.log(logging.DEBUG, "Trying to send message to %s:%d..." % (self.forward_client[0], self.forward_client[1]))
        self.log(logging.DEBUG, utils.pretty_print_hex(bytearray(data)))

        if server == None:
            return

        self.log(logging.DEBUG, "%s %s" % (ip, server['publicip']))
        if server['publicip'] == ip and server['publicport'] == str(self.forward_client[1]):
            if self.forward_client[1] == 0 and 'localport' in server:
                # No public port returned from client, try contacting on the local port.
                self.forward_client = (self.forward_client[0], int(server['localport']))

            # Send command to server to get it to connect to natneg
            cookie = int(utils.generate_random_hex_str(8), 16) # Quick and lazy way to get a random 32bit integer. Replace with something else later

            if len(data) == 10 and bytearray(data)[0:6] == bytearray([0xfd, 0xfc, 0x1e, 0x66, 0x6a, 0xb2]):
                natneg_session = utils.get_int(data,6)
                self.log(logging.DEBUG, "Adding %d to natneg server list: %s" % (natneg_session, server))
                self.server_manager.add_natneg_server(natneg_session, server) # Store info in backend so we can get it later in natneg

                # if self.qr != None:
                #     own_server = self.qr.get_own_server()
                #
                #     self.log(logging.DEBUG, "Adding %d to natneg server list: %s" % (natneg_session, own_server))
                #     self.server_manager.add_natneg_server(natneg_session, own_server) # Store info in backend so we can get it later in natneg

            output = bytearray([0xfe, 0xfd, 0x06])
            output += utils.get_bytes_from_int(server['__session__'])
            output += bytearray(utils.get_bytes_from_int(cookie))
            output += bytearray(data)

            if self.qr != None:
                self.log(logging.DEBUG, "Forwarded data to %s:%s through QR server..." % (forward_client[0], forward_client[1]))
                self.qr.socket.sendto(output, forward_client)
            else:
                # In case we can't contact the QR server, just try sending the packet directly.
                # This isn't standard behavior but it can work in some instances.
                self.log(logging.DEBUG, "Forwarded data to %s:%s directly (potential error occurred)..." % (forward_client[0], forward_client[1]))
                client_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client_s.sendto(output, forward_client)
                
if __name__ == "__main__":
    server_browser = GameSpyServerBrowserServer()
    server_browser.start()