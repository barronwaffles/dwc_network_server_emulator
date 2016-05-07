"""DWC Network Server Emulator

    Copyright (C) 2014 polaris-
    Copyright (C) 2014 ToadKing
    Copyright (C) 2016 Sepalani

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

 Server emulator for *.available.gs.nintendowifi.net
                 and *.master.gs.nintendowifi.net
 Query and Reporting:
 http://docs.poweredbygamespy.com/wiki/Query_and_Reporting_Overview
 http://wiki.tockdom.com/wiki/Server_NATNEG
"""

import logging
import SocketServer
import threading
import time
import Queue
import gamespy.gs_utility as gs_utils
import other.utils as utils
import traceback

from multiprocessing.managers import BaseManager
import dwc_config

logger = dwc_config.get_logger('GameSpyNatNegServer')


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


def handle_natneg(nn, recv_data, addr, socket):
    """Command: Unknown."""
    logger.log(logging.DEBUG,
               "Received unknown command %02x from %s:%d...",
               ord(recv_data[7]), *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(recv_data))


def handle_natneg_init(nn, recv_data, addr, socket):
    """Command: 0x00 - NN_INIT.

    Send by the client to initialize the connection.

    Example:
    fd fc 1e 66 6a b2 03 00 3d f1 00 71 00 00 01 0a
    00 01 e2 00 00 6d 61 72 69 6f 6b 61 72 74 77 69
    69 00

    Description:
    fd fc 1e 66 6a b2 - NATNEG magic
    03                - NATNEG version
    00                - NATNEG record type
    3d f1 00 71       - Session id
    00                - Port type (between 0x00 and 0x03)
    00                - Client index (0x00 - Client,
                                      0x01 - Host)
    01                - Use game port
    0a 00 01 e2       - Local IP
    00 00             - Local port
    GAME_NAME 00      - Game name
    """
    logger.log(logging.DEBUG, "Received initialization from %s:%d...", *addr)

    session_id = utils.get_int(recv_data, 8)
    output = bytearray(recv_data[0:14])

    # Checked with Tetris DS, Mario Kart DS, and Metroid Prime
    # Hunters, and this seems to be the standard response to 0x00
    output += bytearray([0xff, 0xff, 0x6d, 0x16, 0xb5, 0x7d, 0xea])
    output[7] = 0x01  # Initialization response
    nn.write_queue.put((output, addr, socket))

    # Try to connect to the server
    gameid = utils.get_string(recv_data, 0x15)
    client_id = "%02x" % ord(recv_data[13])
    localaddr = utils.get_local_addr(recv_data, 15)

    nn.session_list \
        .setdefault(session_id, {}) \
        .setdefault(client_id,
                    {
                        'connected': False,
                        'addr': '',
                        'localaddr': None,
                        'serveraddr': None,
                        'gameid': None
                    })

    # In fact, it's a pointer
    client_id_session = nn.session_list[session_id][client_id]
    client_id_session['gameid'] = gameid
    client_id_session['addr'] = addr
    client_id_session['localaddr'] = localaddr

    for client in nn.session_list[session_id]:
        # Another pointer
        client_session = nn.session_list[session_id][client]
        if client_session['connected'] or client == client_id:
            continue

        # --- Send to requesting client
        # Get server info
        serveraddr = nn.get_server_addr(gameid, session_id, client)
        client_session['serveraddr'] = serveraddr
        logger.log(logging.DEBUG,
                   "Found server from local ip/port: %s from %d",
                   serveraddr, session_id)

        # Get public port
        if client_session['serveraddr'] is not None:
            publicport = int(client_session['serveraddr']['publicport'])
        else:
            publicport = \
                client_session['localaddr'][1] or \
                client_session['addr'][1]

        output = bytearray(recv_data[0:12])
        output += utils.get_bytes_from_ip_str(client_session['addr'][0])
        output += utils.get_bytes_from_short(publicport, True)

        # Unknown, always seems to be \x42\x00
        output += bytearray([0x42, 0x00])
        output[7] = 0x05  # NN_CONNECT
        nn.write_queue.put((output, client_id_session['addr'], socket))

        logger.log(logging.DEBUG,
                   "Sent connection request to %s:%d...",
                   *client_id_session['addr'])
        logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(output))

        # --- Send to other client
        # Get server info
        serveraddr = nn.get_server_addr(gameid, session_id, client_id)
        client_id_session['serveraddr'] = serveraddr
        logger.log(logging.DEBUG,
                   "Found server 2 from local ip/port: %s from %d",
                   serveraddr, session_id)

        # Get public port
        if client_id_session['serveraddr'] is not None:
            publicport = int(client_id_session['serveraddr']['publicport'])
        else:
            publicport = \
                client_id_session['localaddr'][1] or \
                client_id_session['addr'][1]

        output = bytearray(recv_data[0:12])
        output += utils.get_bytes_from_ip_str(client_id_session['addr'][0])
        output += utils.get_bytes_from_short(publicport, True)

        # Unknown, always seems to be \x42\x00
        output += bytearray([0x42, 0x00])
        output[7] = 0x05  # NN_CONNECT
        nn.write_queue.put((output, client_session['addr'], socket))

        logger.log(logging.DEBUG,
                   "Sent connection request to %s:%d...",
                   *client_session['addr'])
        logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(output))


def handle_natneg_initack(nn, recv_data, addr, socket):
    """Command: 0x01 - NN_INITACK.

    Reply by the server for record NN_INIT (0x00).

    Example:
    fd fc 1e 66 6a b2 03 01 3d f1 00 71 00 00 ff ff
    6d 16 b5 7d ea

    Description:
    fd fc 1e 66 6a b2 - NATNEG magic
    03                - NATNEG version
    01                - NATNEG record type
    3d f1 00 71       - Session id
    00                - Port type (between 0x00 and 0x03)
    00                - Client index (0x00 - Client,
                                      0x01 - Host)
    ff                - Use game port (-1)? Dummy value?
    ff 6d 16 b5       - Local IP? Dummy value?
    7d ea             - Local port? Hex speak of "Idea"? Dummy value?
    """
    logger.log(logging.WARNING,
               "Received server record type command NN_INITACK (0x01)"
               " from %s:%d...", *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(recv_data))


def handle_natneg_erttest(nn, recv_data, addr, socket):
    """Command: 0x02 - NN_ERTTEST.

    Reply by the server for record NN_NATIFY_REQUEST (0x0C).

    Example:
    fd fc 1e 66 6a b2 03 02 00 00 03 09 02 00 00 00
    00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    00 00 00 00 00 00 00 00 00

    Description:
    fd fc 1e 66 6a b2 - NATNEG magic
    03                - NATNEG version
    02                - NATNEG record type
    00 00 03 09       - Session id
    02                - Port type (between 0x00 and 0x03)
                      - 60 bytes padding?
    00                - Client index (0x00 - Client,
                                      0x01 - Host)
    00                - NATNEG result?
    00 00 00 00       - NAT type?
    00 00 00 00       - NAT mapping scheme?
    00 (x50)          - Game name?
    """
    logger.log(logging.WARNING,
               "Received server record type command NN_ERTTEST (0x02)"
               " from %s:%d...", *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(recv_data))


def handle_natneg_ertack(nn, recv_data, addr, socket):
    """Command: 0x03 - NN_ERTACK.

    Reply by the client for record NN_ERTTEST (0x02).
    Only the record type is changed.

    Example:
    fd fc 1e 66 6a b2 03 03 00 00 03 09 02 00 00 00
    00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    00 00 00 00 00 00 00 00 00

    Description:
    fd fc 1e 66 6a b2 - NATNEG magic
    03                - NATNEG version
    03                - NATNEG record type
    00 00 03 09       - Session id
    02                - Port type (between 0x00 and 0x03)
                      - 60 bytes padding?
    00                - Client index (0x00 - Client,
                                      0x01 - Host)
    00                - NATNEG result?
    00 00 00 00       - NAT type?
    00 00 00 00       - NAT mapping scheme?
    00 (x50)          - Game name?
    """
    logger.log(logging.INFO, "Received ERT acknowledgement from %s:%d", *addr)


def handle_natneg_stateupdate(nn, recv_data, addr, socket):
    """Command: 0x04 - NN_STATEUPDATE.

    TODO

    Example:
    TODO

    Description:
    TODO
    """
    logger.log(logging.WARNING,
               "Received unimplemented command NN_STATEUPDATE (0x04)"
               " from %s:%d...", *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(output))


def handle_natneg_connect(nn, recv_data, addr, socket):
    """Command: 0x05 - NN_CONNECT.

    Reply by the server for record NN_INIT (0x00).

    Example:
    fd fc 1e 66 6a b2 03 05 3d f1 00 71 18 ab ed 7a
    da 00 42 00

    Description:
    fd fc 1e 66 6a b2 - NATNEG magic
    03                - NATNEG version
    05                - NATNEG record type
    3d f1 00 71       - Session id
    18 ab ed 7a       - Remote IP
    da 00             - Remote port
    42                - Got remote data
    00                - Finished
    """
    logger.log(logging.WARNING,
               "Received server record type command NN_CONNECT (0x05)"
               " from %s:%d...", *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(recv_data))


def handle_natneg_connect_ack(nn, recv_data, addr, socket):
    """Command: 0x06 - NN_CONNECT_ACK.

    Reply by the client for record NN_CONNECT (0x05).

    Example:
    fd fc 1e 66 6a b2 03 06 3d f1 00 71 90 00 cd a0
    80 00 00 00 90

    Description:
    fd fc 1e 66 6a b2 - NATNEG magic
    03                - NATNEG version
    06                - NATNEG record type
    3d f1 00 71       - Session id
    90                - Port type (0x00, 0x80 or 0x90)
    00                - Client index (0x00 - Client,
                                      0x01 - Host)
    cd                - Use game port?
    a0 80 00 00       - Local IP?
    00 90             - Local port?
    """
    client_id = "%02x" % ord(recv_data[13])
    session_id = utils.get_int(recv_data, 8)
    logger.log(logging.DEBUG,
               "Received connected command from %s:%d...",
               *addr)

    if session_id in nn.session_list and \
       client_id in nn.session_list[session_id]:
        nn.session_list[session_id][client_id]['connected'] = True


def handle_natneg_connect_ping(nn, recv_data, addr, socket):
    """Command: 0x07 - NN_CONNECT_PING.

    Looks like NN_CONNECT but between clients.
    The server shouldn't be involved.

    Example:
    fd fc 1e 66 6a b2 03 07 ?? ?? ?? ?? ?? ?? ?? ??
    ?? ?? ?? ??

    Description:
    fd fc 1e 66 6a b2 - NATNEG magic
    03                - NATNEG version
    07                - NATNEG record type
    ?? ?? ?? ??       - Session id
    ?? ?? ?? ??       - Remote IP
    ?? ??             - Remote port
    ??                - Sequence counter (0 or 1)
    ??                - Error
    """
    logger.log(logging.WARNING,
               "Received unimplemented command NN_CONNECT_PING (0x07)"
               " from %s:%d...", *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(recv_data))


def handle_natneg_backup_test(nn, recv_data, addr, socket):
    """Command: 0x08 - NN_BACKUP_TEST.

    Send by the client.

    Example:
    TODO

    Description:
    Untested
    """
    logger.log(logging.DEBUG, "Received backup command from %s:%d...", *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(recv_data))

    # Backup response
    output = bytearray(recv_data)
    output[7] = 0x09  # NN_BACKUP_ACK
    nn.write_queue.put((output, addr, socket))


def handle_natneg_backup_ack(nn, recv_data, addr, socket):
    """Command: 0x09 - NN_BACKUP_ACK.

    Reply by the server for record NN_BACKUP_TEST (0x08).
    Only the record type is changed.

    Example:
    TODO

    Description:
    TODO
    """
    logger.log(logging.WARNING,
               "Received server record type command NN_BACKUP_ACK (0x09)"
               " from %s:%d...", *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(output))


def handle_natneg_address_check(nn, recv_data, addr, socket):
    """Command: 0x0A - NN_ADDRESS_CHECK.

    Send by the client during connection test.

    Example:
    fd fc 1e 66 6a b2 03 0a 00 00 00 00 01 00 00 00
    00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    00 00 00 00 00 00 00 00 00

    Description:
    fd fc 1e 66 6a b2 - NATNEG magic
    03                - NATNEG version
    0a                - NATNEG record type
    00 00 00 00       - Session id
    01                - Port type (between 0x00 and 0x03)
                      - 60 bytes padding?
    00                - Client index (0x00 - Client,
                                      0x01 - Host)
    00                - NATNEG result?
    00 00 00 00       - NAT type?
    00 00 00 00       - NAT mapping scheme?
    00 (x50)          - Game name?
    """
    client_id = "%02x" % ord(recv_data[13])
    logger.log(logging.DEBUG,
               "Received address check command from %s:%d...",
               *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(recv_data))

    output = bytearray(recv_data[0:15])
    output += utils.get_bytes_from_ip_str(addr[0])
    output += utils.get_bytes_from_short(addr[1], True)
    output += bytearray(recv_data[len(output):])

    output[7] = 0x0b  # NN_ADDRESS_REPLY
    nn.write_queue.put((output, addr, socket))

    logger.log(logging.DEBUG, "Sent address check response to %s:%d...", *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(output))


def handle_natneg_address_reply(nn, recv_data, addr, socket):
    """Command: 0x0B - NN_ADDRESS_REPLY.

    Reply by the server for record NN_ADDRESS_CHECK (0x0A).

    Example:
    fd fc 1e 66 6a b2 03 0b 00 00 00 03 01 00 00 25
    c9 e2 8a 91 e4

    Description:
    fd fc 1e 66 6a b2 - NATNEG magic
    03                - NATNEG version
    0b                - NATNEG record type
    00 00 00 03       - Session id
    01                - Port type (between 0x00 and 0x03)
    00                - Client index (0x00 - Client,
                                      0x01 - Host)
    00                - Use game port
    25 c9 e2 8a       - Public IP
    91 e4             - Public port
    """
    logger.log(logging.WARNING,
               "Received server record type command NN_ADDRESS_REPLY (0x0B)"
               " from %s:%d...", *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(output))


def handle_natneg_natify_request(nn, recv_data, addr, socket):
    """Command: 0x0C - NN_NATIFY_REQUEST.

    Send by the client during connection test.

    Example:
    fd fc 1e 66 6a b2 03 0c 00 00 03 09 01 00 00 00
    00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    00 00 00 00 00 00 00 00 00

    Description:
    fd fc 1e 66 6a b2 - NATNEG magic
    03                - NATNEG version
    0c                - NATNEG record type
    00 00 03 09       - Session id
    01                - Port type (between 0x00 and 0x03)
                      - 60 bytes padding?
    00                - Client index (0x00 - Client,
                                      0x01 - Host)
    00                - NATNEG result?
    00 00 00 00       - NAT type?
    00 00 00 00       - NAT mapping scheme?
    00 (x50)          - Game name?
    """
    port_type = "%02x" % ord(recv_data[12])
    logger.log(logging.DEBUG, "Received natify command from %s:%d...", *addr)

    output = bytearray(recv_data)
    output[7] = 0x02  # ERT Test
    nn.write_queue.put((output, addr, socket))

    logger.log(logging.DEBUG, "Sent natify response to %s:%d...", *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(output))


def handle_natneg_report(nn, recv_data, addr, socket):
    """Command: 0x0D - NN_REPORT.

    Send by the client.

    Example:
    fd fc 1e 66 6a b2 03 0d 3d f1 00 71 00 00 01 00
    00 00 06 00 00 00 00 6d 61 72 69 6f 6b 61 72 74
    77 69 69 00 00 00 00 00 00 00 00 00 00 00 00 00
    00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    00 00 00 00 00 00 00 00 00

    Description:
    fd fc 1e 66 6a b2 - NATNEG magic
    03                - NATNEG version
    0d                - NATNEG record type
    3d f1 00 71       - Session id
    00                - Port type (0x00, 0x80 or 0x90)
    00                - Client index (0x00 - Client,
                                      0x01 - Host)
    01                - NATNEG result (0x00 - Error,
                                       0x01 - Success)
    00 00 00 06       - NAT type (0x00 - No NAT,
                                  0x01 - Firewall only,
                                  0x02 - Full cone,
                                  0x03 - Restricted cone,
                                  0x04 - Port restricted cone,
                                  0x05 - Symmetric,
                                  0x06 - Unknown)
    00 00 00 00       - NAT mapping scheme (0x00 - Unknown,
                                            0x01 - Private same as public,
                                            0x02 - Consistent port,
                                            0x03 - Incremental,
                                            0x04 - Mixed)
    GAME_NAME 00      - Game name (GAME_NAME is 49 bytes length)
    """
    logger.log(logging.DEBUG, "Received report command from %s:%d...", *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(recv_data))

    # Report response
    output = bytearray(recv_data[:21])
    output[7] = 0x0e  # Report response
    output[14] = 0  # Clear byte to match real server's response
    nn.write_queue.put((output, addr, socket))


def handle_natneg_report_ack(nn, recv_data, addr, socket):
    """Command: 0x0E - NN_REPORT_ACK.

    Reply by the server for record NN_REPORT (0x0D).

    Example:
    fd fc 1e 66 6a b2 03 0e 3d f1 00 71 00 00 00 00
    00 00 06 00 00

    Description:
    fd fc 1e 66 6a b2 - NATNEG magic
    03                - NATNEG version
    0e                - NATNEG record type
    3d f1 00 71       - Session id
    00                - Port type (0x00, 0x80 or 0x90)
    00                - Client index (0x00 - Client,
                                      0x01 - Host)
    00                - NATNEG result (0x00 - Error,
                                       0x01 - Success)
    00 00 00 06       - NAT type (0x00 - No NAT,
                                  0x01 - Firewall only,
                                  0x02 - Full cone,
                                  0x03 - Restricted cone,
                                  0x04 - Port restricted cone,
                                  0x05 - Symmetric,
                                  0x06 - Unknown)
    """
    logger.log(logging.WARNING,
               "Received server record type command NN_REPORT_ACK (0x0E)"
               " from %s:%d...", *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(recv_data))


def handle_natneg_preinit(nn, recv_data, addr, socket):
    """Command: 0x0F - NN_PREINIT.

    Natneg v4 command thanks to Pipian.
    Only seems to be used in very few DS games, namely,
    Pokemon Black/White/Black 2/White 2.

    Example:
    fd fc 1e 66 6a b2 04 0f b5 e0 95 2a 00 24 38 b2
    b3 5e

    Description:
    fd fc 1e 66 6a b2 - NATNEG magic
    04                - NATNEG version
    0f                - NATNEG record type
    b5 e0 95 2a       - Session id
    00                - Client index (0x00 - Client,
                                      0x01 - Host)
    24                - State (0x00 - Waiting for client,
                               0x01 - Waiting for matchup,
                               0x02 - Ready)
    38 b2 b3 5e       - Other client's session id
    """
    logger.log(logging.DEBUG, "Received pre-init command from %s:%d...", *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(recv_data))

    session = utils.get_int(recv_data[-4:], 0)

    # Report response
    output = bytearray(recv_data[:-4]) + bytearray([0, 0, 0, 0])
    output[7] = 0x10  # Pre-init response

    if not session:
        # What's the correct behavior when session == 0?
        output[13] = 2
    elif session in nn.natneg_preinit_session:
        # Should this be sent to both clients or just the one that
        # connected most recently?
        # I can't tell from a one sided packet capture of Pokemon.
        # For the time being, send to both clients just in case.
        output[13] = 2
        nn.write_queue.put((output, nn.natneg_preinit_session[session],
                            socket))

        output[12] = (1, 0)[output[12]]  # Swap the index
        del nn.natneg_preinit_session[session]
    else:
        output[13] = 0
        nn.natneg_preinit_session[session] = addr

    nn.write_queue.put((output, addr, socket))


def handle_natneg_preinit_ack(nn, recv_data, addr, socket):
    """Command: 0x10 - NN_PREINIT_ACK.

    Reply by the server for record NN_PREINIT (0x0F).

    Example:
    fd fc 1e 66 6a b2 04 10 b5 e0 95 2a 00 00 00 00
    00 00

    After receiving other client's PREINIT:
    fd fc 1e 66 6a b2 04 10 b5 e0 95 2a 01 02 00 00
    00 00

    Description:
    fd fc 1e 66 6a b2 - NATNEG magic
    04                - NATNEG version
    10                - NATNEG record type
    b5 e0 95 2a       - Session id
    00                - Client index (0x00 - Client,
                                      0x01 - Host)
    00                - State (0x00 - Waiting for client,
                               0x01 - Waiting for matchup,
                               0x02 - Ready)
    00 00 00 00       - Other client's session id (or empty)
    """
    logger.log(logging.WARNING,
               "Received server record type command NN_PREINIT_ACK (0x10)"
               " from %s:%d...", *addr)
    logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(recv_data))


class GameSpyNatNegUDPServerHandler(SocketServer.BaseRequestHandler):
    """GameSpy NAT Negotiation handler."""

    nn_magics = bytearray([0xfd, 0xfc, 0x1e, 0x66, 0x6a, 0xb2])
    nn_commands = {
        '\x00': handle_natneg_init,
        '\x01': handle_natneg_initack,
        '\x02': handle_natneg_erttest,
        '\x03': handle_natneg_ertack,
        '\x04': handle_natneg_stateupdate,
        '\x05': handle_natneg_connect,
        '\x06': handle_natneg_connect_ack,
        '\x07': handle_natneg_connect_ping,
        '\x08': handle_natneg_backup_test,
        '\x09': handle_natneg_backup_ack,
        '\x0A': handle_natneg_address_check,
        '\x0B': handle_natneg_address_reply,
        '\x0C': handle_natneg_natify_request,
        '\x0D': handle_natneg_report,
        '\x0E': handle_natneg_report_ack,
        '\x0F': handle_natneg_preinit,
        '\x10': handle_natneg_preinit_ack
    }

    def handle(self):
        """Handle NAT Negotiation request."""
        recv_data, socket = self.request
        addr = self.client_address

        logger.log(logging.DEBUG, "Connection from %s:%d...", *addr)
        logger.log(logging.DEBUG, "%s", utils.pretty_print_hex(recv_data))

        # Make sure it's a legal packet
        if not recv_data.startswith(self.nn_magics):
            logger.log(logging.ERROR, "Aborted due to illegal packet!")
            return

        # Handle commands
        try:
            command = self.nn_commands.get(recv_data[7], handle_natneg)
            command(self.server, recv_data, addr, socket)
        except:
            logger.log(logging.ERROR, "Failed to handle command!")
            logger.log(logging.ERROR, "%s", traceback.format_exc())


class GameSpyNatNegUDPServer(SocketServer.UDPServer):
    """GameSpy NAT Negotiation server."""

    def __init__(self,
                 server_address=dwc_config.get_ip_port('GameSpyNatNegServer'),
                 RequestHandlerClass=GameSpyNatNegUDPServerHandler,
                 bind_and_activate=True):
        SocketServer.UDPServer.__init__(self,
                                        server_address,
                                        RequestHandlerClass,
                                        bind_and_activate)
        self.session_list = {}
        self.natneg_preinit_session = {}
        self.secret_key_list = gs_utils.generate_secret_keys("gslist.cfg")

        self.server_manager = GameSpyServerDatabase(
            address=dwc_config.get_ip_port('GameSpyManager'),
            authkey=""
        )
        self.server_manager.connect()

        self.write_queue = Queue.Queue()
        threading.Thread(target=self.write_queue_worker).start()

    def write_queue_send(self, data, address, socket):
        time.sleep(0.05)
        socket.sendto(data, address)

    def write_queue_worker(self):
        while True:
            data, address, socket = self.write_queue.get()
            threading.Thread(target=self.write_queue_send,
                             args=(data, address, socket)).start()
            self.write_queue.task_done()

    def get_server_info(self, gameid, session_id, client_id):
        """Get server by public IP."""
        server = None
        ip_str = self.session_list[session_id][client_id]['addr'][0]
        servers = self.server_manager.get_natneg_server(session_id) \
                                     ._getvalue()
        
        if servers is None:
            return None
            
        for console in [False, True]:
            if server is not None:
                break
            ip = str(utils.get_ip_from_str(ip_str, console))
            server = next((s for s in servers if s['publicip'] == ip), None)

        return server

    def get_server_info_alt(self, gameid, session_id, client_id):
        """Get server by local address."""
        server = None
        ip_str = self.session_list[session_id][client_id]['addr'][0]

        for console in [False, True]:
            if server is not None:
                break
            ip = str(utils.get_ip_from_str(ip_str, console))
            server = self.server_manager.find_server_by_local_address(
                ip,
                self.session_list[session_id][client_id]['localaddr'],
                self.session_list[session_id][client_id]['gameid']
            )._getvalue()

        return server

    def get_server_addr(self, gameid, session_id, client_id):
        """Get server address."""
        return \
            self.get_server_info(gameid, session_id, client_id) or \
            self.get_server_info_alt(gameid, session_id, client_id)


class GameSpyNatNegServer(object):
    def start(self):
        server = GameSpyNatNegUDPServer()
        logger.log(logging.INFO, "Server is now listening on %s:%d...",
                   *server.server_address)
        server.serve_forever()


if __name__ == "__main__":
    natneg_server = GameSpyNatNegServer()
    natneg_server.start()
