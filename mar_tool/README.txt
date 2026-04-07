Marissa Ventresca
Team Alpha
mrv7315@rit.edu

What root looks like:
/root/
├── comp/
│   ├── ansible.cfg
│   ├── inventory.ini
│   ├── deploy.yml
│   ├── encrypt_services.py
│   └── comp_logger.py
├── comp_logs/        ← auto-created, logs land here
└── comp_keys/        ← auto-created, per-host keys land here


1. make dirs on jump:
mkdir -p /bin/sys_cache
mkdir -p /root/comp_logs
mkdir -p /root/comp_keys

2. make ssh key on jump box:
ssh-keygen -t ed25519 -f /bin/sys_cache/.key -N ""

3. apt install sshpass -y

4. loop copy it to all the comp boxes:
USA boxes:

for ip in 10.100.2.3 10.100.2.4 10.100.2.5 10.100.2.6 10.100.2.7 10.100.2.8; do
  sshpass -p 'ColdWar123!' ssh-copy-id -i /bin/sys_cache/.key \
    -o StrictHostKeyChecking=no cia@$ip   #also can use herb_brooks, blueteam pass
done

USSR boxes:

for ip in 10.100.3.3 10.100.3.4 10.100.3.5 10.100.3.6 10.100.3.7 10.100.3.8; do
  sshpass -p 'ColdWar123!' ssh-copy-id -i /bin/sys_cache/.key \
    -o StrictHostKeyChecking=no kgb@$ip     #also can use tikhonov, blueteam pass
done

5. ping all boxes with ansible to check for connectivity:
cd /root/comp
ansible all -m ping

should return "pong"

6. install crypto library on all boxes:
ansible all -m pip -a "name=cryptography state=present"

7. deploy logger on all:
ansible-playbook deploy.yml --tags logger

8. look at logs:
tail -f /root/comp_logs/*.log

9. EOD 1 encryption:
ansible-playbook deploy.yml --tags encrypt

10. to decrypt:
ansible-playbook deploy.yml --tags decrypt

11. if blueteam wipes my ssh keys:
# Re-push to a specific box
sshpass -p 'ColdWar123!' ssh-copy-id -i /bin/sys_cache/.key \
  -o StrictHostKeyChecking=no <admin>@<ip>

12. Or re-push to all boxes at once:
for ip in <ip1> <ip2> <ip3>...; do
  sshpass -p 'ColdWar123!' ssh-copy-id -i /bin/sys_cache/.key \
    -o StrictHostKeyChecking=no <admin>@$<ip>
done


