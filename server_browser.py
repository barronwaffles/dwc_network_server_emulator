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
    client, address = s.accept()

    utils.print_log("Received connection from %s:%s" % (address[0], address[1]))
    
    while 1:
        accept_connection = True
        data = client.recv(size).rstrip()
        utils.print_log("RESPONSE: %s" % data)
