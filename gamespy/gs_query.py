import copy

def parse_gamespy_message(message):
    stack = []
    messages = {}
    msg = message

    if len(msg) == 0 or msg[0] != '\\':
        # bad command, return nothing
        return "", ""

    while len(msg) > 0 and msg[0] == '\\' and "\\final\\" in msg:
        # Find the command
        # Don't search for more commands if there isn't a \final\, save the left over for the next packet
        found_command = False
        while len(msg) > 0 and msg[0] == '\\':
            keyEnd = msg[1:].index('\\') + 1
            key = msg[1:keyEnd]
            msg = msg[keyEnd + 1:]

            if key == "final":
                break

            if '\\' in msg:
                if msg[0] == '\\':
                    value = ""
                else:
                    valueEnd = msg[1:].index('\\')
                    value = msg[:valueEnd + 1]
                    msg = msg[valueEnd + 1:]
            else:
                value = msg

            if found_command == False:
                messages['__cmd__'] = key
                messages['__cmd_val__'] = value
                found_command = True

            messages[key] = value

        stack.append(messages)
        messages = {}

    # Return msg so we can prepend any leftover commands to the next packet.
    return stack, msg


# Generate a list based on the input dictionary.
# The main command must also be stored in __cmd__ for it to put the parameter at the beginning.
def create_gamespy_message_from_dict(messages_orig):
    # Deep copy the dictionary because we don't want the original to be modified
    messages = copy.deepcopy(messages_orig)

    cmd = ""
    cmd_val = ""

    if "__cmd__" in messages:
        cmd = messages['__cmd__']
        messages.pop('__cmd__', None)

    if "__cmd_val__" in messages:
        cmd_val = messages['__cmd_val__']
        messages.pop('__cmd_val__', None)

    if cmd in messages:
        messages.pop(cmd, None)

    l = []
    l.append(("__cmd__", cmd))
    l.append(("__cmd_val__", cmd_val))

    for message in messages:
        l.append((message, messages[message]))

    return l


def create_gamespy_message_from_list(messages):
    d = {}
    cmd = ""
    cmd_val = ""

    query = ""
    for message in messages:
        if message[0] == "__cmd__":
            cmd = message[1]
        elif message[0] == "__cmd_val__":
            cmd_val = message[1]
        else:
            query += "\\%s\\%s" % (message[0], message[1])

    if cmd != "":
        # Prepend the main command if one was found.
        query = "\\%s\\%s%s" % (cmd, cmd_val, query)

    return query


# Create a message based on a dictionary (or list) of parameters.
def create_gamespy_message(messages, id=None):
    query = ""

    if isinstance(messages, dict):
        messages = create_gamespy_message_from_dict(messages)

    # Check for an id if the id needs to be updated.
    # If it already exists in the list then update it, else add it
    if id != None:
        for message in messages:
            if message[0] == "id":
                messages.pop(messages.index(message))
                messages.append(("id", str(id)))
                id = None  # Updated id, so don't add it to the query later
                break  # Found id, stop searching list

    query = create_gamespy_message_from_list(messages)

    if id != None:
        query += create_gamespy_message_from_list([("id", id)])

    query += "\\final\\"

    return query
