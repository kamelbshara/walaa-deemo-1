import http.cookiejar
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server

class ClassroomTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        server.DB=Path(cls.temp.name)/'test.sqlite3'
        server.initialize()
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.http.login_attempts={}
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.http.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.temp.cleanup()
    def client(self):
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def req(self,c,path,data=None):
        r=urllib.request.Request(self.base+'/api/'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
        with c.open(r) as res:return json.load(res)
    def teacher(self):
        c=self.client();self.req(c,'login',{'role':'teacher','username':'walaa','password':'uae123'});return c
    def student(self):
        c=self.client();self.req(c,'login',{'name':'Test learner','code':'WALAA9'});return c
    def test_auth_and_private_data(self):
        c=self.client()
        with self.assertRaises(urllib.error.HTTPError) as e:self.req(c,'dashboard')
        self.assertEqual(e.exception.code,401)
        s=self.student()
        with self.assertRaises(urllib.error.HTTPError) as e:self.req(s,'dashboard')
        self.assertEqual(e.exception.code,404)
        with self.assertRaises(urllib.error.HTTPError):c.open(self.base+'/server.py')
        with self.assertRaises(urllib.error.HTTPError):c.open(self.base+'/.classroom/classroom.sqlite3')
    def test_two_device_work_feedback_pace(self):
        t,s=self.teacher(),self.student()
        sid=self.req(s,'state')['student']['id']
        self.req(s,'work',{'reasoning':'1 favorable out of 2.','strokes':[[[.1,.1],[.5,.6]]],'help':True})
        d=self.req(t,'dashboard');work=next(w for w in d['work'] if w['student']==sid)
        self.assertEqual(work['help'],1);self.assertIn('favorable',work['reasoning'])
        self.req(t,'feedback',{'student':sid,'feedback':'Good sample space. Now explain fairness.'})
        d=self.req(s,'classroom');self.assertEqual(d['work']['help'],0);self.assertIn('fairness',d['work']['feedback'])
        self.req(t,'control',{'mode':'teacher','slide':3})
        self.assertEqual(self.req(s,'classroom')['control'],{'mode':'teacher','slide':3})
        self.req(t,'control',{'mode':'student','slide':0})
    def test_video_first_response_and_hidden_key(self):
        t,s=self.teacher(),self.student()
        self.req(t,'lesson',{'videoId':'abcdefghijk','checkpoints':[{'at':20,'en':'Outcomes?','ar':'كم عدد النواتج؟','options':['1','2','3','4'],'correct':1}]})
        l=self.req(s,'state')['lesson'];cp=l['checkpoints'][0]
        self.assertNotIn('correct',cp)
        r=self.req(s,'video-answer',{'id':cp['id'],'choice':0});self.assertFalse(r['correct'])
        r=self.req(s,'video-answer',{'id':cp['id'],'choice':1});self.assertFalse(r['correct'])
    def test_quiz_scoring_duplicate_and_completion(self):
        s=self.student();a=self.req(s,'start',{'mode':'race'})
        ids=[]
        for i in range(10):
            q=a['question'];ids.append(q['id'])
            self.assertNotIn('correct',q)
            r=self.req(s,'answer',{'attempt':a['id'],'index':a['index'],'choice':server.BANK[q['id']]['correct']})
            self.assertTrue(r['feedback']['correct'])
            if i==0:
                duplicate=self.req(s,'answer',{'attempt':a['id'],'index':0,'choice':0})
                self.assertEqual(duplicate['attempt']['index'],1)
            a=r['attempt']
        self.assertEqual(len(set(ids)),10)
        self.assertTrue(a['finished']);self.assertEqual(a['correct'],10);self.assertEqual(a['percent'],100)
        self.assertGreaterEqual(a['points'],1000);self.assertLessEqual(a['points'],2000)
        self.assertTrue(all('correctAnswer' in q for q in a['review']))
        self.assertEqual(self.req(s,'start',{'mode':'race'})['id'],a['id'])
    def test_expiration_mastery_threshold_and_retry(self):
        s=self.student();a=self.req(s,'start',{'mode':'mastery'})
        for i in range(12):
            if a.get('waiting'):a=self.req(s,'resume',{'attempt':a['id']})
            q=a['question'];correct=server.BANK[q['id']]['correct'];choice=correct if i<10 else (correct+1)%4
            a=self.req(s,'answer',{'attempt':a['id'],'index':i,'choice':choice})['attempt']
        self.assertTrue(a['mastered']);self.assertEqual(a['percent'],83.3)
        nxt=self.req(s,'start',{'mode':'mastery'});self.assertNotEqual(a['id'],nxt['id'])
        with server.connect() as db:db.execute('UPDATE attempts SET current_started=? WHERE id=?',(time.time()-481,nxt['id']))
        state=self.req(s,'state');expired=next(x for x in state['attempts'] if x['id']==nxt['id'])
        self.assertTrue(expired['finished']);self.assertEqual(expired['correct'],0);self.assertFalse(expired['mastered']);self.assertEqual(len(expired['review']),12)
    def test_progress_poll_and_persistent_session(self):
        s=self.student();self.req(s,'progress',{'slide':6});self.req(s,'coin',{'choice':1});self.req(s,'poll',{'choice':2})
        row=self.req(s,'state')['student'];self.assertEqual(row['slide'],6);self.assertEqual(row['poll'],2);self.assertEqual(row['coin'],1);self.assertIn(6,json.loads(row['visited']))
        self.req(s,'logout',{})
        with self.assertRaises(urllib.error.HTTPError):self.req(s,'state')
    def test_worked_examples_progress_and_validation(self):
        s,t=self.student(),self.teacher()
        sid=self.req(s,'state')['student']['id']
        for kind,answer in [('coin','1/2'),('dice','3/6'),('spinner','1/4')]:
            for step in range(5):self.req(s,'explore',{'kind':kind,'step':step})
            wrong=self.req(s,'explore',{'kind':kind,'step':4,'answer':'0'})
            self.assertFalse(wrong['answerCorrect'])
            right=self.req(s,'explore',{'kind':kind,'step':4,'answer':answer})
            self.assertTrue(right['answerCorrect'])
            self.assertEqual(right['exploration']['tries'],2)
            self.assertEqual(len(json.loads(right['exploration']['seen'])),5)
        self.assertEqual(len(self.req(s,'state')['explorations']),3)
        observed=[e for e in self.req(t,'dashboard')['explorations'] if e['student']==sid]
        self.assertEqual(len(observed),3)
        self.assertTrue(all(e['correct']==1 for e in observed))
        with self.assertRaises(urllib.error.HTTPError):self.req(s,'explore',{'kind':'invalid','step':0})

    def test_bank_integrity_and_limits(self):
        self.assertEqual(len(server.BANK),37)
        for q in server.BANK:
            self.assertEqual(len(q['choices']),4)
            self.assertEqual(len({eval(x,{'__builtins__':{}}) for x in q['choices']}),4)
            self.assertIn(q['correct'],range(4));self.assertTrue(q['ar'])
        s=self.student()
        with self.assertRaises(urllib.error.HTTPError):self.req(s,'work',{'reasoning':'bad','strokes':[[[2,-1]]]})
        t=self.teacher();self.req(t,'reflection',{'content':'Actual teaching reflection.'})
        self.assertEqual(self.req(t,'dashboard')['reflection'],'Actual teaching reflection.')

if __name__=='__main__':unittest.main(verbosity=2)
