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

I found an open source implemention of this exact server I'm trying to
emulate here: (use as reference later)
https://github.com/sfcspanky/Openspy-Core/blob/master/serverbrowsing/
"""

import logging
import socket
import traceback

from twisted.internet.protocol import Factory
from twisted.internet.endpoints import serverFromString
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning

import gamespy.gs_utility as gs_utils
import other.utils as utils
import dwc_config

from multiprocessing.managers import BaseManager

logger = dwc_config.get_logger('GameSpyServerBrowserServer')


class ServerListFlags:
    UNSOLICITED_UDP_FLAG = 1
    PRIVATE_IP_FLAG = 2
    CONNECT_NEGOTIATE_FLAG = 4
    ICMP_IP_FLAG = 8
    NONSTANDARD_PORT_FLAG = 16
    NONSTANDARD_PRIVATE_PORT_FLAG = 32
    HAS_KEYS_FLAG = 64
    HAS_FULL_RULES_FLAG = 128


class GameSpyServerDatabase(BaseManager):
    pass

GameSpyServerDatabase.register("get_server_list")
GameSpyServerDatabase.register("modify_server_list")
GameSpyServerDatabase.register("find_servers")
GameSpyServerDatabase.register("find_server_by_address")
GameSpyServerDatabase.register("add_natneg_server")
GameSpyServerDatabase.register("get_natneg_server")
GameSpyServerDatabase.register("delete_natneg_server")

address = dwc_config.get_ip_port('GameSpyServerBrowserServer')


class GameSpyServerBrowserServer(object):
    def __init__(self, qr=None):
        self.qr = qr

    def start(self):
        endpoint = serverFromString(
            reactor, "tcp:%d:interface=%s" % (address[1], address[0])
        )
        conn = endpoint.listen(SessionFactory(self.qr))

        try:
            if not reactor.running:
                reactor.run(installSignalHandlers=0)
        except ReactorAlreadyRunning:
            pass


class SessionFactory(Factory):
    def __init__(self, qr):
        logger.log(logging.INFO,
                   "Now listening for connections on %s:%d...",
                   address[0], address[1])
        self.secret_key_list = gs_utils.generate_secret_keys("gslist.cfg")

        # TODO: Prune server cache at some point
        self.server_cache = {}
        self.qr = qr

    def buildProtocol(self, address):
        return Session(address, self.secret_key_list, self.server_cache,
                       self.qr)


class Session(LineReceiver):
    def __init__(self, address, secret_key_list, server_cache, qr):
        self.setRawMode()  # We're dealing with binary data so set to raw mode
        self.address = address
        # Don't waste time parsing every session, so just accept it from
        # the parent
        self.secret_key_list = secret_key_list
        self.console = 0
        self.server_cache = server_cache
        self.qr = qr
        self.own_server = None
        self.buffer = []

        manager_address = dwc_config.get_ip_port('GameSpyManager')
        manager_password = ""
        self.server_manager = GameSpyServerDatabase(address=manager_address,
                                                    authkey=manager_password)
        self.server_manager.connect()

    def log(self, level, msg, *args, **kwargs):
        """TODO: Use logger format"""
        logger.log(level, "[%s:%d] " + msg,
                   self.address.host, self.address.port,
                   *args, **kwargs)

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
            # For Tetris DS, at the very least 0x00 and 0x02 need to be
            # implemented.

            self.buffer += data

            while len(self.buffer) > 0:
                packet_len = utils.get_short(self.buffer, 0, True)
                packet = None

                if len(self.buffer) >= packet_len:
                    packet = self.buffer[:packet_len]
                    self.buffer = self.buffer[packet_len:]

                if packet is None:
                    # Don't have enough for the entire packet, break.
                    break

                if packet[2] == '\x00':  # Server list request
                    self.log(logging.DEBUG,
                             "Received server list request from %s:%s...",
                             self.address.host, self.address.port)

                    # This code is so... not python. The C programmer in me is
                    # coming out strong.
                    # TODO: Rewrite this section later?
                    idx = 3
                    list_version = ord(packet[idx])
                    idx += 1
                    encoding_version = ord(packet[idx])
                    idx += 1
                    game_version = utils.get_int(packet, idx)
                    idx += 4

                    query_game = utils.get_string(packet, idx)
                    idx += len(query_game) + 1
                    game_name = utils.get_string(packet, idx)
                    idx += len(game_name) + 1

                    challenge = ''.join(packet[idx:idx+8])
                    idx += 8

                    filter = utils.get_string(packet, idx)
                    idx += len(filter) + 1
                    fields = utils.get_string(packet, idx)
                    idx += len(fields) + 1

                    options = utils.get_int(packet, idx, True)
                    idx += 4

                    source_ip = 0
                    max_servers = 0

                    NO_SERVER_LIST = 0x02
                    ALTERNATE_SOURCE_IP = 0x08
                    LIMIT_RESULT_COUNT = 0x80

                    send_ip = False
                    if (options & LIMIT_RESULT_COUNT):
                        max_servers = utils.get_int(packet, idx)
                    elif (options & ALTERNATE_SOURCE_IP):
                        source_ip = utils.get_ip(packet, idx)
                    elif (options & NO_SERVER_LIST):
                        send_ip = True

                    if '\\' in fields:
                        fields = [x for x in fields.split('\\')
                                  if x and not x.isspace()]

                    # print "%02x %02x %08x" % \
                    #       (list_version, encoding_version, game_version)
                    # print "%s" % query_game
                    # print "%s" % game_name
                    # print "%s" % challenge
                    # print "%s" % filter
                    # print "%s" % fields

                    # print "%08x" % options
                    # print "%d %08x" % (max_servers, source_ip)

                    self.log(logging.DEBUG,
                             "list version: %02x / encoding version: %02x /"
                             " game version: %08x / query game: %s /"
                             " game name: %s / challenge: %s / filter: %s /"
                             " fields: %s / options: %08x / max servers: %d /"
                             " source ip: %08x",
                             list_version, encoding_version,
                             game_version, query_game,
                             game_name, challenge, filter,
                             fields, options, max_servers,
                             source_ip)

                    # Requesting ip and port of client, not server
                    if not filter and not fields or send_ip:
                        output = bytearray(
                            [int(x) for x in self.address.host.split('.')]
                        )
                        # Does this ever change?
                        output += utils.get_bytes_from_short(6500, True)

                        enc = gs_utils.EncTypeX()
                        output_enc = enc.encrypt(
                            self.secret_key_list[game_name],
                            challenge,
                            output
                        )

                        self.transport.write(bytes(output_enc))

                        self.log(logging.DEBUG,
                                 "%s",
                                 "Responding with own IP and game port...")
                        self.log(logging.DEBUG,
                                 "%s",
                                 utils.pretty_print_hex(output))
                    else:
                        self.find_server(query_game, filter, fields,
                                         max_servers, game_name, challenge)

                elif packet[2] == '\x02':  # Send message request
                    packet_len = utils.get_short(packet, 0, True)
                    dest_addr = '.'.join(["%d" % ord(x) for x in packet[3:7]])
                    # What's the pythonic way to do this? unpack?
                    dest_port = utils.get_short(packet, 7, True)
                    dest = (dest_addr, dest_port)

                    self.log(logging.DEBUG,
                             "Received send message request from %s:%s to"
                             " %s:%d... expecting %d byte packet.",
                             self.address.host, self.address.port,
                             dest_addr, dest_port, packet_len)
                    self.log(logging.DEBUG,
                             "%s",
                             utils.pretty_print_hex(bytearray(packet)))

                    if packet_len == len(packet):
                        # Contains entire packet, send immediately.
                        self.forward_data_to_client(packet[9:], dest)
                    else:
                        self.log(logging.ERROR,
                                 "%s",
                                 "ERROR: Could not find entire packet.")

                elif packet[2] == '\x03':  # Keep alive reply
                    self.log(logging.DEBUG,
                             "Received keep alive from %s:%s...",
                             self.address.host, self.address.port)

                else:
                    self.log(logging.DEBUG,
                             "Received unknown command (%02x) from %s:%s...",
                             ord(packet[2]),
                             self.address.host, self.address.port)
                    self.log(logging.DEBUG,
                             "%s",
                             utils.pretty_print_hex(bytearray(packet)))
        except:
            self.log(logging.ERROR,
                     "Unknown exception: %s",
                     traceback.format_exc())

    def get_game_id(self, data):
        game_id = data[5: -1]
        return game_id

    def get_server_list(self, game, filter, fields, max_count):
        results = self.server_manager.find_servers(game, filter, fields,
                                                   max_count)
        return results

    def generate_server_list_header_data(self, address, fields):
        output = bytearray()

        # Write the address
        output += bytearray([int(x) for x in address.host.split('.')])

        # Write the port
        output += utils.get_bytes_from_short(address.port, True)

        # Write number of fields that will be returned.
        key_count = len(fields)
        output += utils.get_bytes_from_short(key_count)

        if key_count != len(fields):
            # For some reason we didn't get all of the expected data.
            self.log(logging.WARNING,
                     "key_count[%d] != len(fields)[%d]",
                     key_count, len(fields))
            self.log(logging.WARNING, "%s", fields)

        # Write the fields
        for field in fields:
            output += bytearray(field) + '\0\0'

        return output

    def generate_server_list_data(self, address, fields, server_info,
                                  finalize=False):
        output = bytearray()
        flags_buffer = bytearray()

        if len(server_info) > 0:
            # Start server loop here instead of including all of the fields
            # and stuff again
            flags = 0
            if len(server_info) != 0:
                # This condition is always true? Isn't it?
                flags |= ServerListFlags.HAS_KEYS_FLAG

                if "natneg" in server_info:
                    flags |= ServerListFlags.CONNECT_NEGOTIATE_FLAG

                ip = utils.get_bytes_from_int_signed(
                    int(server_info['publicip']), self.console
                )
                flags_buffer += ip

                flags |= ServerListFlags.NONSTANDARD_PORT_FLAG

                if server_info['publicport'] != "0":
                    flags_buffer += utils.get_bytes_from_short(
                        int(server_info['publicport']), True
                    )
                else:
                    flags_buffer += utils.get_bytes_from_short(
                        int(server_info['localport']), True
                    )

                if "localip0" in server_info:
                    # How to handle multiple localips?
                    flags |= ServerListFlags.PRIVATE_IP_FLAG
                    flags_buffer += bytearray(
                        [int(x) for x in server_info['localip0'].split('.')]
                    )  # IP

                if "localport" in server_info:
                    flags |= ServerListFlags.NONSTANDARD_PRIVATE_PORT_FLAG
                    flags_buffer += utils.get_bytes_from_short(
                        int(server_info['localport']), True
                    )

                flags |= ServerListFlags.ICMP_IP_FLAG
                flags_buffer += bytearray(
                    [int(x) for x in "0.0.0.0".split('.')]
                )

                output += bytearray([flags & 0xff])
                output += flags_buffer

                if (flags & ServerListFlags.HAS_KEYS_FLAG):
                    # Write data for associated fields
                    if 'requested' in server_info:
                        for field in fields:
                            output += '\xff' + \
                                      bytearray(
                                          server_info['requested'][field]
                                      ) + '\0'

        return output

    def find_server(self, query_game, filter, fields, max_servers, game_name,
                    challenge):
        def send_encrypted_data(self, challenge, data):
            self.log(logging.DEBUG,
                     "Sent server list message to %s:%s...",
                     self.address.host, self.address.port)
            self.log(logging.DEBUG, "%s", utils.pretty_print_hex(data))

            # Encrypt data
            enc = gs_utils.EncTypeX()
            data = enc.encrypt(self.secret_key_list[game_name],
                               challenge, data)

            # Send to client
            self.transport.write(bytes(data))

        # OpenSpy's max packet length, just go with it for now
        max_packet_length = 256 + 511 + 255

        # Get dictionary from master server list server.
        self.log(logging.DEBUG,
                 "Searching for server matching '%s' with the fields '%s'",
                 filter, fields)

        self.server_list = self.server_manager.find_servers(
            query_game, filter, fields, max_servers
        )._getvalue()

        self.log(logging.DEBUG, "%s", "Found server(s):")
        self.log(logging.DEBUG, "%s", self.server_list)

        if not self.server_list:
            self.server_list = [{}]

        data = self.generate_server_list_header_data(self.address, fields)
        for i in range(0, len(self.server_list)):
            server = self.server_list[i]

            if server and fields and 'requested' in server and \
               not server['requested']:
                # If the requested fields weren't found then don't return
                # a server. This fixes a bug with Mario Kart DS.
                # print "Requested was empty"
                server = {}

            if "__console__" in server:
                self.console = int(server['__console__'])

            # Generate binary server list data
            data += self.generate_server_list_data(
                self.address, fields, server, i >= len(self.server_list)
            )

            if len(data) >= max_packet_length:
                send_encrypted_data(self, challenge, data)
                data = bytearray()

            # if "publicip" in server and "publicport" in server:
            #     self.server_cache[str(server['publicip']) + \
            #                       str(server['publicport'])] = server

        data += '\0'
        data += utils.get_bytes_from_int(0xffffffff)
        send_encrypted_data(self, challenge, data)

    def find_server_in_cache(self, addr, port, console):
        ip = str(utils.get_ip(
            bytearray([int(x) for x in addr.split('.')]),
            0,
            console
        ))
        server = self.server_manager.find_server_by_address(ip,
                                                            port)._getvalue()
        self.log(logging.DEBUG,
                 "find_server_in_cache is returning: %s %s",
                 server, ip)

        return server, ip

    def forward_data_to_client(self, data, forward_client):
        # Find session id of server
        # Iterate through the list of servers sent to the client and match by
        # IP and port. Is there a better way to determine this information?
        if forward_client is None or len(forward_client) != 2:
            return

        server, ip = self.find_server_in_cache(forward_client[0],
                                               forward_client[1], self.console)

        if server is None:
            if self.console == 0:
                server, ip = self.find_server_in_cache(forward_client[0],
                                                       forward_client[1],
                                                       1)  # Try Wii
            elif self.console == 1:
                server, ip = self.find_server_in_cache(forward_client[0],
                                                       forward_client[1],
                                                       0)  # Try DS

        self.log(logging.DEBUG,
                 "find_server_in_cache returned: %s",
                 server)
        self.log(logging.DEBUG,
                 "Trying to send message to %s:%d...",
                 forward_client[0], forward_client[1])
        self.log(logging.DEBUG, "%s", utils.pretty_print_hex(bytearray(data)))

        if server is None:
            return

        self.log(logging.DEBUG, "%s %s", ip, server['publicip'])
        if server['publicip'] == ip and \
           server['publicport'] == str(forward_client[1]):
            if forward_client[1] == 0 and 'localport' in server:
                # No public port returned from client, try contacting on
                # the local port.
                forward_client = (forward_client[0], int(server['localport']))

            # Send command to server to get it to connect to natneg
            # Quick and lazy way to get a random 32bit integer. Replace with
            # something else later
            cookie = int(utils.generate_random_hex_str(8), 16)

            # if (len(data) == 24 and bytearray(data)[0:10] == \
            #     bytearray([0x53, 0x42, 0x43, 0x4d, 0x03,
            #                0x00, 0x00, 0x00, 0x01, 0x04])) or \
            #     (len(data) == 40 and bytearray(data)[0:10] == \
            #                          bytearray([0x53, 0x42, 0x43, 0x4d,
            #                                     0x0b, 0x00, 0x00, 0x00,
            #                                     0x01, 0x04])):
            if self.own_server is None and len(data) >= 16 and \
               bytearray(data)[0:4] in (bytearray([0xbb, 0x49, 0xcc, 0x4d]),
                                        bytearray([0x53, 0x42, 0x43, 0x4d])):
                # Is the endianness the same between the DS and Wii here?
                # It seems so but I'm not positive.
                # Note to self: Port is little endian here.
                self_port = utils.get_short(bytearray(data[10:12]), 0, False)
                self_ip = '.'.join(["%d" % x for x in bytearray(data[12:16])])

                self.own_server, _ = self.find_server_in_cache(self_ip,
                                                               self_port,
                                                               self.console)

                if self.own_server is None:
                    if self.console == 0:
                        # Try Wii
                        self.own_server, _ = self.find_server_in_cache(
                            self_ip, self_port, 1
                        )
                    elif self.console == 1:
                        # Try DS
                        self.own_server, _ = self.find_server_in_cache(
                            self_ip, self_port, 0
                        )

                if self.own_server is None:
                    self.log(logging.DEBUG,
                             "Could not find own server: %s:%d",
                             self_ip, self_port)
                else:
                    self.log(logging.DEBUG,
                             "Found own server: %s",
                             self.own_server)

            elif len(data) == 10 and \
                    bytearray(data)[0:6] == \
                    bytearray([0xfd, 0xfc, 0x1e, 0x66, 0x6a, 0xb2]):
                natneg_session = utils.get_int_signed(data, 6)
                self.log(logging.DEBUG,
                         "Adding %d to natneg server list: %s",
                         natneg_session, server)
                # Store info in backend so we can get it later in natneg
                self.server_manager.add_natneg_server(natneg_session, server)

                if self.own_server is not None:
                    self.log(logging.DEBUG,
                             "Adding %d to natneg server list: %s (self)",
                             natneg_session, self.own_server)
                    # Store info in backend so we can get it later in natneg
                    self.server_manager.add_natneg_server(natneg_session,
                                                          self.own_server)

                # if self.qr is not None:
                #     own_server = self.qr.get_own_server()
                #
                #     self.log(logging.DEBUG,
                #              "Adding %d to natneg server list: %s",
                #              natneg_session, own_server)
                #     self.server_manager.add_natneg_server(natneg_session,
                #                                           own_server)

            output = bytearray([0xfe, 0xfd, 0x06])
            output += utils.get_bytes_from_int(server['__session__'])
            output += bytearray(utils.get_bytes_from_int(cookie))
            output += bytearray(data)

            if self.qr is not None:
                self.log(logging.DEBUG,
                         "Forwarded data to %s:%s through QR server...",
                         forward_client[0], forward_client[1])
                self.qr.socket.sendto(output, forward_client)
            else:
                # In case we can't contact the QR server, just try sending
                # the packet directly. This isn't standard behavior but it
                # can work in some instances.
                self.log(logging.DEBUG,
                         "Forwarded data to %s:%s directly"
                         " (potential error occurred)...",
                         forward_client[0], forward_client[1])
                client_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client_s.sendto(output, forward_client)


if __name__ == "__main__":
    server_browser = GameSpyServerBrowserServer()
    server_browser.start()
