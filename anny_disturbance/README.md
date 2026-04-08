# Terminal Disruption Tool (Bad Apple ASCII)

## Overview
This project is a terminal-based disruption tool designed for use in red team environments. It deploys an ASCII-rendered of bad apple that automatically runs whenever a user opens a terminal session, interfering with usability and slowing down defensive response actions.
---

## Features
- Automatically executes on every terminal session
- ASCII-rendered video playback inside the terminal
- Dynamic scaling to match terminal size
- Interactive controls:
  - Ctrl + L → red team kill switch
  - Ctrl + C → requires multiple attempts to terminate
- Runs using a self-contained Python virtual environment
- Fully deployable across multiple machines using Ansible


## Deployment (Ansible)

### 1. Configure Inventory
Create an `inventory.ini` file:

```
[ubuntu_vms]
192.168.1.20
192.168.1.141

[ubuntu_vms:vars]
ansible_user=cyberrange
ansible_ssh_pass=YOUR_PASSWORD
ansible_become_pass=YOUR_PASSWORD
ansible_become=yes
```

---

### 2. Run Playbook

```
ansible-playbook -i inventory.ini playbook.yml
```

This will:
- Install dependencies
- Create a virtual environment
- Deploy scripts and video
- Configure automatic execution on terminal startup

---

## How It Works
1. Ansible deploys files to the target system
2. A script is placed in `/etc/profile.d/`
3. `/etc/bash.bashrc` is configured to source the script
4. On terminal launch:
   - The script runs
   - The ASCII animation plays automatically

---

## Controls
- Ctrl + L → Immediately exit animation  
- Ctrl + C → Requires multiple presses to terminate  

---

## Notes
- The animation scales dynamically based on terminal size
- Runs once per session to avoid excessive resource usage
- Works in both SSH and local terminal sessions

---

## Author
Anny Hua
Team Alpha

---

## Disclaimer
This tool is intended for educational use in controlled cybersecurity environments only. Do not use on systems without authorization.