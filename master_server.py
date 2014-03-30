# Server emulator for *.available.gs.nintendowifi.net and *.master.gs.nintendowifi.net
import socket
import time
import other.utils as utils

def get_game_id(data):
	game_id = data[5: -1]
	return game_id

#address = ('127.0.0.1', 27900) # accessible to only the local computer
address = ('0.0.0.0', 27900) # accessible to outside connections (use this if you don't know what you're doing)

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(address)

utils.print_log("Server is now listening on %s:%s..." % (address[0], address[1]))

while(1):
	recv_data, addr = s.recvfrom(2048)
	
	if [ord(x) for x in recv_data[0:5]] == [0x09, 0x00, 0x00, 0x00, 0x00]:
		utils.print_log("Received request for '%s' from %s:%s... %s" % (get_game_id(recv_data), addr[0], addr[1], [elem.encode("hex") for elem in recv_data]))
	
		# I have not seen any games that use anything other than \x09\x00\x00\x00\x00 + null terminated game id,
		# but just in case there are others out there, copy the data received from the game as the response.
		s.sendto(bytearray([0xfe, 0xfd, recv_data[0], recv_data[1], recv_data[2], recv_data[3], recv_data[4]]), addr)
	else:
		utils.print_log("Unknown request from %s:%s: %s" % (addr[0], addr[1], [elem.encode("hex") for elem in recv_data]))

