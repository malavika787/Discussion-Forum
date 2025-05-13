#imports
import socket
import os
import re
import threading
import queue
import sys

BUFFER_SIZE = 1024 #initialising buffer size to 1024 bytes 
CREDENTIALS_FILE = 'credentials.txt' 
LOGGED_IN_USERS = set()
FILE_LOCKS = {}  #to store locks for each threads file
client_queues = {}

#dispatcher - need to run multiple clients at the same time using locks and dispatching threads
def dispatcher(serverSocket):
    while True:
        data, client_address = serverSocket.recvfrom(BUFFER_SIZE)

        if client_address not in client_queues:
            q = queue.Queue()
            client_queues[client_address] = q
            handler_thread = threading.Thread(
                target=handle_client, 
                args=(serverSocket, client_address, q),
                daemon=True
            )
            handler_thread.start()

        client_queues[client_address].put(data)


#to lock the file access - im only going to allow one command to be executed at a time
def acquire_lock(thread_title):
    if thread_title not in FILE_LOCKS:
        FILE_LOCKS[thread_title] = threading.Lock()
    FILE_LOCKS[thread_title].acquire()

#to release the lock after command execution
def release_lock(thread_title):
    if thread_title in FILE_LOCKS:
        FILE_LOCKS[thread_title].release()

global_lock = threading.Lock()

#function to load the username and password from the credentials file
def load_credentials():
    credentials = {}
    with open('credentials.txt', 'r') as file:
        for line in file:
            if line.strip() == "":
                continue  #to skip empty lines
            parts = line.strip().split()
            if len(parts) != 2:
                continue  #to skip invalid lines
            username, password = parts
            credentials[username] = password
    return credentials

#to write a new credential into the credentials file
def new_user(username, password): 
     with global_lock:
        with open(CREDENTIALS_FILE, 'a') as file:
            file.write(f"{username} {password}\n")

#to check if a user is already logged in
def is_logged_in(username): 
    return username in LOGGED_IN_USERS

#function to handle all the commands
def handle_authenticated_command(serverSocket, client_address, username, message):
    parts = message.split() #the message is what we input
    if not parts: #empty input
        serverSocket.sendto("Empty command received.".encode(), client_address)
        return
    command = parts[0]

    #creating a new thread - CRT
    if command.startswith("CRT"): 
        if len(parts) != 2: #format check
            serverSocket.sendto("Format: CRT <threadtitle>".encode(), client_address)
        
        thread_title=parts[1] #threadtitle
        thread_file = thread_title
        acquire_lock(thread_title)
        try:
            if os.path.exists(thread_file):
                serverSocket.sendto(f"Thread {thread_title} already exists.".encode(), client_address)
            else:
                #creating a new thread 
                with open(thread_file, 'w') as f:
                    f.write(f"{username}\n")
                serverSocket.sendto(f"Thread {thread_title} created.".encode(), client_address)
                print(f'{username} created thread {thread_title}')
        finally: 
            release_lock(thread_title)

    #to post a new message into a thread - MSG
    elif command == "MSG":
        if len(parts) < 3:
            serverSocket.sendto("Format: MSG <threadtitle> <message>".encode(), client_address)
            return

        thread_title = parts[1]
        msg = " ".join(parts[2:])  #the rest of the message can be multiple words, so need to be combined

        thread_file = thread_title
        acquire_lock(thread_title)
        try:
            if not os.path.exists(thread_file):
                serverSocket.sendto("Error: Thread does not exist.".encode(), client_address)
                return

            with open(thread_file, 'r') as f:
                lines = f.readlines()
                msg_lines = [line for line in lines if re.match(r'^\d+ ', line)]
                msg_num = len(msg_lines) + 1

            with open(thread_file, 'a') as f:
                f.write(f"{msg_num} {username}: {msg}\n")

            serverSocket.sendto(f"Message posted to {thread_title}".encode(), client_address)
            print(f'{username} posted message successfully to {thread_title}')
        finally:
            release_lock(thread_title)

    #to delete a message from a thread - DLT
    elif command == "DLT":
        if len(parts) != 3:
            serverSocket.sendto("Usage: DLT <threadtitle> <messagenumber>".encode(), client_address)
            return

        thread_title = parts[1]
        try:
            msg_num = int(parts[2])
        except ValueError:
            serverSocket.sendto("Error: Message number must be an integer.".encode(), client_address)
            return

        thread_file = thread_title
        acquire_lock(thread_title)
        try:
            if not os.path.exists(thread_file):
                serverSocket.sendto("Error: Thread does not exist.".encode(), client_address)
                return

            with open(thread_file, 'r') as f:
                lines = f.readlines()

            #to find the message by index
            msg_line_indices = [
                idx for idx, line in enumerate(lines)
                if re.match(r'^\d+ ', line)
            ]

            if msg_num <= 0 or msg_num > len(msg_line_indices):
                serverSocket.sendto("Error: Invalid message number.".encode(), client_address)
                return

            #to get the line index
            target_line_index = msg_line_indices[msg_num - 1]
            target_line = lines[target_line_index]

            #user can only delete own message
            if not target_line.startswith(f"{msg_num} {username}:"):
                serverSocket.sendto("Error: You can only delete your own messages.".encode(), client_address)
                return

            #to delete the line
            del lines[target_line_index]

            #to renumber the remaining messages
            new_msg_num = 1
            for i in range(len(lines)):
                if re.match(r'^\d+ ', lines[i]):
                    _, rest = lines[i].split(' ', 1)
                    lines[i] = f"{new_msg_num} {rest}"
                    new_msg_num += 1

            with open(thread_file, 'w') as f:
                f.writelines(lines)

            serverSocket.sendto("Message deleted successfully.".encode(), client_address)
            print(f'{username} deleted message successfully from {thread_title}')
        finally:
            release_lock(thread_title)

        
    #to edit a message in a thread - EDT
    elif command == "EDT":
        if len(parts) < 4:
            serverSocket.sendto("Usage: EDT <threadtitle> <messagenumber> <message>".encode(), client_address)
            return
    
        thread_title = parts[1]
        try:
            msg_num = int(parts[2])
        except ValueError:
            serverSocket.sendto("Error: Message number must be an integer.".encode(), client_address)
            return
    
        new_message = ' '.join(parts[3:])
        thread_file = thread_title
        acquire_lock(thread_title)
        try:
            if not os.path.exists(thread_file):
                serverSocket.sendto("Error: Thread does not exist.".encode(), client_address)
                return
    
            with open(thread_file, 'r') as f:
                lines = f.readlines()
    
            #to get the message line index
            msg_line_indices = [
                idx for idx, line in enumerate(lines)
                if re.match(r'^\d+ ', line)
            ]
    
            if msg_num <= 0 or msg_num > len(msg_line_indices):
                serverSocket.sendto("Error: Invalid message number.".encode(), client_address)
                return
    
            target_line_index = msg_line_indices[msg_num - 1]
            target_line = lines[target_line_index].strip()
    
            if not target_line.startswith(f"{msg_num} {username}:"):
                serverSocket.sendto("Error: You can only edit your own message.".encode(), client_address)
                return
    
            #to replace the old message with the edited message
            lines[target_line_index] = f"{msg_num} {username}: {new_message}\n"
    
            with open(thread_file, 'w') as f:
                f.writelines(lines)
    
            serverSocket.sendto("Message edited successfully.".encode(), client_address)
            print(f'{username}:Message edited successfully.')
        finally:
            release_lock(thread_title)
    

    #to list all the existing threads - LST
    elif command == "LST":
       excluded_files = {CREDENTIALS_FILE, os.path.basename(__file__)} #all the files we cant print

       if len(parts) > 1:
            serverSocket.sendto("Usage: LST".encode(), client_address)
       #to narrow down which files are thread files
       potential_threads = [
           f for f in os.listdir()
           if os.path.isfile(f)
           and f not in excluded_files
           and '.' not in f  #files with no extensions are the thread files
       ]
    
       active_threads = []
    
       for thread_file in potential_threads:
           acquire_lock(thread_file)
           try:
               if os.path.exists(thread_file):  
                   active_threads.append(thread_file)
           finally:
               release_lock(thread_file)
    
       if not active_threads:
           serverSocket.sendto("No active threads.".encode(), client_address)
       else:
           thread_list = "\n".join(active_threads)
           serverSocket.sendto(thread_list.encode(), client_address)
           print("listing threads..")

    
    
    #to read the thread - RDT
    elif command.startswith("RDT"):
        if len(parts) != 2:
            serverSocket.sendto("Usage: RDT <threadtitle>".encode(), client_address)
            return
        thread_title = parts[1]
        thread_file = thread_title
        acquire_lock(thread_title)
        try:
            if not os.path.exists(thread_file):
                serverSocket.sendto("Error: Thread does not exist.".encode(), client_address)
                return
            with open(thread_file, 'r') as f:
                lines = f.readlines()[1:]  #to skip the creators username line
            if not lines:
                serverSocket.sendto("Thread is empty.".encode(), client_address)
            else:
                content = "".join(lines)
                serverSocket.sendto(content.encode(), client_address)
                print(f'reading thread {thread_title}')
        finally:
            release_lock(thread_title)

    
    # to upload a file - UPD
    elif command.startswith("UPD"):
        try:
            thread_title = parts[1]
            filename = parts[2]
        except ValueError:
            serverSocket.sendto("Usage: UPD <threadtitle> <filename>".encode(), client_address)
            return
        
        thread_file = thread_title
        file_path_on_server = f"{thread_title}-{filename}"
        
        acquire_lock(thread_title)
        try:
            if not os.path.exists(thread_file):
                serverSocket.sendto("Error: Thread does not exist.".encode(), client_address)
                return
    
            if os.path.exists(file_path_on_server):
                serverSocket.sendto("Error: File already uploaded to this thread.".encode(), client_address)
                return
    
            #to send confirmation to the client to start the TCP transfer
            serverSocket.sendto("Ready to receive file. Please connect over TCP.".encode(), client_address)
            
            #TCP socket
            tcp_port = 6000  
            tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_server.bind(('localhost', tcp_port))
            tcp_server.listen(1)
            
            #sending port number for connection
            serverSocket.sendto(str(tcp_port).encode(), client_address)
    
            def handle_file_upload():
                tcp_conn, _ = tcp_server.accept()
                with open(file_path_on_server, 'wb') as f:
                    while True:
                        chunk = tcp_conn.recv(BUFFER_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                tcp_conn.close()
                tcp_server.close()
                
                with open(thread_file, 'a') as thread_log:
                    thread_log.write(f"{username} uploaded {filename}\n")
    
                serverSocket.sendto("File uploaded successfully.".encode(), client_address)
    
            # file upload handling is done in a separate thread to prevent server lock
            upload_thread = threading.Thread(target=handle_file_upload)
            upload_thread.start()
    
        finally:
            release_lock(thread_title)
    

    
    # to download a file from a thread - DWN
    elif command.startswith("DWN"):
        try:
            thread_title = parts[1]
            filename = parts[2]
        except ValueError:
            serverSocket.sendto("Usage: DWN <threadtitle> <filename>".encode(), client_address)
            return

        thread_file = thread_title
        file_path_on_server = f"{thread_title}-{filename}"
        acquire_lock(thread_title)
        try:
            if not os.path.exists(thread_file):
                serverSocket.sendto("Error: Thread does not exist.".encode(), client_address)
                

            if not os.path.exists(file_path_on_server):
                serverSocket.sendto("Error: File not found in the specified thread.".encode(), client_address)
                return

            # to notify client to prepare for TCP transfer
            serverSocket.sendto("Ready to send file. Please connect over TCP.".encode(), client_address)

            #TCP setup - in a diff thread
            def handle_file_download():
                tcp_port = 6001  #different port for DWN
                tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_server.bind(('localhost', tcp_port))
                tcp_server.listen(1)

                serverSocket.sendto(str(tcp_port).encode(), client_address)

                tcp_conn, _ = tcp_server.accept()
                with open(file_path_on_server, 'rb') as f:
                    while True:
                        chunk = f.read(BUFFER_SIZE)
                        if not chunk:
                            break
                        tcp_conn.sendall(chunk)
                tcp_conn.close()
                tcp_server.close()

                with open(thread_file, 'a') as thread_log:
                    thread_log.write(f"{username} downloaded {filename}\n")

                serverSocket.sendto("File downloaded successfully.".encode(), client_address)

            #download handling done in separate thread
            download_thread = threading.Thread(target=handle_file_download)
            download_thread.start()
        finally:
            release_lock(thread_title)

    # to remove a thread - RMV
    elif command.startswith("RMV"):
        if len(parts) != 2:
            serverSocket.sendto("Usage: RMV <threadtitle>".encode(), client_address)
            
        thread_title = parts[1]
        thread_file = thread_title
        acquire_lock(thread_title)
        try:
            if not os.path.exists(thread_file):
                serverSocket.sendto("Error: Thread does not exist.".encode(), client_address)

            with open(thread_file, 'r') as f:
                creator = f.readline().strip()
            if creator != username:
                serverSocket.sendto("Error: You can only remove threads you created.".encode(), client_address)
                return

            os.remove(thread_file)
            #to remove the files uploaded to the thread
            for file in os.listdir():
                if file.startswith(f"{thread_title}-"):
                    os.remove(file)
            serverSocket.sendto(f"Thread {thread_title} removed successfully.".encode(), client_address)
            print(f'removing thread{thread_title}')
        finally:
            release_lock(thread_title)
    
    # to exit - XIT
    elif command.startswith("XIT"):
        #to remove the user from the logged in users set
        if username in LOGGED_IN_USERS:
            LOGGED_IN_USERS.remove(username)
    
        #exit confirmation
        serverSocket.sendto("Goodbye.".encode(), client_address)
        print(f"{username} has logged out.")
        return 

    else:
        serverSocket.sendto("Invalid command.".encode(), client_address)



def handle_client(serverSocket, client_address, q):
    username = None
    print(f"[{client_address}] New client connected")

    while True:
        if not username:
            uname_data = q.get()
            uname = uname_data.decode().strip()
            print(f"[{client_address}] Attempting login: {uname}")

            if is_logged_in(uname):
                serverSocket.sendto("username is already being used.".encode(), client_address)
                continue

            credentials = load_credentials()

            if uname in credentials:
                serverSocket.sendto("username is valid.".encode(), client_address)

                #password wait
                password_data = q.get()
                password = password_data.decode().strip()

                if credentials[uname] == password:
                    serverSocket.sendto("password matches. Login Successful".encode(), client_address)
                    username = uname
                    LOGGED_IN_USERS.add(username)
                    print(f"[{username}] Login successful")
                    command_list = (
                    "CRT: Create Thread\nLST: List Threads\nMSG: Post Message\n"
                    "DLT: Delete Message\nRDT: Read Thread\nEDT: Edit Message\n"
                    "UPD: Upload File\nDWN: Download File\nRMV: Remove Thread\nXIT: Exit."
                    )
                    serverSocket.sendto(command_list.encode(), client_address)
                else:
                    serverSocket.sendto("Incorrect password".encode(), client_address)
                    print("Incorrect password")
                    continue
            else:
                serverSocket.sendto("New User.".encode(), client_address) #new user

                new_password_data = q.get()
                new_password = new_password_data.decode().strip()

                new_user(uname, new_password)
                LOGGED_IN_USERS.add(uname)
                username = uname
                serverSocket.sendto("New account created successfully.".encode(), client_address)
                print(f"Account created successfully. {username} logged in.")
                command_list = (
                    "CRT: Create Thread\nLST: List Threads\nMSG: Post Message\n"
                    "DLT: Delete Message\nRDT: Read Thread\nEDT: Edit Message\n"
                    "UPD: Upload File\nDWN: Download File\nRMV: Remove Thread\nXIT: Exit."
                    )
                serverSocket.sendto(command_list.encode(), client_address)
        else:
            #wait for command if alr logged in
            command_data = q.get()
            message = command_data.decode().strip()

            if not message:
                print("not message")
                continue

            handle_authenticated_command(serverSocket, client_address, username, message)


def start_server():
    if len(sys.argv) != 2:
        print("Usage: python3 server.py <port>")
        sys.exit(1)
    try:
        port = int(sys.argv[1])
    except ValueError:
        print("Port number must be an integer.")
        sys.exit(1)
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    serverSocket.bind(('localhost', port))
    print(f'Server started on port {port}')
    print("Waiting for clients...")

    dispatcher_thread = threading.Thread(target=dispatcher, args=(serverSocket,), daemon=True)
    dispatcher_thread.start()
    dispatcher_thread.join()

start_server()


