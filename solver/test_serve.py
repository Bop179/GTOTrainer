import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import serve

JOB = dict(board='Ks7d2c5h9s', pot=20, stack=80, oop='AA,QQ', ip='KK,JJ',
           flop_sizes=['33%, 75%', '2.5x'], turn_sizes=['75%', '2.5x'], river_sizes=['75%', '2.5x'])

class Validation(unittest.TestCase):
    def test_server_owns_resource_limits(self):
        j = serve.validate(JOB)
        self.assertEqual(j['max_gb'], 12)
        self.assertTrue(j['compress'] and j['starting_street_only'])
        for key, value in [('board','AhAh2c'), ('board','éééé'), ('pot',True), ('pot',float('nan')),
                           ('stack',0), ('oop',''), ('ip',{'AhKh':1}), ('max_gb',100),
                           ('flop_sizes',['1%', '1.01x']), ('river_sizes',['75%']), ('request_id','../x')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                serve.validate(dict(JOB, **{key:value}))

class Service(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.script = Path(self.tmp.name)/'fake.py'
        self.script.write_text('import json,sys,time\nj=json.load(open(sys.argv[1]))\nsys.exit(1) if j["pot"]==22 else None\ntime.sleep(0.3 if j["pot"]==20 else 5)\njson.dump({"board":j["board"],"nodes":{"":{}}},open(sys.argv[2],"w"))\n')
        self.manager = serve.Jobs([sys.executable, str(self.script)], Path(self.tmp.name)/'jobs', timeout=2, available=lambda:32)
        self.server = serve.Server(('127.0.0.1',0), self.manager)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
    def tearDown(self):
        self.manager.close()
        self.server.shutdown(); self.server.server_close(); self.tmp.cleanup()
    def req(self, method, path, body=None, token='test-secret'):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        c.request(method,path,json.dumps(body) if body is not None else None,
                  {'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        r=c.getresponse(); data=r.read(); c.close()
        return r.status, json.loads(data) if data else None
    def wait(self, id):
        for _ in range(100):
            _, j=self.req('GET','/solve/jobs/'+id)
            if j['state']!='running': return j
            time.sleep(.03)
        self.fail('job did not finish')
    def test_public_access_and_preflight(self):
        self.assertEqual(self.req('GET','/solve/health',token='')[0],200)
        self.assertEqual(self.req('OPTIONS','/solve/jobs',token='')[0],204)
        code,j=self.req('POST','/solve/jobs',JOB,token='')
        self.assertEqual(code,202)
        self.assertEqual(self.req('DELETE','/solve/jobs/'+'f'*32,token='')[0],404)
        self.req('DELETE','/solve/jobs/'+j['id'],token='')
    def test_completion_capacity_idempotence_and_results(self):
        job=dict(JOB,request_id='a'*32)
        code,j=self.req('POST','/solve/jobs',job); self.assertEqual(code,202)
        self.assertEqual(self.req('POST','/solve/jobs',job)[1]['id'],j['id'])
        self.assertEqual(self.req('POST','/solve/jobs',dict(JOB,pot=21))[0],409)
        self.assertEqual(self.req('GET','/solve/jobs/'+j['id']+'/result')[0],409)
        done=self.wait(j['id']); self.assertEqual(done['state'],'done')
        code,out=self.req('GET','/solve/jobs/'+j['id']+'/result'); self.assertEqual(code,200)
        self.assertEqual(out['board'],JOB['board'])
        self.assertEqual(self.req('GET','/solve/jobs/'+j['id']+'/result',token='')[0],200)
    def test_cancel_reaps_process_and_releases_slot(self):
        _,j=self.req('POST','/solve/jobs',dict(JOB,pot=21))

        self.req('DELETE','/solve/jobs/'+j['id'])
        self.assertEqual(self.wait(j['id'])['state'],'cancelled')
        self.assertIsNotNone(self.manager.jobs[j['id']]['process'].poll())
        self.assertEqual(self.req('POST','/solve/jobs',JOB)[0],202)
    def test_timeout_and_low_memory(self):
        self.manager.timeout=.1
        _,j=self.req('POST','/solve/jobs',dict(JOB,pot=21))
        self.assertEqual(self.wait(j['id'])['state'],'failed')
        self.manager.available=lambda:2
        self.assertEqual(self.req('POST','/solve/jobs',JOB)[0],503)
    def test_old_results_do_not_block_public_access(self):
        first=None
        for _ in range(32):
            code,j=self.req('POST','/solve/jobs',dict(JOB,pot=22))
            self.assertEqual(code,202)
            first=first or j['id']
            self.assertEqual(self.wait(j['id'])['state'],'failed')
        self.assertEqual(self.req('POST','/solve/jobs',JOB)[0],202)
        self.assertEqual(self.req('GET','/solve/jobs/'+first)[0],404)

    def test_bad_body_and_unknown_job(self):
        self.assertEqual(self.req('POST','/solve/jobs',dict(JOB,board='AhAh2c'))[0],400)
        self.assertEqual(self.req('GET','/solve/jobs/'+'f'*32)[0],404)

if __name__=='__main__': unittest.main()
