My (Rose's) Python client is an HTTPS-based Command & Control (C2) agent. It securely communicates with Andrew's central 
C2 server to receive and execute tasks, report results, and maintain persistence on Linux hosts. This client uses 
randomized headers, service detection, and configurable sleep/jitter intervals to operate stealthily.