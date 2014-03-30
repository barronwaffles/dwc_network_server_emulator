# Server emulator for *.available.gs.nintendowifi.net and *.master.gs.nintendowifi.net
import socket
import gamespy.gs_utility as gs_utils
import other.utils as utils

def get_game_id(data):
    game_id = data[5: -1]
    return game_id

#address = ('127.0.0.1', 27900) # accessible to only the local computer
address = ('0.0.0.0', 27900)  # accessible to outside connections (use this if you don't know what you're doing)

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(address)

utils.print_log("Server is now listening on %s:%s..." % (address[0], address[1]))

while 1:
    recv_data, addr = s.recvfrom(2048)

    # Tetris DS overlay 10 @ 02144184 - Handle responses back to server
    # Tetris DS overlay 10 @ 02144184 - Handle responses back to server
    #
    # After some more packet inspection, it seems the format goes something like this:
    # - All server messages seem to always start with \xfe\xfe.
    # - The first byte from the client (or third byte from the server) is a command.
    # - Bytes 2 - 5 from the client is some kind of ID. This will have to be inspected later. I believe it's a
    # session-like ID because the number changes between connections. Copying the client's ID might be enough.
    #
    # The above was as guessed.
    # The code in Tetris DS (overlay 10) @ 0216E974 handles the network command creation.
    # R1 contains the command to be sent to the server.
    # R2 contains a pointer to some unknown integer that gets written after the command.
    #
    # - Commands
    #   Commands range from 0x00 to 0x09 (for client only at least?) (Tetris DS overlay 10 @ 0216DDCC)
    #
    #   CLIENT:
    #       0x01 - Response (Tetris DS overlay 10 @ 216DCA4)
    #           Sends back base64 of RC4 encrypted string that was gotten from the server's 0x01. Server doesn't respond?
    #
    #       0x03 - Send client state? (Tetris DS overlay 10 @ 216DA30)
    #           Data sent:
    #           1) Loop for each localip available on the system, write as localip%d\x00(local ip)
    #           2) localport\x00(local port)
    #           3) natneg (either 0 or 1)
    #           4) ONLY IF STATE CHANGED: statechanged\x00(state) (Possible values: 0, 1, 2, 3)
    #           5) gamename\x00(game name)
    #           6) ONLY IF PUBLIC IP AND PORT ARE AVAILABLE: publicip\x00(public ip)
    #           7) ONLY IF PUBLIC IP AND PORT ARE AVAILABLE: publicport\x00(public port)
    #
    #           if statechanged != 2:
    #               Write various other data described here: http://docs.poweredbygamespy.com/wiki/Query_and_Reporting_Implementation
    #
    #       0x07 - Unknown, related to server's 0x06 (returns value sent from server)
    #
    #       0x08 - Keep alive? Sent after 0x03
    #
    #       0x09 - Availability check
    #
    #   SERVER:
    #       0x01 - Unknown
    #           Data sent:
    #           8 random ASCII characters (?) followed by the public IP and port of the client as a hex string
    #
    #       0x06 - Unknown
    #           First 4 bytes is some kind of id? I believe it's a unique identifier for the data being sent,
    #           seeing how the server can send the same IP information many times in a row. If the IP information has
    #           already been parsed then it doesn't waste time handling it.
    #
    #           After that is a "SBCM" section which is 0x14 bytes in total.
    #           SBCM information gets parsed at 2141A0C in Tetris DS overlay 10.
    #           Seems to contain IP address information.
    #
    #           The SBCM seems to contain a little information that must be parsed before.
    #           After the SBCM:
    #               \x03\x00\x00\x00 - Always the same?
    #               \x01 - Found player?
    #               \x04 - Unknown
    #               (2 bytes) - Unknown. Port?
    #               (4 bytes) - Player's IP
    #               (4 bytes) - Unknown. Some other IP? Remote server IP?
    #               \x00\x00\x00\x00 - Unknown but seems to get checked
    #
    #           Another SBCM, after a player has been found and attempting to start a game:
    #               \x03\x00\x00\x00 - Always the same?
    #               \x05 - Connecting to player?
    #               \x00 - Unknown
    #               (2 bytes) - Unknown. Port? Same as before.
    #               (4 bytes) - Player's IP
    #               (4 bytes) - Unknown. Some other IP? Remote server IP?
    #
    #       0x0a - Response to 0x01
    #           Gets sent after receiving 0x01 from the client. So, server 0x01 -> client 0x01 -> server 0x0a.
    #           Has no other data besides the client ID.
    #
    #  - \xfd\xfc commands get passed directly between the other player(s)?
    #

    if recv_data[0] == '\x01':
        utils.print_log("Response received from %s:%s... %s" % (addr[0], addr[1], recv_data[5:]))
    elif recv_data[0] == '\x03':
        utils.print_log("Received client state from %s:%s... %s" % (addr[0], addr[1], recv_data[5:]))
    elif recv_data[0] == '\x07':
        utils.print_log("Received unknown data from %s:%s... %s" % (addr[0], addr[1], recv_data[5:]))
    elif recv_data[0] == '\x08':
        utils.print_log("Received keep alive from %s:%s..." % (addr[0], addr[1]))
    elif recv_data[0] == '\x09':
        # Availability check only sent to *.available.gs.nintendowifi.net
        utils.print_log("Received availability request for '%s' from %s:%s... %s" % (
            get_game_id(recv_data), addr[0], addr[1], [elem.encode("hex") for elem in recv_data]))

        s.sendto(bytearray([0xfe, 0xfd, recv_data[0], recv_data[1], recv_data[2], recv_data[3], recv_data[4]]), addr)
    else:
        utils.print_log(
            "Unknown request from %s:%s: %s" % (addr[0], addr[1], [elem.encode("hex") for elem in recv_data]))
