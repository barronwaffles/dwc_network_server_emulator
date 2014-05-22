'''
Provides functions for creating GameSpy messages out of different structure types

GameSpy messages are \-seperated sets of key-value pairs separated by \ .

'''
import copy

def parse_gamespy_message(msg):
    stack = []

    while "\\final\\" in msg:
        # Find the command
        # Don't search for more commands if there isn't a \final\, save the left over for the next packet
        found_command = False
        messages = {}
        while msg and msg[0] == '\\':

            key, msg = msg[1:].split('\\', 1)

            if key == "final":
                break

            if '\\' in msg:
                if msg[0] == '\\':
                    value = ""
                else:
                    value, msg = msg.split('\\')
                    msg = '\\' + msg
            else:
                value = msg

            if found_command == False:
                messages['__cmd__'] = key
                messages['__cmd_val__'] = value
                found_command = True

            messages[key] = value

        stack.append(messages)

    # Return msg so we can prepend any leftover commands to the next packet.
    return stack, msg

def prepare_kv(key, value):
    return r'\{0}\{1}'.format(key, value)

# Generate a list based on the input dictionary.
# The main command must also be stored in __cmd__ for it to put the parameter at the beginning.
def create_gamespy_message_from_dict(messages_orig):
    # Deep copy the dictionary because we don't want the original to be modified
    messages = copy.deepcopy(messages_orig)

    cmd = messages.pop('__cmd__', "")
    cmd_val = messages.pop('__cmd_val__', "")

    if cmd in messages:
        messages.pop(cmd, None)

    l = [
        ("__cmd__", cmd),
        ("__cmd_val__", cmd_val),
    ]

    l.extend((key, val) for key, val in messages.items())
    return l


def create_gamespy_message_from_list(messages):
    cmd, cmdval = "", ""

    query = ""
    for key, val in messages:
        if key == "__cmd__":
            cmd = val
        elif key == "__cmd_val__":
            cmd_val = val
        else:
            query += prepare_kv(key, val)

    if cmd:
        # Prepend the main command if one was found.
        query = r"\%s\%s%s" % (cmd, cmd_val, query)

    return query


# Create a message based on a dictionary (or list) of parameters.
def create_gamespy_message(messages, i=None):
    query = ""

    if isinstance(messages, dict):
        messages = create_gamespy_message_from_dict(messages)

    # Check for an id if the id needs to be updated.
    # If it already exists in the list then update it, else add it
    if i != None:
        for message in messages:
            if message[0] == "id":
                messages.pop(messages.index(message))
                messages.append(("id", str(i)))
                i = None  # Updated id, so don't add it to the query later
                break  # Found id, stop searching list

    query = create_gamespy_message_from_list(messages)

    if i != None:
        query += create_gamespy_message_from_list([("id", i)])

    return query + "\\final\\"
