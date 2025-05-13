import socket
import sys

def get_input(prompt):
    return input(prompt).strip()

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 client.py <server port>")
        sys.exit(1)

    try:
        port = int(sys.argv[1])
    except ValueError:
        print("Error: Port must be an integer.")
        sys.exit(1)

    server_address = ('localhost', port)
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    while True:
        #login prompt
        username = get_input("Enter username: ")
        clientSocket.sendto(username.encode(), server_address)

        response, _ = clientSocket.recvfrom(1024)
        response = response.decode()
        print(f"Server: {response}")

        if response == "username is already being used.":
            continue

        if response == "username is valid.":
            password = get_input("Enter password: ")
            clientSocket.sendto(password.encode(), server_address)

            login_result, _ = clientSocket.recvfrom(1024)
            login_result = login_result.decode()
            print(f"Server: {login_result}")

            if login_result == "password matches. Login Successful":
                break  
            else:
                print("Try again.\n")
                continue

        if response == "New User.":
            password = get_input("Set a password for your new account: ")
            clientSocket.sendto(password.encode(), server_address)

            confirmation, _ = clientSocket.recvfrom(1024)
            print(f"Server: {confirmation}")
            break 

    command_list, _ = clientSocket.recvfrom(1024)
    print("\nAvailable Commands:")
    print(command_list.decode())

    while True:
        user_input = get_input("\nEnter command: ")

        if user_input.startswith("CRT"):
            clientSocket.sendto(user_input.encode(), server_address)
            server_reply, _ = clientSocket.recvfrom(1024)
            print(f"Server: {server_reply.decode()}")

        elif user_input.startswith("MSG"):
            parts = user_input.split(' ', 2)
            if len(parts) < 3:
                print("Usage: MSG <threadtitle> <message>")
                continue
            clientSocket.sendto(user_input.encode(), server_address)
            server_reply, _ = clientSocket.recvfrom(1024)
            print(f"Server: {server_reply.decode()}")

        elif user_input.startswith("DLT"):
            parts = user_input.split()
            if len(parts) != 3:
                print("Usage: DLT <threadtitle> <messagenumber>")
                continue
            clientSocket.sendto(user_input.encode(), server_address)
            server_reply, _ = clientSocket.recvfrom(1024)
            print(f"Server: {server_reply.decode()}")

        elif user_input.startswith("EDT"):
            parts = user_input.split(' ', 3)
            if len(parts) < 4:
                print("Usage: EDT <threadtitle> <messagenumber> <message>")
                continue
            clientSocket.sendto(user_input.encode(), server_address)
            server_reply, _ = clientSocket.recvfrom(1024)
            print(f"Server: {server_reply.decode()}")

        elif user_input.strip() == "LST":
            clientSocket.sendto(user_input.encode(), server_address)
            server_reply, _ = clientSocket.recvfrom(1024)
            print("Server:\n" + server_reply.decode())

        elif user_input.startswith("RDT"):
            parts = user_input.split()
            if len(parts) != 2:
                print("Usage: RDT <threadtitle>")
                continue

            clientSocket.sendto(user_input.encode(), server_address)
            server_reply, _ = clientSocket.recvfrom(1024)
            print(f"\nThread Contents:\n{server_reply.decode()}")


        #UPD
        elif user_input.startswith("UPD"):
            parts = user_input.split()
            if len(parts) != 3:
                print("Usage: UPD <threadtitle> <filename>")
                continue

            _, thread_title, filename = parts

            try:
                with open(filename, 'rb') as f:
                    file_data = f.read()
            except FileNotFoundError:
                print(f"Error: File '{filename}' not found.")
                continue

            #to send upload command over UDP
            clientSocket.sendto(user_input.encode(), server_address)
            response, _ = clientSocket.recvfrom(1024)
            decoded = response.decode() #first response - ready to recieve

            if not decoded.startswith("Ready to receive"):
                print(f"Server: {decoded}")
                continue

            print(f"Server: {decoded}")

            port_response, _ = clientSocket.recvfrom(1024)
            try:
                tcp_port = int(port_response.decode())
            except ValueError:
                print(f"Unexpected port value: {port_response.decode()}")
                continue

            print(f"Connecting to TCP port {tcp_port} to upload file...")

            #TCP connection and file upload
            try:
                tcpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcpSocket.connect(('localhost', tcp_port))
                tcpSocket.sendall(file_data)
                tcpSocket.close()
                print("File upload complete.")
            except Exception as e:
                print(f"Error during TCP file upload: {e}")
                continue

            #final confirmation - UDP
            confirmation, _ = clientSocket.recvfrom(1024)
            print(f"Server: {confirmation.decode()}")

        elif user_input.startswith("DWN"):
            parts = user_input.split()
            if len(parts) != 3:
                print("Usage: DWN <threadtitle> <filename>")
                continue

            _, thread_title, filename = parts


            clientSocket.sendto(user_input.encode(), server_address)

            response, _ = clientSocket.recvfrom(1024)
            decoded = response.decode()

            if not decoded.startswith("Ready to send"):
                print(f"Server: {decoded}")
                continue

            print(f"Server: {decoded}")

            port_response, _ = clientSocket.recvfrom(1024)
            try:
                tcp_port = int(port_response.decode())
            except ValueError:
                print(f"Unexpected port value: {port_response.decode()}")
                continue

            print(f"Connecting to TCP port {tcp_port} to download file...")

            # file download over tcp connection
            try:
                tcpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcpSocket.connect(('localhost', tcp_port))

                #file data
                file_data = b""
                while True:
                    chunk = tcpSocket.recv(4096)
                    if not chunk:
                        break
                    file_data += chunk
                tcpSocket.close()

                #save file
                with open(filename, 'wb') as f:
                    f.write(file_data)

                print(f"File '{filename}' downloaded successfully.")
            except Exception as e:
                print(f"Error during TCP file download: {e}")
                continue

            #udp confirmation
            confirmation, _ = clientSocket.recvfrom(1024)
            print(f"Server: {confirmation.decode()}")


        elif user_input.startswith("RMV"):
            parts = user_input.split()
            if len(parts) != 2:
                print("Usage: RMV <threadtitle>")
                continue

            clientSocket.sendto(user_input.encode(), server_address)
            server_reply, _ = clientSocket.recvfrom(1024)
            print(f"Server: {server_reply.decode()}")

        elif user_input.strip() == "XIT":
            clientSocket.sendto(user_input.encode(), server_address)
            server_reply, _ = clientSocket.recvfrom(1024)
            print(f"Server: {server_reply.decode()}")
            print("Exiting...")
            break

        else:
            print("Invalid Command")

    clientSocket.close()

if __name__ == "__main__":
    main()
