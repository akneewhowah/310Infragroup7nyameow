Sohan Patel - Red Team Tool 

This tool is a  Python C2 that deploys an agent to target Windows boxes and gives you a remote command shell over HTTP.



Usage
Start the C2 server on your Kali box:
python3 c2/c2server.py
Deploy the agent to targets:
ansible-playbook -i inventory.ini deploy.yml
Open the operator shell:
python3 c2/c2_operator.py
Type agents to see who checked in, use <id> to get a shell on that box.ShareContentpdfpdf[NEW] CSEC473-Homework-4.docx96 linesdocx