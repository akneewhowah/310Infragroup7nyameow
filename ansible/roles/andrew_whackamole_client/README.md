# andrew_whackamole_client

Ansible to deploy the Whackamole agent example. Usage (from Ansible root directory): ansible-playbook playbook.yaml -i inventory.yaml -t whackamole_client

Customize deployment variables in defaults/main.yaml (or override those variables with your own elsewhere).

See files/agent.py for the example agent source code and instructions for how to use the agent as a reference to implementing support for the Whackamole server in your tool.

This agent is not intended to be deployed in a live environment due to its basic nature as it is primarily a learning tool. However, it is fully functional as a basic C2 implementation using the Whackamole server, and can be deployed as such if really desired.

See the Whackamole Server API instructions document and comments inside agent.py for more information.