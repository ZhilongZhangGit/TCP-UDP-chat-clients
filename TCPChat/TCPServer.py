import socket
import os
import signal
import sys
import selectors

# Selector for helping us select incoming data and connections from multiple sources.

sel = selectors.DefaultSelector()

# Client list for mapping connected clients to their connections.

client_list = []


# Signal handler for graceful exiting.  We let clients know in the process so they can disconnect too.

def signal_handler(sig, frame):
    print('Interrupt received, shutting down ...')
    message='DISCONNECT CHAT/1.0\n'
    for reg in client_list:
        reg[1].send(message.encode())
    sys.exit(0)

# Read a single line (ending with \n) from a socket and return it.
# We will strip out the \r and the \n in the process.

def get_line_from_socket(sock):

    done = False
    line = ''
    while (not done):
        char = sock.recv(1).decode()
        if (char == '\r'):
            pass
        elif (char == '\n'):
            done = True
        else:
            line = line + char
    return line

# Search the client list for a particular user.

def client_search(user):
    for reg in client_list:
        if reg[0] == user:
            return reg[1]
    return None

# Search the client list for a particular user by their socket.

def client_search_by_socket(sock):
    for reg in client_list:
        if reg[1] == sock:
            return reg[0]
    return None

# Add a user to the client list.

def client_add(user, conn):
    registration = (user, conn)
    client_list.append(registration)

# Remove a client when disconnected.

def client_remove(user):
    for reg in client_list:
        if reg[0] == user:
            client_list.remove(reg)
            break

# Function to read messages from clients.
follow_list = []
def read_message(sock, mask):

    message = get_line_from_socket(sock)
    # Does this indicate a closed connection?

    if message == '':
        print('Closing connection')
        sel.unregister(sock)
        sock.close()

    # Receive the message.  

    else:
        user = client_search_by_socket(sock)
        print(f'Received message from user {user}:  ' + message)
        words = message.split(' ')
        # global follow_list

        # Check for client disconnections.  
  
        if words[0] == 'DISCONNECT':
            # print(words[0])
            print('Disconnecting user ' + user)
            client_remove(user)
            sel.unregister(sock)
            sock.close()

        if words[1] == '!list':
            
            # print(words[0])
            for cli in client_list:
                if cli[0] == user:
                    client_sock = cli[1]
                    list_of_users = []
                    for users in client_list:
                        users = f'{users[0]}'
                        list_of_users.append(users)
                    msg = ', '.join(str(e) for e in list_of_users)
                    msg = f'{msg}\n'
                    client_sock.send(str(msg).encode())

        # follow_list = []
        elif words[1] == '!follow?':
            for reg in client_list:
                if reg[0] == user:
                    client_sock = reg[1]
                    followed_items = []
                    for followed in follow_list:
                        followed_items.append(followed)

                    message = f"{', '.join(str(e) for e in followed_items)}\n"
                    client_sock.send(str(message).encode())

        elif words[1] == '!follow' and len(words[2]) > 0:
            for reg in client_list:
                if reg[0] == user:
                    client_sock = reg[1]
                    to_follow = words[2]
                    follow_list.append(to_follow)
                    msg = f'Now following {words[2]}\n'
                    client_sock.send(str(msg).encode())

        elif words[1] == '!unfollow' and len(words[2]) > 0:
            for reg in client_list:
                if reg[0] == user:
                    client_sock = reg[1]
                    to_unfollow = words[2]

                    if to_unfollow in follow_list:
                        follow_list.remove(to_unfollow)
                        msg = f'No longer following {to_unfollow}\n'
                        client_sock.send(str(msg).encode())
                    else:
                        msg = f'Error: {to_unfollow} not in the follow list\n'
                        client_sock.send(str(msg).encode())

        elif words[1] == '!exit':
            for reg in client_list:
                if reg[0]==user: 
                    client_sock = reg[1]
                    close_signal = b"!exit\n"
                    client_sock.send(close_signal)
                    client_remove(reg[0])


        elif words[1] == '!attach':
            for reg in client_list:
                if reg[0] == user:
                    client_sock = reg[1]
                    
                    try:
                        file = words[2]
                        print(file)
                        if os.path.exists(file):
                            filesize = os.path.getsize(file)
                            msg = f'incoming file: {file} \n Origin: {reg[0]} \n Content-Length: {filesize}\n'
                            client_sock.send(msg.encode())
                            while True:
                                with open(file, 'rb') as f:
                                    bytes_read = f.read(9128)
                                    while True:
                                        file_down = client_sock.recv(9128)
                                        # if not file_down:
                                        break
                                    f.write(file_down)
                                break
                            msg2 = f'Attachment {file} attached and distributed\n'
                            client_sock.send(msg2.encode())
                        else:
                            msg = f'Error: {file} does not exists in specified path \n'
                            client_sock.send(msg.encode())
                    except IOError as e:
                        if 'BlockingIOError: [Errno 11] Resource temporarily unavailable' in str(e):
                            pass

        if '@all' in words:
            for reg in client_list:
                if reg[0] == user:
                    client_sock = reg[1]
                    client_sock.send(f'{message}\n'.encode())
        clean_follow_list = list(set(follow_list))
        for keyword in clean_follow_list:
            if '@' in keyword and keyword != '@all':
                if keyword in client_list:
                    for reg in client_list:
                        if reg[0] == user:
                            client_sock = reg[1]
                            client_sock.send(f'{message}\n'.encode())

        # Send message to all users.  Send at most only once, and don't send to yourself. 
        # Need to re-add stripped newlines here.

        else:
            for reg in client_list:
                if reg[0] == user:
                    continue
                client_sock = reg[1]
                forwarded_message = f'{message}\n'
                client_sock.send(forwarded_message.encode())

# Function to accept and set up clients.

def accept_client(sock, mask):
    conn, addr = sock.accept()
    print('Accepted connection from client address:', addr)
    message = get_line_from_socket(conn)
    message_parts = message.split()

    # Check format of request.

    if ((len(message_parts) != 3) or (message_parts[0] != 'REGISTER') or (message_parts[2] != 'CHAT/1.0')):
        print('Error:  Invalid registration message.')
        print('Received: ' + message)
        print('Connection closing ...')
        response='400 Invalid registration\n'
        conn.send(response.encode())
        conn.close()

    # If request is properly formatted and user not already listed, go ahead with registration.

    else:
        user = message_parts[1]

        if (client_search(user) == None):
            client_add(user,conn)
            print(f'Connection to client established, waiting to receive messages from user \'{user}\'...')
            response='200 Registration succesful\n'
            conn.send(response.encode())
            conn.setblocking(False)
            sel.register(conn, selectors.EVENT_READ, read_message)

        # If user already in list, return a registration error.

        else:
            print('Error:  Client already registered.')
            print('Connection closing ...')
            response='401 Client already registered\n'
            conn.send(response.encode())
            conn.close()


# Our main function.

def main():

    # Register our signal handler for shutting down.

    signal.signal(signal.SIGINT, signal_handler)

    # Create the socket.  We will ask this to work on any interface and to pick
    # a free port at random.  We'll print this out for clients to use.

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('', 0))
    print('Will wait for client connections at port ' + str(server_socket.getsockname()[1]))
    server_socket.listen(100)
    server_socket.setblocking(False)
    sel.register(server_socket, selectors.EVENT_READ, accept_client)
    print('Waiting for incoming client connections ...')
     
    # Keep the server running forever, waiting for connections or messages.
    
    while(True):
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)    

if __name__ == '__main__':
    main()

