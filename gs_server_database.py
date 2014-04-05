# Master server list server
#
# Basic idea:
# The server listing does not need to be persistent, and it must be easily searchable for any unknown parameters.
# So instead of using a SQL database, I've opted to create a server list database server which communicates between the
# server browser and the qr server. The server list database will be stored in dictionaries as to allow dynamic columns
# that can be easily searched. The main reason for this configuration is because it cannot be guaranteed what data
# a game's server will required. For example, in addition to the common fields such as publicip, numplayers, dwc_pid, etc,
# Lost Magic also uses fields such as LMname, LMsecN, LMrating, LMbtmode, and LMversion.
#
# It would be possible to create game-specific databases but this would be more of a hassle and less universal. It would
# also be possible pickle a dictionary containing all of the fields and store it in a SQL database instead, but that
# would require unpickling every server each time you want to match search queries which would cause overhead if there
# are a lot of running servers. One trade off here is that we'll be using more memory by storing each server as a
# dictionary in the memory instead of storing it in a SQL database.
#
# qr_server and server_browser both will act as clients to gs_server_database.
# qr_server will send an add and/or delete to add or remove servers from the server list.
# server_browser will send a request with the game name followed by optional search parameters to get a list of servers.

from multiprocessing.managers import BaseManager
from multiprocessing import freeze_support

server_list = {}

class TokenType:
    UNKNOWN = 0
    FIELD = 1
    STRING = 2
    NUMBER = 3
    TOKEN = 4

def get_token(filter, i):
    # Complex example from Dungeon Explorer: Warriors of Ancient Arts
    # dwc_mver = 3 and dwc_pid != 474890913 and maxplayers = 2 and numplayers < 2 and dwc_mtype = 0 and dwc_mresv != dwc_pid and (MatchType='english')
    #
    # Digging into a few DS games, and these hardcoded search queries seem to be consistent between them:
    # %s = %d and %s != %u and maxplayers = %d and numplayers < %d and %s = %d and %s != %s
    # %s and (%s)
    # %s = %u
    #
    # It does not look like OR commands are (at least by default) supported, so for now they won't be implemented.
    #
    # Things that must be implemented:
    #   - and operator
    #   - integer comparisons
    #   - string literals comparisons
    #   - comparison between two fields
    #   - comparison operators (<, >, =, !=)
    #   - if not already available, maybe extend the comparison operators to include <= and >= just to be safe
    #
    # Things that won't be supported for now unless required:
    #   - or operator
    #   - grouping of operators, e.g.: (x or y) and (y or z)

    start = i
    special_chars = "_"

    token_type = TokenType.UNKNOWN

    # Skip whitespace
    while i < len(filter) and filter[i].isspace():
        i += 1
        start += 1

    if i < len(filter):
        if filter[i] == "(" or filter[i] == ")":
            i += 1
            token_type = TokenType.TOKEN

        elif filter[i] == "=":
            i += 1
            token_type = TokenType.TOKEN

        elif filter[i] == ">" or filter[i] == "<":
            i += 1
            token_type = TokenType.TOKEN

            if i + 1 < len(filter) and filter[i+1] == "=":
                # >= or <=
                i += 1

        elif i + 1 < len(filter) and filter[i] == "!" and filter[i + 1] == "=":
            i += 2
            token_type = TokenType.TOKEN

        elif filter[i] == "'":
            token_type = TokenType.STRING

            i += 1 # Skip quotation mark
            while i < len(filter) and filter[i] != "'":
                i += 1

            if i < len(filter) and filter[i] == "'":
                i += 1 # Skip quotation mark

        elif filter[i] == "\"":
            # I don't know if it's in the spec or not, but I added "" string literals as well just in case.
            token_type = TokenType.STRING

            i += 1 # Skip quotation mark
            while i < len(filter) and filter[i] != "\"":
                i += 1

            if i < len(filter) and filter[i] == "\"":
                i += 1 # Skip quotation mark

        elif filter[i].isalnum() or filter[i] in special_chars:
            # Get whole numbers or words
            if filter[i].isdigit():
                token_type = TokenType.NUMBER
            if filter[i].isalpha():
                token_type = TokenType.FIELD

            while i < len(filter) and (filter[i].isalnum() or filter[i] in special_chars) and filter[i] not in "!=>< ":
                i += 1

    if token_type == TokenType.STRING:
        token = filter[start + 1:i - 1]
    else:
        token = filter[start:i]

    return token, i, token_type

def match(filter, i, search):
    start = i
    found_match = False

    # Get the next token
    token, i, _ = get_token(filter, i)

    # If the token isn't the same as what we're searching for, don't move forward.
    if token != search:
        i = start
    else:
        found_match = True

    return found_match, i

def parse_filter(filter):
    filters = []

    i = 0
    found_match = True
    # Continue while there's a connecting "and".
    while found_match and i < len(filter):
        found_match_bracket, i = match(filter, i, "(")

        left, i, _ = get_token(filter, i)
        if i >= len(filter):
            break

        op, i, _ = get_token(filter, i)
        if i >= len(filter):
            break

        right, i, token_type = get_token(filter, i)

        if found_match_bracket:
            found_closing_match_bracket, i = match(filter, i, ")")

        found_match, i = match(filter, i, "and")

        filters.append({'op': op, 'left': left, 'right': right, 'type': token_type})

    return filters

def find_servers(gameid, filter, fields, max_count):
    servers = []
    if gameid in server_list:
        filters = parse_filter(filter)

        if max_count <= 0:
            max_count = 1

        # Generate a list of servers that match the given criteria.
        for server in server_list[gameid]:
            if len(servers) > max_count and max_count != -1:
                break

            matched_filters = 0

            for key in filters:
                if key['left'] in server:
                    # Found key, perform actual comparison
                    right = key['right']
                    type = key['type']

                    # Only assume that a field will ever reference another field once, so nested references are not supported.
                    if type == TokenType.FIELD and key['right'] in server:
                        right = server[key['right']]

                        # Reuse the get_token function to update the new token type of the field in the database.
                        # Strings will return as fields but the distinction does not matter for the comparisons.
                        _, _, type = get_token(right, 0)

                    if key['op'] == "=" and server[key['left']] == right:
                        matched_filters += 1
                    elif key['op'] == "!=" and server[key['left']] != right:
                        matched_filters += 1
                    elif type == TokenType.NUMBER:
                        # Only perform greater than/less than comparisons on integer types.
                        if key['op'] == ">" and server[key['left']] > right:
                            matched_filters += 1
                        elif key['op'] == ">=" and server[key['left']] >= right:
                            matched_filters += 1
                        elif key['op'] == "<" and server[key['left']] < right:
                            matched_filters += 1
                        elif key['op'] == "<=" and server[key['left']] <= right:
                            matched_filters += 1
                else:
                    break

            if matched_filters == len(filters):
                # Create a result with only the fields requested
                result = {}

                if 'localip0' in server:
                    # localip1, localip2, ... are possible, but are they ever used?
                    # Small chance this might cause an issue later.
                    result['localip0'] = server['localip0']

                if 'localport' in server:
                    result['localport'] = server['localport']

                if 'localport' in server:
                    result['localport'] = server['localport']

                if 'natneg' in server:
                    result['natneg'] = server['natneg']

                if 'publicip' in server:
                    result['publicip'] = server['publicip']

                if 'publicport' in server:
                    result['publicport'] = server['publicport']

                if '__session__' in server:
                    result['__session__'] = server['__session__']

                requested = {}
                for field in fields:
                    if not field in result:
                        if field in server:
                            requested[field] = server[field]
                        else:
                            # Return a dummy value. What's the normal behavior of the real server in this case?
                            requested[field] = ""


                result['requested'] = requested
                servers.append(result)

    return servers

def update_server_list(gameid, session, value):
    # Make sure the user isn't hosting multiple servers or there isn't some left over server information that
    # never got handled properly (game crashed, etc).
    delete_server(gameid, session)

    # If the game doesn't exist already, create a new list.
    if not gameid in server_list:
        server_list[gameid] = []

    # Add new server
    value['__session__'] = session
    print "Added %s to the server list for %s" % (gameid, value)
    server_list[gameid].append(value)

def delete_server(gameid, session):
    if not gameid in server_list:
        # Nothing to do if no servers for that game even exist.
        return

    # Remove all servers hosted by the given session id.
    server_list[gameid] = [x for x in server_list[gameid] if x['__session__'] != session]


class GamespyServerDatabase(BaseManager):
    pass

def start_server():
    address = ("127.0.0.1", 27500)
    password = ""

    #server_list["tetrisds"] = []
    #server_list["tetrisds"].append({'__session__': 0, 'key': "helloworld", 'value': "Hello, world!", 'extra': "Test"})

    GamespyServerDatabase.register("get_server_list", callable=lambda:server_list)
    GamespyServerDatabase.register("find_servers", callable=find_servers)
    GamespyServerDatabase.register("update_server_list", callable=update_server_list)
    GamespyServerDatabase.register("delete_server", callable=delete_server)

    print "Started server on %s:%d..." % (address[0], address[1])

    manager = GamespyServerDatabase(address = address, authkey = password)
    server = manager.get_server()
    server.serve_forever()

if __name__ == '__main__':
    freeze_support()
    start_server()
