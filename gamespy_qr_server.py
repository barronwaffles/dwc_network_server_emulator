# Server emulator for *.available.gs.nintendowifi.net and *.master.gs.nintendowifi.net
# Query and Reporting:
# http://docs.poweredbygamespy.com/wiki/Query_and_Reporting_Overview

import logging
import socket
import struct
import threading
import time
import ctypes

from multiprocessing.managers import BaseManager

import gamespy.gs_utility as gs_utils
import gamespy.gs_database as gs_database
import other.utils as utils
from gamespy_server_browser_server import GameSpyServerBrowserServer

# Logger settings
logger_output_to_console = True
logger_output_to_file = True
logger_name = "GameSpyQRServer"
logger_filename = "gamespy_qr_server.log"
logger = utils.create_logger(
    logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)


class GameSpyServerDatabase(BaseManager):
    pass


class GameSpyQRServer(object):

    class Session(object):

        def __init__(self, address):
            self.session = ""
            self.challenge = ""
            self.secretkey = ""  # Parse gslist.cfg later
            self.sent_challenge = False
            self.address = address
            self.console = 0
            self.playerid = 0

            self.gamename = ""
            self.keepalive = -1

    def __init__(self):
        self.sessions = {}

        # Generate a dictionary "secret_key_list" containing the secret game keys associated with their game IDs.
        # The dictionary key will be the game's ID, and the value will be the
        # secret key.
        self.secret_key_list = gs_utils.generate_secret_keys("gslist.cfg")
        #self.log(logging.DEBUG, address, "Generated list of secret game keys...")

        self.db = gs_database.GamespyDatabase()

        GameSpyServerDatabase.register("update_server_list")
        GameSpyServerDatabase.register("delete_server")

    def log(self, level, address, message, *args):
        logger.log(level, "%s%s", ("[%s:%d ]"%(address[0], address[1])) if address else "", message % args)

    def start(self):
        manager_address = ("127.0.0.1", 27500)
        manager_password = ""

        self.server_manager = GameSpyServerDatabase(address = manager_address, authkey= manager_password)
        self.server_manager.connect()

        # Start QR server
        address = ('0.0.0.0', 27900)  # accessible to outside connections (use this if you don't know what you're doing)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(address)

        logger.info("Server is now listening on %s:%s...", address[0], address[1])

        # Dependencies! I don't really like this solution but it's easier than trying to manage it another way.
        server_browser_server = GameSpyServerBrowserServer(self)
        server_browser_server_thread = threading.Thread(target=server_browser_server.start())
        server_browser_server_thread.start()

        threading.Timer(1, self.keepalive_check).start()

        self.wait_loop()

    def wait_loop(self):
        while 1:
            recv_data, address = self.socket.recvfrom(2048)

            # Tetris DS overlay 10 @ 02144184 - Handle responses back to server
            # Tetris DS overlay 10 @ 02144184 - Handle responses back to server
            #
            # After some more packet inspection, it seems the format goes something like this:
            # - All server messages seem to always start with \xfe\xfd.
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
            #           Sends back base64 of RC4 encrypted string that was gotten from the server's 0x01.
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
            #
            # Open source version of GameSpy found here: https://github.com/sfcspanky/Openspy-Core/tree/master/qr
            # Use as reference.

            if recv_data[0] != '\x09':
                # Don't add a session if the client is trying to check if the
                # game is available or not
                session_id = struct.unpack("<I", recv_data[1:5])[0]
                session_id_raw = recv_data[1:5]
                if session_id not in self.sessions:
                    # Found a new session, add to session list
                    self.sessions[session_id] = self.Session(address)
                    self.sessions[session_id].session = session_id
                    self.sessions[session_id].keepalive = int(time.time())

            # Handle commands
            if recv_data[0] == '\x00': # Query
                self.log(logging.DEBUG, address, "NOT IMPLEMENTED! Received query from %s:%s... %s", address[0], address[1], recv_data[5:])

            elif recv_data[0] == '\x01': # Challenge
                self.log(logging.DEBUG, address, "Received challenge from %s:%s... %s", address[0], address[1], recv_data[5:])

                # Prepare the challenge sent from the server to be compared
                challenge = gs_utils.prepare_rc4_base64(self.sessions[session_id].secretkey, self.sessions[session_id].challenge)

                # Compare challenge
                client_challenge = recv_data[5:-1]
                if client_challenge == challenge:
                    # Challenge succeeded

                    # Send message back to client saying it was accepted
                    packet = bytearray([0xfe, 0xfd, 0x0a]) # Send client registered command
                    packet.extend(session_id_raw) # Get the session ID
                    self.socket.sendto(packet, address)
                    self.log(logging.DEBUG, address, "Sent client registered to %s:%s...", address[0], address[1])
                else:
                    # Failed the challenge, request another during the next heartbeat
                    self.sessions[session_id].sent_challenge = False

            elif recv_data[0] == '\x02': # Echo
                self.log(logging.DEBUG, address, "NOT IMPLEMENTED! Received echo from %s:%s... %s", address[0], address[1], recv_data[5:])

            elif recv_data[0] == '\x03': # Heartbeat
                data = recv_data[5:]
                self.log(logging.DEBUG, address, "Received heartbeat from %s:%s... %s", address[0], address[1], data)

                # Parse information from heartbeat here
                d = data.rstrip('\0').split('\0')

                # It may be safe to ignore "unknown" keys because the proper key names get filled in later...
                k = {}
                for i in range(0, len(d), 2):
                    #self.log(logging.DEBUG, address, "%s = %s" % (d[i], d[i+1]))
                    k[d[i]] = d[i+1]

                if "gamename" in k:
                    self.sessions[session_id].secretkey = self.secret_key_list[k['gamename']]
                    #print "Got secret key %s for %s" % (self.sessions[session_id].secretkey, k['gamename'])

                if self.sessions[session_id].playerid == 0 and "dwc_pid" in k:
                    # Get the player's id and then query the profile to figure out what console they are on.
                    # The endianness of some server data depends on the endianness of the console, so we must be able
                    # to account for that.
                    self.sessions[session_id].playerid = int(k['dwc_pid'])
                    profile = self.db.get_profile_from_profileid(self.sessions[session_id].playerid)

                    if "console" in profile:
                        self.sessions[session_id].console = profile['console']


                if self.sessions[session_id].sent_challenge == False:
                    addr_hex =  ''.join("%02X" % int(x) for x in address[0].split('.'))
                    port_hex = "%04X" % int(address[1])
                    server_challenge = utils.generate_random_str(8) + addr_hex + port_hex

                    self.sessions[session_id].challenge = server_challenge

                    packet = bytearray([0xfe, 0xfd, 0x01]) # Send challenge command
                    packet.extend(session_id_raw) # Get the session ID
                    packet.extend(server_challenge)
                    packet.extend('\x00')

                    self.socket.sendto(packet, address)
                    self.log(logging.DEBUG, address, "Sent challenge to %s:%s...", address[0], address[1])

                    self.sessions[session_id].sent_challenge = True

                if 'publicip' in k and k['publicip'] == "0": #and k['dwc_hoststate'] == "2": # When dwc_hoststate == 2 then it doesn't send an IP, so calculate it ourselves
                    getint = [utils.get_int, utils.get_int_be][self.sessions[session_id].console != 0] # Use BE for Wii
                    k['publicip'] = str(ctypes.c_int32(getint(bytearray([int(x) for x in address[0].split('.')]), 0)).value)

                if "statechanged" in k:
                    if k['statechanged'] == "1": # Create server
                        #if k['publicport'] != "0" and k['publicip'] != "0":
                            # dwc_mtype controls what kind of server query we're looking for.
                            # dwc_mtype = 0 is used when looking for a matchmaking game.
                            # dwc_mtype = 1 is unknown.
                            # dwc_mtype = 2 is used when hosting a friends only game (possibly other uses too).
                            # dwc_mtype = 3 is used when looking for a friends only game (possibly other uses too).

                            # Some memory could be saved by clearing out any unwanted fields from k before sending.
                        self.server_manager.update_server_list(k['gamename'], session_id, k, self.sessions[session_id].console)._getvalue()

                        if session_id in self.sessions:
                            self.sessions[session_id].gamename = k['gamename']
                    elif k['statechanged'] == "2": # Close server
                        self.server_manager.delete_server(k['gamename'] , session_id)
                        self.sessions.pop(session_id, None)


            elif recv_data[0] == '\x04': # Add Error
                self.log(logging.WARNING, address, "NOT IMPLEMENTED! Received add error from %s:%s... %s", address[0], address[1], recv_data[5:])

            elif recv_data[0] == '\x05': # Echo Response
                self.log(logging.WARNING, address, "NOT IMPLEMENTED! Received echo response from %s:%s... %s", address[0], address[1], recv_data[5:])

            elif recv_data[0] == '\x06': # Client Message
                self.log(logging.WARNING, address, "NOT IMPLEMENTED! Received echo from %s:%s... %s", address[0], address[1], recv_data[5:])

            elif recv_data[0] == '\x07': # Client Message Ack
                #self.log(logging.WARNING, address, "NOT IMPLEMENTED! Received client message ack from %s:%s... %s", address[0], address[1], recv_data[5:])
                self.log(logging.DEBUG, address, "Received client message ack from %s:%s...", address[0], address[1])

            elif recv_data[0] == '\x08': # Keep Alive
                self.log(logging.DEBUG, address, "Received keep alive from %s:%s...", address[0], address[1])
                self.sessions[session_id].keepalive = int(time.time())

            elif recv_data[0] == '\x09': # Available
                # Availability check only sent to *.available.gs.nintendowifi.net
                self.log(logging.DEBUG, address, "Received availability request for '%s' from %s:%s...", recv_data[5: -1], address[0], address[1])
                self.socket.sendto(bytearray([0xfe, 0xfd, 0x09, 0x00, 0x00, 0x00, 0x00]), address)

            elif recv_data[0] == '\x0a': # Client Registered
                # Only sent to client, never received?
                self.log(logging.WARNING, address, "NOT IMPLEMENTED! Received client registered from %s:%s... %s", address[0], address[1], recv_data[5:])

            else:
                self.log(logging.ERROR, address, "Unknown request from %s:%s:", address[0], address[1])
                self.log(logging.DEBUG, address, utils.pretty_print_hex(recv_data))

    def keepalive_check(self):
        while 1:
            #self.log(logging.DEBUG, None, "Keep alive check on %d sessions" % (len(self.sessions)))

            pruned = []
            for session_id in self.sessions:
                now = int(time.time())
                delta = now - self.sessions[session_id].keepalive
                # Remove clients that haven't responded in 60 seconds
                timeout = 60

                if delta < 0 or delta >= timeout:
                    pruned.append(session_id)
                    self.server_manager.delete_server(self.sessions[session_id].gamename, self.sessions[session_id].session)
                    self.log(logging.DEBUG, None, "Keep alive check removed %s:%s for game %s", self.sessions[session_id].address[0], self.sessions[session_id].address[1], self.sessions[session_id].gamename)

            for session_id in pruned:
                del self.sessions[session_id]

            time.sleep(15.0)
