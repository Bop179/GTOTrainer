#!/usr/bin/env python3
"""Public custom-spot API. Run behind Caddy; see README for systemd setup.
A separate binary and temporary job directory keep the batch solver untouched.
"""
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY = 32768
MAX_RESULT = 64 * 1024 * 1024
SIZES = {'flop_sizes':['33%, 75%', '2.5x'], 'turn_sizes':['75%, 125%', '2.5x'], 'river_sizes':['75%', '2.5x']}


def validate(data):
    if not isinstance(data, dict) or set(data) - {'board','pot','stack','oop','ip','request_id',*SIZES}:
        raise ValueError('Unknown solve fields')
    board = data.get('board', '')
    if not isinstance(board,str) or not re.fullmatch(r'(?:[2-9TJQKA][cdhs]){3,5}',board):
        raise ValueError('Board must contain 3, 4 or 5 cards, e.g. Ks7d2c')
    if len(set(re.findall('..',board))) != len(board)//2:
        raise ValueError('Board cards must be unique')
    j = {'board':board}
    for key in ('pot','stack'):
        v=data.get(key)
        if type(v) not in (int,float) or not math.isfinite(v) or not .05 <= v <= 2000:
            raise ValueError(key+' must be between 0.05 and 2000 bb')
        j[key]=round(v*20)/20
    for key in ('oop','ip'):
        v=data.get(key)
        if not isinstance(v,str) or not 1 <= len(v.strip()) <= 12000 or not v.isascii():
            raise ValueError(key+' must be a range string (up to 12000 characters)')
        j[key]=v.strip()
    for key, default in SIZES.items():
        v=data.get(key,default)
        if not isinstance(v,list) or len(v)!=2 or not all(isinstance(s,str) for s in v):
            raise ValueError(key+' must contain bets and raises')
        bets=[s.strip() for s in v[0].split(',')]
        if not 1<=len(bets)<=3 or any(not re.fullmatch(r'\d+(?:\.\d+)?%',s) or not 10<=float(s[:-1])<=200 for s in bets):
            raise ValueError('Use 1 to 3 bet sizes between 10% and 200%')
        if not re.fullmatch(r'[2-4](?:\.\d+)?x',v[1]) or not 2<=float(v[1][:-1])<=4:
            raise ValueError('Raise size must be between 2x and 4x')
        j[key]=[', '.join(bets),v[1]]
    rid=data.get('request_id',secrets.token_hex(16))
    if not isinstance(rid,str) or not re.fullmatch('[a-f0-9]{32}',rid):
        raise ValueError('Invalid request ID')
    j.update(compress=True,max_gb=12,target=.01,max_iter=1000,min_reach=0,starting_street_only=True)
    return j


def available_gb():
    # Production runs on Linux. Fail closed if the memory guard cannot be read.
    try:
        lines=Path('/proc/meminfo').read_text().splitlines()
        return next(int(s.split()[1])/1024**2 for s in lines if s.startswith('MemAvailable:'))
    except (OSError,StopIteration,ValueError):
        return 0


class APIError(Exception):
    def __init__(self,status,message): self.status,self.message=status,message


class Jobs:
    def __init__(self,command,root,timeout=1800,available=available_gb):
        self.command,self.root,self.timeout,self.available=command,Path(root),timeout,available
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.jobs={}
        self.lock=threading.RLock()

    def cleanup(self):
        for id,j in list(self.jobs.items()):
            if j['state']!='running' and time.time()-j['finished']>7200:
                shutil.rmtree(j['dir']); del self.jobs[id]

    def submit(self,data):
        spec=validate(data)
        id=data.get('request_id') or secrets.token_hex(16)
        with self.lock:
            self.cleanup()
            if id in self.jobs:
                if self.jobs[id]['input']!=spec: raise APIError(409,'Request ID already used for another spot')
                return self.status(id)
            if any(j['state']=='running' for j in self.jobs.values()):
                raise APIError(409,'The server is solving another spot. Try again when it finishes.')
            if len(self.jobs)>=32:
                oldest=min(self.jobs,key=lambda k:self.jobs[k]['finished'])
                shutil.rmtree(self.jobs[oldest]['dir']); del self.jobs[oldest]
            if self.available()<15: raise APIError(503,'The server is busy: less than 15 GB RAM available. Try again later.')
            if shutil.disk_usage(self.root).free < 1024**3: raise APIError(503,'The server is low on disk space.')
            d=self.root/id; d.mkdir(mode=0o700)
            (d/'input.json').write_text(json.dumps(spec))
            try:
                with (d/'error.log').open('wb') as err:
                    proc=subprocess.Popen([*self.command,str(d/'input.json'),str(d/'result.json')],
                        stdout=subprocess.DEVNULL,stderr=err,env={**os.environ,'RAYON_NUM_THREADS':'4'})
            except OSError:
                shutil.rmtree(d); raise APIError(503,'The solver could not start.')
            j=dict(id=id,state='running',started=time.time(),input=spec,dir=d,process=proc)
            self.jobs[id]=j
            thread=threading.Thread(target=self.finish,args=(id,),daemon=True)
            j['thread']=thread; thread.start()
            return self.status(id)

    def finish(self,id):
        j=self.jobs[id]; proc=j['process']; error=None
        deadline=time.monotonic()+self.timeout
        while proc.poll() is None:
            if time.monotonic()>deadline: error='Solve exceeded the 30-minute time limit. Try fewer bet sizes.'
            for name,limit in [('result.json',MAX_RESULT),('error.log',1024**2)]:
                try:
                    if (j['dir']/name).stat().st_size>limit: error='Solve output exceeded the size limit. Try fewer bet sizes.'
                except FileNotFoundError: pass
            if error: proc.kill(); break
            time.sleep(.05)
        proc.wait()
        with self.lock:
            if j['state']=='cancelled': return
            if proc.returncode!=0 and not error:
                log=(j['dir']/'error.log').read_text(errors='replace')[-2000:].strip()
                error=log or 'Solver stopped (possibly its memory limit). Try fewer bet sizes or narrower ranges.'
            path=j['dir']/'result.json'
            if not error:
                if not path.exists() or path.stat().st_size>MAX_RESULT: error='Solver produced no result or exceeded the result size limit.'
                else:
                    try:
                        out=json.loads(path.read_bytes())
                        if not isinstance(out.get('nodes'),dict) or '' not in out['nodes']: error='Solver produced no root strategy.'
                    except (ValueError,AttributeError): error='Solver produced an invalid result.'
            j.update(state='failed' if error else 'done',finished=time.time())
            if error:
                j['error']=error
                path.unlink(missing_ok=True)

    def get(self,id):
        self.cleanup()
        if id not in self.jobs: raise APIError(404,'Solve not found (expired or server restarted). Submit the spot again.')
        return self.jobs[id]

    def status(self,id):
        with self.lock:
            j=self.get(id)
            return {k:v for k,v in j.items() if k in ('id','state','started','finished','input','error')}

    def result(self,id):
        with self.lock:
            j=self.get(id)
            if j['state']!='done': raise APIError(409,'Result is not ready')
            return (j['dir']/'result.json').read_bytes()

    def cancel(self,id):
        with self.lock:
            j=self.get(id)
            if j['state']=='running':
                j['state']='cancelled'; j['finished']=time.time()
                if j['process'].poll() is None: j['process'].kill()
                j['process'].wait()
                (j['dir']/'result.json').unlink(missing_ok=True)
            return self.status(id)

    def close(self):
        for id in list(self.jobs): self.cancel(id)
        for j in self.jobs.values(): j['thread'].join(timeout=5)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup(); self.connection.settimeout(10)
    def log_message(self,*args): pass  # don't log job IDs or ranges
    def reply(self,status,body=None):
        raw=body if isinstance(body,bytes) else json.dumps(body).encode() if body is not None else b''
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store')
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.send_header('Access-Control-Allow-Methods','GET, POST, DELETE, OPTIONS')
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers(); self.wfile.write(raw)
    def do_OPTIONS(self): self.reply(204)
    def handle_api(self):
        try:
            path=self.path
            if self.command=='GET' and path=='/solve/health':
                return self.reply(200,{'ok':True,'max_gb':12,'timeout_seconds':1800})
            if self.command=='POST' and path=='/solve/jobs':
                if self.headers.get('Content-Type','').split(';')[0]!='application/json': raise APIError(415,'Send JSON')
                try: length=int(self.headers.get('Content-Length','0'))
                except ValueError: raise APIError(400,'Invalid body length')
                if not 0<length<=MAX_BODY: raise APIError(413,'Request must be at most 32 KB')
                data=json.loads(self.rfile.read(length))
                return self.reply(202,self.server.jobs.submit(data))
            match=re.fullmatch(r'/solve/jobs/([a-f0-9]{32})(/result)?',path)
            if not match: raise APIError(404,'Unknown API route')
            id,result=match.groups()
            if self.command=='GET': return self.reply(200,self.server.jobs.result(id) if result else self.server.jobs.status(id))
            if self.command=='DELETE' and not result: return self.reply(200,self.server.jobs.cancel(id))
            raise APIError(405,'Method not allowed')
        except APIError as e: self.reply(e.status,{'error':e.message})
        except (ValueError,UnicodeError) as e: self.reply(400,{'error':str(e)})
        except (BrokenPipeError,ConnectionResetError,TimeoutError): pass
        except Exception:
            self.reply(500,{'error':'Server error; retry or contact the server owner.'})
    do_GET=do_POST=do_DELETE=handle_api


class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,jobs):
        self.jobs=jobs
        self.slots=threading.BoundedSemaphore(16)
        super().__init__(address,Handler)
    def process_request(self,request,client_address):
        if not self.slots.acquire(blocking=False): request.close(); return
        try: super().process_request(request,client_address)
        except Exception: self.slots.release(); raise
    def process_request_thread(self,request,client_address):
        try: super().process_request_thread(request,client_address)
        finally: self.slots.release()


if __name__=='__main__':
    binary=os.environ.get('GTO_SOLVER_BIN',str(Path(__file__).parent/'target/release/gto-solve'))
    # Ephemeral private results disappear on service restart and never enter the public post/ tree.
    with tempfile.TemporaryDirectory(prefix='gto-custom-') as root:
        jobs=Jobs([binary],root)
        server=Server(('127.0.0.1',int(os.environ.get('GTO_SOLVER_PORT','8081'))),jobs)
        try: server.serve_forever()
        finally: jobs.close(); server.server_close()
