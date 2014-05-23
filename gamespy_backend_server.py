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
import time
import ast

from multiprocessing.managers import BaseManager
from multiprocessing import freeze_support
import other.utils as utils

class TokenType:
    UNKNOWN = 0
    FIELD = 1
    STRING = 2
    NUMBER = 3
    TOKEN = 4

# Logger settings
logger_output_to_console = True
logger_output_to_file = True
logger_name = "GamespyBackendServer"
logger_filename = "gamespy_backend_server.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

def get_token(filters):
    # Complex example from Dungeon Explorer: Warriors of Ancient Arts
    # dwc_mver = 3 and dwc_pid != 474890913 and maxplayers = 2 and numplayers < 2 and dwc_mtype = 0 and dwc_mresv != dwc_pid and (MatchType='english')
    #
    # Even more complex example from Phantasy Star Zero:
    # dwc_mver = 3 and dwc_pid != 4 and maxplayers = 3 and numplayers < 3 and dwc_mtype = 0 and dwc_mresv != dwc_pid and (((20=auth)AND((1&mskdif)=mskdif)AND((14&mskstg)=mskstg)))
    #
    # Example with OR from Mario Kart Wii:
    # dwc_mver = 90 and dwc_pid != 1 and maxplayers = 11 and numplayers < 11 and dwc_mtype = 0 and dwc_hoststate = 2 and dwc_suspend = 0 and (rk = 'vs_123' and (ev > 4263 or ev <= 5763) and p = 0)
    i = 0
    start = i
    special_chars = "_"

    token_type = TokenType.UNKNOWN

    # Skip whitespace
    while i < len(filters) and filters[i].isspace():
        i += 1
        start += 1

    if i < len(filters):
        if filters[i] == "(":
            i += 1
            token_type = TokenType.TOKEN

        elif filters[i] == ")":
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

            if i < len(filters) and filters[i] == "=":
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

        elif i + 1 < len(filters) and filters[i] == '-' and filters[i + 1].isdigit():
            # Negative number
            token_type = TokenType.NUMBER
            i += 1
            while i < len(filters) and filters[i].isdigit():
                i += 1
        elif filters[i].isalnum() or filters[i] in special_chars:
            # Whole numbers or words
            if filters[i].isdigit():
                token_type = TokenType.NUMBER
            elif filters[i].isalpha():
                token_type = TokenType.FIELD

            while i < len(filters) and (filters[i].isalnum() or filters[i] in special_chars) and filters[i] not in "!=>< ":
                i += 1

    token = filters[start:i]
    if token_type == TokenType.FIELD and (token.lower() == "and" or token.lower() == "or"):
        token = token.lower()

    return token, i, token_type

def translate_expression(filters):
    output = []
    variables = []

    while filters:
        token, i, token_type = get_token(filters)
        filters = filters[i:]

        if token_type == TokenType.TOKEN:
            # Python uses == instead of = for comparisons, so replace it with the proper token for compilation.
            if token == "=":
                token = "=="

        elif token_type == TokenType.FIELD:
            # Each server has its own variables so handle it later.
            variables.append(len(output))

        output.append(token)

    return output, variables

def validate_ast(node, num_literal_only):
    # This function tries to verify that the expression is a valid expression before it gets evaluated.
    # Anything besides the whitelisted things below are strictly forbidden:
    # - String literals
    # - Number literals
    # - Binary operators (CAN ONLY BE PERFORMED ON TWO NUMBER LITERALS)
    # - Comparisons (cannot use 'in', 'not in', 'is', 'is not' operators)
    #
    # Anything such as variables or arrays or function calls are NOT VALID.
    # Never run the expression received from the client before running this function on the expression first.
    #print type(node)

    # Only allow literals, comparisons, and math operations
    valid_node = False
    if isinstance(node, ast.Num):
        valid_node = True

    elif isinstance(node, ast.Str):
        if num_literal_only == False:
            valid_node = True

    elif isinstance(node, ast.BoolOp):
        for value in node.values:
            valid_node = validate_ast(value, num_literal_only)

            if valid_node == False:
                break

    elif isinstance(node, ast.BinOp):
        valid_node = validate_ast(node.left, True)

        if valid_node == True:
            valid_node = validate_ast(node.right, True)

    elif isinstance(node, ast.UnaryOp):
        valid_node = validate_ast(node.operand, num_literal_only)

    elif isinstance(node, ast.Expr):
        valid_node = validate_ast(node.value, num_literal_only)

    elif isinstance(node, ast.Compare):
        valid_node = validate_ast(node.left, num_literal_only)

        for op in node.ops:
            #print type(op)

            # Restrict "is", "is not", "in", and "not in" python comparison operators.
            # These are python-specific and the games have no way of knowing what they are, so there's no reason
            # to keep them around.
            if isinstance(op, ast.Is) or isinstance(op, ast.IsNot) or isinstance(op, ast.In) or isinstance(op, ast.NotIn):
                valid_node = False
                break

        if valid_node == True:
            for expr in node.comparators:
                valid_node = validate_ast(expr, num_literal_only)

    elif isinstance(node, ast.Call):
        valid_node = False

    return valid_node


class GameSpyServerDatabase(BaseManager):
    pass

class GameSpyBackendServer(object):
    def __init__(self):
        self.server_list = {}
        self.natneg_list = {}

        GameSpyServerDatabase.register("get_server_list", callable=lambda:self.server_list)
        GameSpyServerDatabase.register("find_servers", callable=self.find_servers)
        GameSpyServerDatabase.register("find_server_by_address", callable=self.find_server_by_address)
        GameSpyServerDatabase.register("find_server_by_local_address", callable=self.find_server_by_local_address)
        GameSpyServerDatabase.register("update_server_list", callable=self.update_server_list)
        GameSpyServerDatabase.register("delete_server", callable=self.delete_server)
        GameSpyServerDatabase.register("add_natneg_server", callable=self.add_natneg_server)
        GameSpyServerDatabase.register("get_natneg_server", callable=self.get_natneg_server)
        GameSpyServerDatabase.register("delete_natneg_server", callable=self.delete_natneg_server)

    def start(self):
        address = ("127.0.0.1", 27500)
        password = ""

        logger.info("Started server on %s:%d..." % (address[0], address[1]))

        manager = GameSpyServerDatabase(address = address, authkey = password)
        server = manager.get_server()
        server.serve_forever()


    def find_servers(self, gameid, filters, fields, max_count):
        matched_servers = []

        # How does it handle 0?
        if max_count == 0:
            return []

        if gameid not in self.server_list:
            return []

        start = time.time()

        for server in self.server_list[gameid]:
            translated, variables = translate_expression(filters)

            for idx in variables:
                token = translated[idx]

                if token in server:
                    token = server[token]
                    _, _, token_type = get_token(token)

                    if token_type == TokenType.FIELD:
                        # At this point, any field should be a string.
                        # This does not support stuff like:
                        # dwc_test = 'test', dwc_test2 = dwc_test, dwc_test3 = dwc_test2
                        token = '"' + token + '"'

                    translated[idx] = token

            q = ' '.join(translated)

            # Always run validate_ast over the entire AST before evaluating anything. eval() is dangerous to use on
            # unsanitized inputs. The validate_ast function has a fairly strict whitelist so it should be safe in what
            # it accepts as valid.
            m = ast.parse(q, "<string>", "exec")
            valid_filter = True
            for node in m.body:
                valid_filter = validate_ast(node, False)

            if valid_filter == False:
                # Return only anything matched up until this point.
                return matched_servers

            # Use Python to evaluate the query. This method may take a little time but it shouldn't be all that
            # big of a difference, I think. It takes about 0.0004 seconds per server to determine whether or not it's a
            # match on my computer. Usually there's a low max_servers set when the game searches for servers, so assuming
            # something like the game is asking for 6 servers, it would take about 0.0024 seconds total. These times
            # will obviously be different per computer. It's not ideal, but it shouldn't be a huge bottleneck.
            # A possible way to speed it up is to make validate_ast also evaluate the expressions at the same time as it
            # validates it.
            result = eval(q)

            if result == True:
                matched_servers.append(server)

                if len(matched_servers) >= max_count:
                    break

        servers = []
        for server in matched_servers:
            # Create a result with only the fields requested
            result = {}

            # Return all localips
            i = 0
            while 'localip' + str(i) in server:
                result['localip' + str(i)] = server['localip' + str(i)]
                i += 1

            allkeys = ('localport', 'localport', 'natneg', 'publicip', 'publicport', '__session__', '__console__')
            for key in allkeys:
                if key in server:
                    result[key] = server[key]

            # Return a dummy value if we don't have one.
            # What's the normal behavior of the real server in this case?
            requested = {field: server.get(field, "") for field in fields}


            result['requested'] = requested
            servers.append(result)

        logger.debug("Matched %d servers in %s seconds" % (len(servers), (time.time() - start)))

        return servers

    def update_server_list(self, gameid, session, value, console):
        # Make sure the user isn't hosting multiple servers or there isn't some left over server information that
        # never got handled properly (game crashed, etc).
        self.delete_server(gameid, session)

        # If the game doesn't exist already, create a new list.
        self.server_list.setdefault(gameid, [])

        # Add new server
        value['__session__'] = session
        value['__console__'] = console

        logger.debug("Added %s to the server list for %s" % (value, gameid))
        self.server_list[gameid].append(value)
        logger.debug("%s servers: %d" % (gameid, len(self.server_list[gameid])))

        return value

    def delete_server(self, gameid, session):
        if not gameid in self.server_list:
            # Nothing to do if no servers for that game even exist.
            return

        # Remove all servers hosted by the given session id.
        count = len(self.server_list[gameid])
        self.server_list[gameid] = [x for x in self.server_list[gameid] if x['__session__'] != session]
        count -= len(self.server_list[gameid])
        logger.debug("Deleted %d %s servers where session = %d" % (count, gameid, session))

    def find_server_by_address(self, ip, port, gameid = None):
        if gameid == None:
            # Search all servers
            for gid in self.server_list:
                server = self.find_server_by_address(ip, port, gid)
                if server is not None:
                    return server
        else:
            for server in self.server_list[gameid]:
                if server['publicip'] == ip and server['publicport'] == str(port):
                    return server

    def find_server_by_local_address(self, publicip, localaddr, gameid = None):
        localip = localaddr[0]
        localport = localaddr[1]
        localip_int_le = localaddr[2]
        localip_int_be = localaddr[3]

        if gameid == None:
            # Search all servers
            for gid in self.server_list:
                server = self.find_server_by_local_address(publicip, localaddr, gid)
                if server is not None:
                    return server
        else:
            for server in self.server_list[gameid]:
                logger.debug("publicip 1: %s == %s ? %d port: %s == %s ? %d",
                             server['publicip'], str(localip_int_le), server['publicip'] == str(localip_int_le),
                             server['publicport'], str(localport), server['publicport'] == str(localport))
                if server['publicip'] == str(localip_int_le) and server['publicport'] == str(localport):
                    return server

                logger.debug("publicip 2: %s == %s ? %d port: %s == %s ? %d",
                             server['publicip'], str(localip_int_be), server['publicip'] == str(localip_int_be),
                             server['publicport'], str(localport), server['publicport'] == str(localport))
                if server['publicip'] == str(localip_int_be) and server['publicport'] == str(localport):
                    return server

                logger.debug("publicip 3: %s == %s ? %d", server['publicip'], publicip, server['publicip'] == publicip)
                if server['publicip'] == publicip and (server['localport'] == str(localport) or server['publicport'] == str(localport)):
                    for x in range(10):
                        if server.get('localip%d'%x, None) == localip:
                            return server

    def add_natneg_server(self, cookie, server):
        self.natneg_list.setdefault(cookie, [])
        logger.debug("Added natneg server %d", cookie)
        self.natneg_list[cookie].append(server)

    def get_natneg_server(self, cookie):
        return self.natneg_list.get(cookie, None)

    def delete_natneg_server(self, cookie):
        # TODO: Find a good time to prune the natneg server listing.
        if cookie in self.natneg_list:
            del self.natneg_list[cookie]
        logger.debug("Deleted natneg server %d", cookie)


if __name__ == '__main__':
    freeze_support()

    backend_server = GameSpyBackendServer()
    backend_server.start()
