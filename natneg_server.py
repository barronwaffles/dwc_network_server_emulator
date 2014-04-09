# Server emulator for *.available.gs.nintendowifi.net and *.master.gs.nintendowifi.net
# Query and Reporting: http://docs.poweredbygamespy.com/wiki/Query_and_Reporting_Overview

import socket
import struct
import gamespy.gs_utility as gs_utils
import other.utils as utils
from multiprocessing.managers import BaseManager

session_list = {}

secret_key_list = gs_utils.generate_secret_keys("gslist.cfg")

# Start QR server
address = ('0.0.0.0', 27901)  # accessible to outside connections (use this if you don't know what you're doing)

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(address)

utils.print_log("Server is now listening on %s:%s..." % (address[0], address[1]))

while 1:
    recv_data, addr = s.recvfrom(2048)

    print "Connection from %s:%d..." % (addr[0], addr[1])

    # Make sure it's a legal packet
    if recv_data[0:6] != bytearray([0xfd, 0xfc, 0x1e, 0x66, 0x6a, 0xb2]):
        continue

    session_id = struct.unpack("<I", recv_data[8:12])[0]
    session_id_raw = recv_data[8:12]

    # Handle commands
    if recv_data[7] == '\x00':
        utils.print_log("Received initialization from %s:%s..." % (addr[0], addr[1]))

        gameid = utils.get_string(recv_data, 0x16)
        client_id = "%02x" % ord(recv_data[13])

        if gameid not in session_list:
            session_list[gameid] = {}
        if session_id not in session_list[gameid]:
            session_list[gameid][session_id] = {}
        if client_id not in session_list[gameid][session_id]:
            session_list[gameid][session_id][client_id] = { 'connected': False, 'addr': '' }

        session_list[gameid][session_id][client_id]['addr'] = addr
        clients = len(session_list[gameid][session_id])
        #if client_id in session_list[gameid][session_id]:
        #    clients -= 1

        if clients > 0:
            # Someone else is waiting to connect, send message
            for client in session_list[gameid][session_id]:
                if session_list[gameid][session_id][client]['connected'] == True or client == client_id:
                    continue

                output = bytearray(recv_data[0:12])
                if client == client_id:
                    output += bytearray(recv_data[15:15+4+2]) # IP Address and port
                else:
                    output += bytearray([int(x) for x in addr[0].split('.')])
                    output += utils.get_bytes_from_short_be(addr[1])

                output += bytearray([0x42, 0x00]) # Unknown, always seems to be \x42\x00
                output[7] = 0x05
                s.sendto(output, (session_list[gameid][session_id][client]['addr']))

                print "Sent connection request to %s:%d..." % (session_list[gameid][session_id][client]['addr'][0], session_list[gameid][session_id][client]['addr'][1])
                utils.print_hex(output)
                print ""
                #session_list[gameid][session_id][client_id]['connected'] = True

        output = bytearray(recv_data[0:14])
        output += bytearray([0xff, 0xff, 0x6d, 0x16, 0xb5, 0x7d, 0xea ]) # Checked with Tetris DS, Mario Kart DS, and Metroid Prime Hunters, and this seems to be the standard response to 0x00
        output[7] = 0x01 # Initialization response
        s.sendto(output, addr)

    elif recv_data[7] == '\x06': # Was able to connect
        client_id = "%02x" % ord(recv_data[13])
        utils.print_log("Received connected command from %s:%s..." % (addr[0], addr[1]))

        if gameid not in session_list:
            pass
        if session_id not in session_list[gameid]:
            pass
        if client_id not in session_list[gameid][session_id]:
            pass

        #session_list[gameid][session_id][client_id]['connected'] = True

    elif recv_data[7] == '\x0d':
        client_id = "%02x" % ord(recv_data[13])
        utils.print_log("Received report command from %s:%s..." % (addr[0], addr[1]))

        utils.print_hex(bytearray(recv_data))

        output[7] = 0x0e # Report response
        s.sendto(output, addr)

    else: # Was able to connect
        utils.print_log("Received unknown command %02x from %s:%s..." % (ord(recv_data[7]), addr[0], addr[1]))








