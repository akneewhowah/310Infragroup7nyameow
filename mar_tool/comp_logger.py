#!/usr/bin/env python3
"""
Competition Command & Auth Logger
Monitors:
  - Shell history files (bash/zsh) for command activity
  - /var/log/auth.log for password changes & sudo usage
  - /var/log/syslog for backup-related activity

Usage: sudo python3 comp_logger.py [--logfile output.log]
"""

import time
import os
import re
import argparse
from pathlib import Path
from datetime import datetime

# Config
WATCH_AUTH_LOG = "/var/log/auth.log"   #ubuntu/deb
WATCH_SYSLOG   = "/var/log/syslog"
 
# All competition users from packet
# USA normal:  rob_mclanahan, mark_johnson, ken_morrow, dave_silk,
#              jack_oh_callahan, dave_christian, buzz_schneider, bob_suter
# USA admin:   herb_brooks, jimmy_carter, eruzione, jim_craig, craig_patrick
# USSR normal: zhukov, gusev, makarov, fetisov, kasatonov,
#              krutov, lebedev, vasiliev
# USSR admin:  tikhonov, kulagin, brezhnev, tretiak, larionov
 
COMP_USERS = [
    # USA normal
    "rob_mclanahan", "mark_johnson", "ken_morrow", "dave_silk",
    "jack_oh_callahan", "dave_christian", "buzz_schneider", "bob_suter",
    # USA admin
    "herb_brooks", "jimmy_carter", "eruzione", "jim_craig", "craig_patrick",
    # USSR normal
    "zhukov", "gusev", "makarov", "fetisov", "kasatonov",
    "krutov", "lebedev", "vasiliev",
    # USSR admin
    "tikhonov", "kulagin", "brezhnev", "tretiak", "larionov",
]
 
HISTORY_FILES = (
    ["/root/.bash_history", "/root/.zsh_history"] +
    [f"/home/{u}/.bash_history" for u in COMP_USERS] +
    [f"/home/{u}/.zsh_history" for u in COMP_USERS]
)
POLL_INTERVAL    = 2   

#keywords to look for
PASSWD_KEYWORDS  = re.compile(r"passwd|chpasswd|usermod|useradd|userdel|shadow", re.I)
BACKUP_KEYWORDS  = re.compile(r"rsync|tar|cp -r|scp|backup|dump|snapshot", re.I)
SUDO_KEYWORDS    = re.compile(r"sudo|su\b", re.I)



def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str, logfile):
    line = f"[{ts()}] {msg}"
    print(line)
    if logfile:
        with open(logfile, "a") as f:
            f.write(line + "\n")


def tail_file(path: str, last_pos: dict, label: str, pattern: re.Pattern, logfile):
    """read new lines added to a file since last check"""
    p = Path(path)
    if not p.exists():
        return
    size = p.stat().st_size
    pos  = last_pos.get(path, size)   #start at EOF on first run
    if size < pos:
        pos = 0   #file was rotated
    if size == pos:
        return
    with open(path, "r", errors="replace") as f:
        f.seek(pos)
        for line in f:
            line = line.rstrip()
            if pattern.search(line):
                log(f"[{label}] {line}", logfile)
    last_pos[path] = p.stat().st_size


def resolve_history_globs(patterns):
    paths=[]
    for pat in patterns:
        if "*" in pat:
            import glob
            paths.extend(glob.glob(pat))
        else:
            paths.append(pat)
    return list(set(paths))


def monitor_history(history_paths: list, last_sizes: dict, logfile):
    """detect new lines appended to shell history files"""
    for path in history_paths:
        p = Path(path)
        if not p.exists():
            continue
        size = p.stat().st_size
        pos  = last_sizes.get(path, size)
        if size <= pos:
            last_sizes[path] = size
            continue
        with open(path, "r", errors="replace") as f:
            f.seek(pos)
            for line in f:
                line = line.rstrip()
                if line.startswith("#") or not line:   #zsh timestamps
                    continue
                flag = ""
                if PASSWD_KEYWORDS.search(line):
                    flag = " *** PASSWORD CHANGE ***"
                elif BACKUP_KEYWORDS.search(line):
                    flag = " *** BACKUP ACTIVITY ***"
                elif SUDO_KEYWORDS.search(line):
                    flag = " [sudo]"
                log(f"[HISTORY:{Path(path).parent.name}] {line}{flag}", logfile)
        last_sizes[path] = size


def main():
    parser = argparse.ArgumentParser(description="Competition command & auth logger")
    parser.add_argument("--logfile", default="comp_activity.log", help="Output log file path")
    args = parser.parse_args()

    logfile  = args.logfile
    last_pos = {}       
    hist_pos = {}       

    history_paths = resolve_history_globs(HISTORY_FILES)

    log(f"[*] Logger started. Writing to: {logfile}", logfile)
    log(f"[*] Watching auth log : {WATCH_AUTH_LOG}", logfile)
    log(f"[*] Watching syslog   : {WATCH_SYSLOG}", logfile)
    log(f"[*] History files     : {history_paths}", logfile)

    try:
        while True:
            tail_file(WATCH_AUTH_LOG, last_pos, "AUTH",   PASSWD_KEYWORDS, logfile)
            tail_file(WATCH_SYSLOG,   last_pos, "SYSLOG", BACKUP_KEYWORDS, logfile)
            monitor_history(history_paths, hist_pos, logfile)
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        log("[*] Logger stopped by user.", logfile)


if __name__ == "__main__":
    main()
