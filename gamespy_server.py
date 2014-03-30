# Server emulator for gpcm.gs.nintendowifi.net
import socket
import gamespy.gs_database as gs_database
import gamespy.gs_query as gs_query
import gamespy.gs_utility as gs_utils
import other.utils as utils

db = gs_database.GamespyDatabase()

address = ('0.0.0.0', 29900)
backlog = 10
size = 2048

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(address)
s.listen(backlog)

utils.print_log("Server is now listening on %s:%s..." % (address[0], address[1]))

while 1:
    client, address = s.accept()

    # TODO: Redo this part of the server so it'll handle multiple connections
    utils.print_log("Received connection from %s:%s" % (address[0], address[1]))

    # Send request for login information
    challenge = utils.generate_random_str(8)

    msg_d = []
    msg_d.append(('__cmd__', "lc"))
    msg_d.append(('__cmd_val__', "1"))
    msg_d.append(('challenge', challenge))
    msg_d.append(('id', "1"))
    msg = gs_query.create_gamespy_message(msg_d)

    utils.print_log("SENDING: '%s'..." % msg)
    client.send(msg)

    # Receive any command
    accept_connection = True
    while accept_connection:
        data = client.recv(size).rstrip()
        utils.print_log("RESPONSE: %s" % data)

        commands = gs_query.parse_gamespy_message(data)

        for data_parsed in commands:
            msg_d = []

            print data_parsed

            if data_parsed['__cmd__'] == "login":
                authtoken_parsed = gs_utils.parse_authtoken(data_parsed['authtoken'])
                print authtoken_parsed

                # get correct information
                userid = authtoken_parsed['userid']
                password = authtoken_parsed['passwd']
                uniquenick = utils.base32_encode(int(userid)) + authtoken_parsed['gsbrcd']
                email = uniquenick + "@nds"
                nick = uniquenick

                # Verify the client's response
                valid_response = gs_utils.generate_response(challenge, authtoken_parsed['challenge'], data_parsed['challenge'], data_parsed['authtoken'])
                if data_parsed['response'] != valid_response:
                    utils.print_log("ERROR: Got invalid response. Got %s, expected %s" % (data_parsed['response'], valid_response))

                proof = gs_utils.generate_proof(challenge, authtoken_parsed['challenge'], data_parsed['challenge'], data_parsed['authtoken'])

                valid_user = db.check_user_exists(userid)
                profileid = None
                if valid_user == False:
                    profileid = db.create_user(userid, password, email, uniquenick)
                else:
                    profileid = db.perform_login(userid, password)
                    if profileid == None:
                        # Handle case where the user is invalid
                        print "Invalid password"

                sesskey = db.create_session(profileid)

                msg_d.append(('__cmd__', "lc"))
                msg_d.append(('__cmd_val__', "2"))
                msg_d.append(('sesskey', sesskey))
                msg_d.append(('proof', proof))
                msg_d.append(('userid', userid))
                msg_d.append(('profileid', db.get_profileid_from_session_key(sesskey)))
                msg_d.append(('uniquenick', uniquenick))
                msg_d.append(('lt', gs_utils.base64_encode(utils.generate_random_str(16)))) # Some kind of token... don't know it gets used or generated, but it doesn't seem to have any negative effects if it's not properly generated.
                msg_d.append(('id', data_parsed['id']))
                msg = gs_query.create_gamespy_message(msg_d)

            elif data_parsed['__cmd__'] == "getprofile":
                msg_d = []

                profile = db.get_profile_from_session_key(data_parsed.append(('sesskey')))
                msg_d.append(('__cmd__', "pi"))
                msg_d.append(('__cmd_val__', ""))
                msg_d.append(('profileid', profile['profileid']))
                msg_d.append(('nick', profile['nick']))
                msg_d.append(('userid', profile['userid']))
                msg_d.append(('email', profile['email']))
                msg_d.append(('sig', utils.generate_random_hex_str(32)))
                msg_d.append(('uniquenick', profile['uniquenick']))
                msg_d.append(('pid', profile['pid']))
                msg_d.append(('lastname', profile['lastname']))
                msg_d.append(('lon', profile['lon']))
                msg_d.append(('lat', profile['lat']))
                msg_d.append(('loc', profile['loc']))
                msg_d.append(('id', data_parsed['id']))
                msg = gs_query.create_gamespy_message(msg_d)

            elif data_parsed['__cmd__'] == "updatepro":
                # Handle properly later
                # Assume that there will be other parameters besides lastname, so make it a loop or something along those lines later
                db.update_profile(data_parsed['sesskey'], [("lastname", data_parsed['lastname'])])

            elif data_parsed['__cmd__'] == "status":
                # Handle status update
                msg = ""

            elif data_parsed['__cmd__'] == "logout":
                print "Session %s has logged off" % (data_parsed['sesskey'])
                db.delete_session(data_parsed['sesskey'])
                accept_connection = False

            utils.print_log("SENDING: %s" % msg)
            client.send(msg)

    client.close()
