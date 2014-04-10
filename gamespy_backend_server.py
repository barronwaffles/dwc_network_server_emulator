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

import logging

from multiprocessing.managers import BaseManager
from multiprocessing import freeze_support
import other.utils as utils

class TokenType:
    UNKNOWN = 0
    FIELD = 1
    STRING = 2
    NUMBER = 3
    TOKEN = 4

logger = utils.create_logger("GamespyBackendServer", "gamespy_backend_server.log", -1)

class GameSpyServerDatabase(BaseManager):
    pass

class GameSpyBackendServer(object):
    def __init__(self):
        self.server_list = {}

        GameSpyServerDatabase.register("get_server_list", callable=lambda:self.server_list)
        GameSpyServerDatabase.register("find_servers", callable=self.find_servers)
        GameSpyServerDatabase.register("find_server_by_address", callable=self.find_server_by_address)
        GameSpyServerDatabase.register("update_server_list", callable=self.update_server_list)
        GameSpyServerDatabase.register("delete_server", callable=self.delete_server)

    def start(self):
        address = ("127.0.0.1", 27500)
        password = ""

        logger.log(logging.INFO, "Started server on %s:%d..." % (address[0], address[1]))

        manager = GameSpyServerDatabase(address = address, authkey = password)
        server = manager.get_server()
        server.serve_forever()

    def get_token(self, filters, i):
        # Complex example from Dungeon Explorer: Warriors of Ancient Arts
        # dwc_mver = 3 and dwc_pid != 474890913 and maxplayers = 2 and numplayers < 2 and dwc_mtype = 0 and dwc_mresv != dwc_pid and (MatchType='english')
        #
        # Even more complex example from Phantasy Star Zero:
        # dwc_mver = 3 and dwc_pid != 4 and maxplayers = 3 and numplayers < 3 and dwc_mtype = 0 and dwc_mresv != dwc_pid and (((20=auth)AND((1&mskdif)=mskdif)AND((14&mskstg)=mskstg)))
        #
        # Digging into a few DS games, and these hardcoded search queries seem to be consistent between them:
        # %s = %d and %s != %u and maxplayers = %d and numplayers < %d and %s = %d and %s != %s
        # %s and (%s)
        # %s = %u
        #
        # It does not look like OR commands are (at least by default) supported, so for now they won't be implemented.
        #
        # Things that have been implemented:
        #   - and operator (assuming all commands are linked by ANDs)
        #   - integer comparisons
        #   - string literals comparisons
        #   - comparison between two fields
        #   - comparison operators (<, >, =, !=, <=, >=)
        #   - bitwise and operator (&)
        #
        # Things that won't be supported for now unless required:
        #   - or operator
        #   - grouping of operators, e.g.: (x or y) and (y or z)
        start = i
        special_chars = "_"

        token_type = TokenType.UNKNOWN

        # Skip whitespace
        while i < len(filters) and filters[i].isspace():
            i += 1
            start += 1

        if i < len(filters):
            if filters[i] == "(" or filters[i] == ")":
                i += 1
                token_type = TokenType.TOKEN

            elif filters[i] == "&":
                i += 1
                token_type = TokenType.TOKEN

            elif filters[i] == "=":
                i += 1
                token_type = TokenType.TOKEN

            elif filters[i] == ">" or filters[i] == "<":
                i += 1
                token_type = TokenType.TOKEN

                if i + 1 < len(filters) and filters[i+1] == "=":
                    # >= or <=
                    i += 1

            elif i + 1 < len(filters) and filters[i] == "!" and filters[i + 1] == "=":
                i += 2
                token_type = TokenType.TOKEN

            elif filters[i] == "'":
                # String literal
                token_type = TokenType.STRING

                i += 1 # Skip quotation mark
                while i < len(filters) and filters[i] != "'":
                    i += 1

                if i < len(filters) and filters[i] == "'":
                    i += 1 # Skip quotation mark

            elif filters[i] == "\"":
                # I don't know if it's in the spec or not, but I added "" string literals as well just in case.
                token_type = TokenType.STRING

                i += 1 # Skip quotation mark
                while i < len(filters) and filters[i] != "\"":
                    i += 1

                if i < len(filters) and filters[i] == "\"":
                    i += 1 # Skip quotation mark

            elif filters[i].isalnum() or filters[i] in special_chars:
                # Whole numbers or words
                if filters[i].isdigit():
                    token_type = TokenType.NUMBER
                if filters[i].isalpha():
                    token_type = TokenType.FIELD

                while i < len(filters) and (filters[i].isalnum() or filters[i] in special_chars) and filters[i] not in "!=>< ":
                    i += 1

        if token_type == TokenType.STRING:
            token = filters[start + 1:i - 1]
        else:
            token = filters[start:i]

        if token_type == TokenType.NUMBER:
            token = int(token)

        return token, i, token_type

    def match(self, filters, i, search, case_insensitive=False):
        start = i
        found_match = False

        # Get the next token
        token, i, _ = self.get_token(filters, i)

        if case_insensitive == True:
            token = token.lower()
            search = search.lower()

        # If the token isn't the same as what we're searching for, don't move forward.
        if token != search:
            i = start
        else:
            found_match = True

        return found_match, i

    def parse_filter(self, filters):
        ops = []
        values = []
        i = 0
        found_match = True
        filter_count = 0

        # Continue while there's a connecting "and".
        while found_match and i < len(filters):
            found_match_bracket, i = self.match(filters, i, "(")

            if found_match_bracket:
                a, b, filters, f = self.parse_filter(filters[i:])
                found_closing_match_bracket, i = self.match(filters, i, ")")
                found_match = found_closing_match_bracket
                a.reverse()
                b.reverse()
                ops = a + ops
                values = b + values
                filter_count += f

            else:
                l, i, token_type = self.get_token(filters, i)

                if token_type == TokenType.FIELD and l.lower() == "and":
                    filter_count += 1
                    continue

                elif l == "(" or l == ")":
                    continue

                if token_type == TokenType.TOKEN:
                    ops.append(l)
                else:
                    values.append({'value': l, 'type': token_type})

        return ops, values, filters[i:], filter_count

    def find_servers(self, gameid, filters, fields, max_count):
        servers = []

        if gameid in self.server_list:
            ops_parsed, values_parsed, _, filter_count = self.parse_filter(filters)

            # In the case that there were no "AND" commands, check to make sure there was at least one other command
            if len(ops_parsed) > 0:
                filter_count += 1

            if max_count <= 0:
                max_count = 1

            # Generate a list of servers that match the given criteria.
            for server in self.server_list[gameid]:
                ops = ops_parsed
                values = values_parsed

                if len(servers) > max_count and max_count != -1:
                    break

                matched_filters = 0
                while len(ops) > 0:
                    op = ops.pop()
                    r = None
                    l = None

                    if len(values) != 0:
                        r = values.pop()
                    if len(values) != 0:
                        l = values.pop()

                    if r == None or l == None:
                        break

                    lval = l['value']
                    rval = r['value']

                    # If the left value is a field name and it's in the server variables, get its value.
                    if l['type'] == TokenType.FIELD and l['value'] in server:
                        lval = server[l['value']]
                        _, _, l['type'] = self.get_token(lval, 0)

                    # If the value is a number then convert it to an integer for proper integer comparison.
                    if l['type'] == TokenType.NUMBER:
                        lval = int(lval)

                    # If the right value is a field name and it's in the server variables, get its value.
                    if r['type'] == TokenType.FIELD and r['value'] in server:
                        rval = server[r['value']]
                        _, _, r['type'] = self.get_token(rval, 0)

                    # If the value is a number then convert it to an integer for proper integer comparison.
                    if r['type'] == TokenType.NUMBER:
                        rval = int(rval)

                    match = False
                    if op == "=" and lval == rval:
                        match = True
                    elif op == "!=" and lval != rval:
                        match = True
                    elif op == "<" and lval < rval:
                        match = True
                    elif op == ">" and lval > rval:
                        match = True
                    elif op == ">=" and lval >= rval:
                        match = True
                    elif op == "<=" and lval <= rval:
                        match = True
                    elif op == "&":
                        values.append({ 'value': int(lval & rval), 'type': TokenType.NUMBER})

                    if match == True:
                        #print "Matched: %s %s %s" % (l['value'], op, r['value'])
                        matched_filters += 1
                    elif op != "&": # & doesn't need to be matched, so don't display a message for it
                        #print "Not matched: %s %s %s" % (l['value'], op, r['value'])
                        pass

                #print "Matched %d/%d" % (matched_filters, filter_count)

                # Add the server if everything was matched
                if matched_filters == filter_count:
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

    def update_server_list(self, gameid, session, value):
        # Make sure the user isn't hosting multiple servers or there isn't some left over server information that
        # never got handled properly (game crashed, etc).
        self.delete_server(gameid, session)

        # If the game doesn't exist already, create a new list.
        if not gameid in self.server_list:
            self.server_list[gameid] = []

        # Add new server
        value['__session__'] = session

        logger.log(logging.DEBUG, "Added %s to the server list for %s" % (value, gameid))
        self.server_list[gameid].append(value)
        logger.log(logging.DEBUG, "%s servers: %d" % (gameid, len(self.server_list[gameid])))

    def delete_server(self, gameid, session):
        if not gameid in self.server_list:
            # Nothing to do if no servers for that game even exist.
            return

        # Remove all servers hosted by the given session id.
        count = len(self.server_list[gameid])
        self.server_list[gameid] = [x for x in self.server_list[gameid] if x['__session__'] != session]
        count -= len(self.server_list[gameid])
        logger.log(logging.DEBUG, "Deleted %d %s servers where session = %d" % (count, gameid, session))

    def find_server_by_address(self, ip, port, gameid = None):
        if gameid == None:
            # Search all servers
            for gameid in self.server_list:
                for server in self.server_list[gameid]:
                    if server['publicip'] == ip and server['publicport'] == str(port):
                        return server
        else:
            for server in self.server_list[gameid]:
                if server['publicip'] == ip and server['publicport'] == str(port):
                    return server

        return None

if __name__ == '__main__':
    freeze_support()

    backend_server = GameSpyBackendServer()
    backend_server.start()