Matt Sisco - Red Team Tool team Alpha

This tool is a super basic C2 server that 
deploys itself as a service on the target windows boxes with help from nssm



Run ansible-playbook -i inventory.ini deploy_c2_server.yml
 
cd c2_programs
python c2_server.py

should have a command shell on the target hosts listed in inventory.ini

