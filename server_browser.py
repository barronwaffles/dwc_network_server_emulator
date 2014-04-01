# I found an open source implemention of this exact server I'm trying to emulate here: https://github.com/sfcspanky/Openspy-Core/blob/master/serverbrowsing/
# Use as reference later.

# Tetris DS won't let you search for a match unless this server exists, so just create an empty server for now.

import socket
import gamespy.gs_utility as gs_utils
import other.utils as utils
import time

def get_game_id(data):
    game_id = data[5: -1]
    return game_id

#address = ('127.0.0.1', 28910) # accessible to only the local computer
address = ('0.0.0.0', 28910)  # accessible to outside connections (use this if you don't know what you're doing)
backlog = 10
size = 2048

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(address)
s.listen(backlog)

utils.print_log("Server is now listening on %s:%s..." % (address[0], address[1]))

while 1:
    client, addr = s.accept()

    utils.print_log("Received connection from %s:%s" % (address[0], address[1]))

    receive_data = True
    while receive_data:
        utils.print_log("Waiting for data...")

        accept_connection = True
        data = client.recv(size)

        # Didn't get a valid command.
        # Player disconnected?
        # Close connection
        if not data:
            break

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
        if data[2] == '\x00': # Server list request
            utils.print_log("Received server list request from %s:%s..." % (addr[0], addr[1]))

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

            print "%02x %02x %08x" % (list_version, encoding_version, game_version)
            print "%s" % query_game
            print "%s" % game_name
            print "%s" % challenge
            print "%s" % filter
            print "%s" % fields

            print "%08x" % options
            print "%d %08x" % (max_servers, source_ip)

            # TODO: Handle query

        elif data[2] == '\x02': # Send message request
            dest_addr = '.'.join(["%d" % x for x in addr[3:7]])
            dest_port = utils.get_short_be(addr, 7) # What's the pythonic way to do this? unpack?
            dest = (dest_addr, dest_port)

            # Wait for message data
            msg_data = client.recv(size)

            utils.print_log("Received send message request from %s:%s to %s:%d... %s" % (addr[0], addr[1], dest_addr, dest_port, msg_data))

            # Create new connection to send to other user over UDP.
            # Move this code somewhere else after testing has been finished.
            user_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            user_s.bind(dest)
            user_s.sendto(msg_data, dest)

            utils.print_log("Sent message to %s:%d... %s" % (dest_addr, dest_port, msg_data))

        elif data[2] == '\x03': # Keep alive reply
            utils.print_log("Received keep alive from %s:%s..." % (addr[0], addr[1]))

        else:
            utils.print_log("Received unknown command (%02x) from %s:%s... %s" % (ord(data[2]), addr[0], addr[1], data))
