# I found an open source implemention of this exact server I'm trying to emulate here: https://github.com/sfcspanky/Openspy-Core/blob/master/serverbrowsing/
# Use as reference later.

from twisted.internet.protocol import Factory
from twisted.internet.endpoints import serverFromString
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor

import socket
import ctypes
import time
from threading import Thread

import gamespy.gs_utility as gs_utils
import other.utils as utils

from multiprocessing.managers import BaseManager

def get_game_id(data):
    game_id = data[5: -1]
    return game_id

def get_server_list(game, filter, fields, max_count):
    results = server_manager.find_servers(game, filter, fields, max_count)
    return results

class ServerListFlags:
    UNSOLICITED_UDP_FLAG = 1
    PRIVATE_IP_FLAG = 2
    CONNECT_NEGOTIATE_FLAG = 4
    ICMP_IP_FLAG = 8
    NONSTANDARD_PORT_FLAG = 16
    NONSTANDARD_PRIVATE_PORT_FLAG = 32
    HAS_KEYS_FLAG = 64
    HAS_FULL_RULES_FLAG = 128

def generate_server_list_data(address, fields, server_info):
    output = bytearray()

    # Write the address
    output += bytearray([int(x) for x in address.host.split('.')])

    # Write the port
    output += utils.get_bytes_from_short_be(address.port)

    if len(server_info) > 0:
        # Write number of fields that will be returned.
        key_count = len(server_info['requested'])
        output += utils.get_bytes_from_short(key_count)

        if key_count != len(fields):
            # For some reason we didn't get all of the expected data.
            print "key_count[%d] != len(fields)[%d]" % (key_count, len(fields))
            print fields
            return

        flags_buffer = bytearray()

        # Write the fields
        for field in fields:
            output += bytearray(field) + '\0\0'

        # Start server loop here instead of including all of the fields and stuff again
        flags = 0
        if key_count > 0:
            flags |= ServerListFlags.HAS_KEYS_FLAG

        if "natneg" in server_info:
            flags |= ServerListFlags.CONNECT_NEGOTIATE_FLAG

        flags_buffer += utils.get_bytes_from_int(int(server_info['publicip']))

        flags |= ServerListFlags.NONSTANDARD_PORT_FLAG
        flags_buffer += utils.get_bytes_from_short_be(int(server_info['publicport']))

        if "localip0" in server_info:
            flags |= ServerListFlags.PRIVATE_IP_FLAG
            flags_buffer += bytearray([int(x) for x in server_info['localip0'].split('.')])

        if "localport" in server_info:
            flags |= ServerListFlags.NONSTANDARD_PRIVATE_PORT_FLAG
            flags_buffer += utils.get_bytes_from_short_be(int(server_info['localport']))

        flags |= ServerListFlags.ICMP_IP_FLAG
        flags_buffer += bytearray([int(x) for x in "0.0.0.0".split('.')])

        output += bytearray([flags & 0xff])
        output += flags_buffer

        if (flags & ServerListFlags.HAS_KEYS_FLAG):
            # Write data for associated fields
            for field in fields:
                output += '\xff' + bytearray(server_info['requested'][field]) + '\0'

        output += '\0'
        output += utils.get_bytes_from_int(-1)

    return output

class Session(LineReceiver):
    def __init__(self, addr):
        self.setRawMode() # We're dealing with binary data so set to raw mode
        self.addr = addr
        self.forward_to_client = False
        self.forward_client = ()
        self.is_searching = False

        # Amount of time (in seconds) we can search for a match before getting kicked off.
        # Set to -1 to allow keep searching forever until a server appears.
        #self.timeout = 60 * 10
        self.timeout = -1

    def rawDataReceived(self, data):
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
            self.forward_to_client = False

            # Find session id of server
            # Iterate through the list of servers sent to the client and match by IP and port.
            # Is there a better way to determine this information?
            ip = str(ctypes.c_int32(utils.get_int(bytearray([int(x) for x in self.forward_client[0].split('.')]), 0)).value)
            print "Trying to send message to %s:%d..." % (self.forward_client[0], self.forward_client[1])
            utils.print_hex(bytearray(data))

            # Get server based on ip/port
            server = server_manager.find_server_by_address(ip, self.forward_client[1])._getvalue()
            print self.server_list

            if self.server_list == None:
                pass

            #print "%s %s" % (ip, server['publicip'])
            if server['publicip'] == ip and server['publicport'] == str(self.forward_client[1]):
                print server

                # Send command to server to get it to connect to natneg
                natneg_session = int(utils.generate_random_hex_str(8), 16) # Quick and lazy way to get a random 32bit integer. Replace with something else late.r

                output = bytearray([0xfe, 0xfd, 0x06])
                output += utils.get_bytes_from_int(server['__session__'])
                output += bytearray(utils.get_bytes_from_int(natneg_session))
                output += bytearray(data)

                client_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client_s.sendto(output, self.forward_client)
                utils.print_log("Forwarded data to %s:%s..." % (self.forward_client[0], self.forward_client[1]))
            return

        if data[2] == '\x00': # Server list request
            utils.print_log("Received server list request from %s:%s..." % (self.addr.host, self.addr.port))

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

            ALTERNATE_SOURCE_IP = 0x08
            LIMIT_RESULT_COUNT = 0x80
            if (options & LIMIT_RESULT_COUNT):
                max_servers = utils.get_int(data, idx)
            elif (options & ALTERNATE_SOURCE_IP):
                source_ip = utils.get_int(data, idx)

            if '\\' in fields:
                fields = [x for x in fields.split('\\') if x and not x.isspace()]

            #print "%02x %02x %08x" % (list_version, encoding_version, game_version)
            #print "%s" % query_game
            print "%s" % game_name
            #print "%s" % challenge
            print "%s" % filter
            print "%s" % fields

            #print "%08x" % options
            #print "%d %08x" % (max_servers, source_ip)

            if self.is_searching == False:
                self.is_searching = True

                # I still want the connection to close properly when the client disconnects, so put the server search
                # part into its own thread.
                # The game will create a new connection for every search query, so don't worry about setting
                # self.is_searching to False.
                t = Thread(target = self.find_server, args=(query_game, filter, fields, max_servers, game_name, challenge))
                t.start()



        elif data[2] == '\x02': # Send message request
            dest_addr = '.'.join(["%d" % ord(x) for x in data[3:7]])
            dest_port = utils.get_short_be(data, 7) # What's the pythonic way to do this? unpack?
            dest = (dest_addr, dest_port)

            utils.print_log("Received send message request from %s:%s to %s:%d..." % (self.addr.host, self.addr.port, dest_addr, dest_port))

            self.forward_to_client = True
            self.forward_client = dest

        elif data[2] == '\x03': # Keep alive reply
            utils.print_log("Received keep alive from %s:%s..." % (self.addr.host, self.addr.port))

        else:
            utils.print_log("Received unknown command (%02x) from %s:%s... %s" % (ord(data[2]), self.addr.host, self.addr.port, data))

    def find_server(self, query_game, filter, fields, max_servers, game_name, challenge):
            # Get dictionary from master server list server.
            # The game sends a search query only once so we must loop until something is found.
            # Search for the specified amount of time, or if self.timeout is set to -1, until a match is found.
            start = time.time()
            self.server_list = []
            while True:
                self.server_list = get_server_list(query_game, filter, fields, max_servers)._getvalue()

                if self.server_list != []:
                    break

                time.sleep(1) # Sleep 1 second

                if self.timeout != -1 and time.time() - start > self.timeout:
                    break

            # Generate encrypted server list and send to client.
            print self.server_list
            for server in self.server_list:
                # Generate binary server list data
                data = generate_server_list_data(self.addr, fields, server)

                # Encrypt data
                enc = gs_utils.EncTypeX()
                data = enc.encrypt(secret_key_list[game_name], challenge, data)

                # Send to client
                self.transport.write(bytes(data))
                utils.print_log("Sent server list message to %s:%s..." % (self.addr.host, self.addr.port))
                break


class SessionFactory(Factory):
    def __init__(self):
        print "Now listening for connections..."

    def buildProtocol(self, addr):
        return Session(addr)





# Initialize server list server connection
class GamespyServerDatabase(BaseManager):
    pass

GamespyServerDatabase.register("get_server_list")
GamespyServerDatabase.register("modify_server_list")
GamespyServerDatabase.register("find_servers")
GamespyServerDatabase.register("find_server_by_address")

manager_address = ("127.0.0.1", 27500)
manager_password = ""

server_manager = GamespyServerDatabase(address = manager_address, authkey= manager_password)
server_manager.connect()

secret_key_list = gs_utils.generate_secret_keys("gslist.cfg")

endpoint = serverFromString(reactor, "tcp:28910")
conn = endpoint.listen(SessionFactory())
reactor.run()