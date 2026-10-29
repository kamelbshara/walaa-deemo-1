"""Probability Studio: dependency-free classroom server (Python 3.10+)."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('CLASSROOM_DATA_DIR', str(ROOT / '.classroom')))
if not os.environ.get('DATABASE_URL') and not os.environ.get('VERCEL'):
    DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'classroom.sqlite3'
PASSWORD = os.environ.get('TEACHER_PASSWORD', 'uae123')
CLASS_CODE = os.environ.get('CLASS_CODE', 'WALAA9').upper()


def connect():
    if os.environ.get('DATABASE_URL'):
        from postgres_store import Database
        return Database(os.environ['DATABASE_URL'])
    if os.environ.get('VERCEL'):
        raise RuntimeError('Persistent DATABASE_URL is required on Vercel.')
    db = sqlite3.connect(DB, timeout=15)
    db.row_factory = sqlite3.Row
    return db


def initialize():
    with connect() as db:
        db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS students(id TEXT PRIMARY KEY, name TEXT NOT NULL, created REAL, seen REAL, slide INTEGER DEFAULT 0, poll INTEGER, coin INTEGER, video TEXT DEFAULT '{}', visited TEXT DEFAULT '[0]');
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, role TEXT, student TEXT, expires REAL);
        CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY, student TEXT, mode TEXT, questions TEXT, answers TEXT DEFAULT '[]', current_started REAL, finished INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS work_samples(student TEXT, slide INTEGER, reasoning TEXT, strokes TEXT, updated REAL, PRIMARY KEY(student,slide));
        CREATE TABLE IF NOT EXISTS explorations(student TEXT, kind TEXT, step INTEGER DEFAULT 0, seen TEXT DEFAULT '[0]', correct INTEGER DEFAULT 0, tries INTEGER DEFAULT 0, updated REAL, PRIMARY KEY(student,kind));
        CREATE TABLE IF NOT EXISTS reflections(id INTEGER PRIMARY KEY CHECK(id=1), content TEXT DEFAULT '');
        INSERT OR IGNORE INTO reflections VALUES(1,'');
        CREATE TABLE IF NOT EXISTS work(student TEXT PRIMARY KEY, reasoning TEXT DEFAULT '', strokes TEXT DEFAULT '[]', feedback TEXT DEFAULT '', help INTEGER DEFAULT 0, updated REAL);
        ''')
        if 'waiting' not in [r[1] for r in db.execute('PRAGMA table_info(attempts)')]:
            db.execute('ALTER TABLE attempts ADD COLUMN waiting INTEGER DEFAULT 0')
        db.execute("INSERT OR IGNORE INTO settings VALUES('control', ?)", (json.dumps({'mode':'student','slide':0}),))
        db.execute("INSERT OR IGNORE INTO settings VALUES('lesson', ?)", ((ROOT/'lesson-video.json').read_text(),))


def make_bank():
    bank = []
    def add(kind, en, ar, numerator, denominator, visual, detail):
        value = numerator / denominator
        candidates = [(numerator, denominator), (0, 1), (1, 1), (1, 2), (1, 6), (1, 4), (3, 4), (1, 3), (2, 3), (5, 6), (1, 8)]
        choices, values = [], []
        for n, d in candidates:
            if not any(abs(n/d - x) < 1e-8 for x in values):
                choices.append(f'{n}/{d}' if d != 1 else str(n))
                values.append(n/d)
            if len(choices) == 4:
                break
        # Rotate correct answer so it is not always the first option.
        offset = len(bank) % 4
        choices = choices[offset:] + choices[:offset]
        bank.append({'id': len(bank), 'kind': kind, 'en': en, 'ar': ar, 'choices': choices, 'correct': choices.index(f'{numerator}/{denominator}' if denominator != 1 else str(numerator)), 'visual': visual, 'detail': detail, 'explanation': f'{numerator} favorable outcome(s) ÷ {denominator} equally likely outcomes.', 'explanationAr': f'{numerator} نواتج مرغوبة ÷ {denominator} نواتج متساوية الاحتمال.'})
    for label, arabic, n in [('heads', 'وجه الدلة', 1), ('tails', 'وجه الرقم', 1), ('heads or tails', 'أحد الوجهين', 2), ('neither heads nor tails', 'لا أحد من الوجهين', 0)]:
        add('coin', f'A fair dirham is flipped once. What is P({label})?', f'نقلب درهماً عادلاً مرة واحدة. ما احتمال ظهور {arabic}؟', n, 2, 'coin', 'Fair coin · 2 equally likely faces / وجهان متساويا الاحتمال')
    for i in range(1, 7):
        add('dice', f'A fair die is rolled. What is P(rolling {i})?', f'نرمي نرداً عادلاً. ما احتمال ظهور العدد {i}؟', 1, 6, 'dice', f'Event: {i} · Outcomes: 1, 2, 3, 4, 5, 6')
    events = [('an even number', 'عدد زوجي', 3), ('an odd number', 'عدد فردي', 3), ('a number greater than 4', 'عدد أكبر من ٤', 2), ('a number less than 3', 'عدد أصغر من ٣', 2), ('a number at most 4', 'عدد لا يزيد عن ٤', 4), ('a number greater than 1', 'عدد أكبر من ١', 5), ('a number less than 7', 'عدد أصغر من ٧', 6), ('the number 7', 'العدد ٧', 0), ('a multiple of 3', 'أحد مضاعفات ٣', 2), ('a prime number', 'عدد أولي', 3)]
    for en, ar, n in events:
        add('dice', f'On a fair six-sided die, what is P({en})?', f'في نرد عادل ذي ستة أوجه، ما احتمال ظهور {ar}؟', n, 6, 'dice', 'Equally likely outcomes: 1, 2, 3, 4, 5, 6 / نرد عادل')
    for segments in [4, 6, 8]:
        for red in range(1, segments):
            add('spinner', 'What is the probability of landing on a coral sector?', 'ما احتمال توقف المؤشر عند قطاع مرجاني اللون؟', red, segments, 'spinner', {'segments': segments, 'red': red})
    add('spinner', 'A fair spinner has 4 numbered sectors. What is P(an even number)?', 'قرص عادل له ٤ قطاعات مرقمة. ما احتمال عدد زوجي؟', 2, 4, 'numbered', '1, 2, 3, 4 · Equal sectors / قطاعات متساوية')
    add('spinner', 'A fair spinner has 8 numbered sectors. What is P(a number greater than 6)?', 'قرص عادل له ٨ قطاعات مرقمة. ما احتمال عدد أكبر من ٦؟', 2, 8, 'numbered', '1, 2, 3, 4, 5, 6, 7, 8 · Equal sectors')
    return bank

BANK = make_bank()


def settings(db):
    return json.loads(db.execute("SELECT value FROM settings WHERE key='lesson'").fetchone()[0])


def advance_expired(db, attempt):
    if attempt['waiting']:
        return attempt
    answers = json.loads(attempt['answers'])
    ids = json.loads(attempt['questions'])
    started = attempt['current_started']
    while len(answers) < len(ids) and time.time() >= started + 40:
        answers.append({'question': ids[len(answers)], 'choice': None, 'correct': False, 'points': 0, 'seconds': 40})
        started += 40
    finished = len(answers) == len(ids)
    db.execute('UPDATE attempts SET answers=?,current_started=?,finished=? WHERE id=?', (json.dumps(answers), started, int(finished), attempt['id']))
    return db.execute('SELECT * FROM attempts WHERE id=?', (attempt['id'],)).fetchone()


def public_attempt(row):
    ids, answers = json.loads(row['questions']), json.loads(row['answers'])
    correct = sum(a['correct'] for a in answers)
    out = {'id': row['id'], 'mode': row['mode'], 'total': len(ids), 'index': len(answers), 'finished': bool(row['finished']), 'correct': correct, 'points': sum(a['points'] for a in answers), 'percent': round(100 * correct / len(ids), 1), 'mastered': row['finished'] == 1 and correct / len(ids) >= .8, 'deadline': (row['current_started'] + 40) * 1000, 'serverNow': time.time() * 1000, 'waiting':bool(row['waiting'])}
    out['responses'] = [{**BANK[a['question']], **a, 'correctAnswer':BANK[a['question']]['correct']} for a in answers]
    if not row['finished']:
        q = BANK[ids[len(answers)]]
        out['question'] = {k:v for k,v in q.items() if k not in ('correct', 'explanation', 'explanationAr')}
    else:
        out['review'] = [{**BANK[a['question']], **a, 'correctAnswer': BANK[a['question']]['correct']} for a in answers]
    return out


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        # Log paths only, never bodies, cookies, passwords or session tokens.
        if args and isinstance(args[0], str):
            super().log_message('%s', args[0].split('?')[0])

    def send_json(self, status, value, cookie=None):
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if cookie:
            secure = '; Secure' if self.headers.get('X-Forwarded-Proto') == 'https' else ''
            self.send_header('Set-Cookie', cookie + secure)
        self.end_headers()
        self.wfile.write(data)

    def session(self, db):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            token = cookie['class_session'].value if 'class_session' in cookie else ''
        except Exception:
            token = ''
        hashed = hashlib.sha256(token.encode()).hexdigest()
        return db.execute('SELECT * FROM sessions WHERE token=? AND expires>?', (hashed, time.time())).fetchone()

    def new_session(self, db, role, student=None):
        token = secrets.token_urlsafe(32)
        db.execute('INSERT INTO sessions VALUES(?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), role, student, time.time()+12*3600))
        return f'class_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith('/api/'):
            self.api('GET', path, {})
        elif path in ('/', '/index.html', '/app.js', '/studio.js', '/style.css', '/warm-theme.css', '/dice-lab.html', '/lesson-plan.md', '/vendor/mathjax/tex-svg.js'):
            super().do_GET()
        else:
            self.send_error(404)

    def do_POST(self):
        # Same-origin requests only; no permissive CORS.
        origin = self.headers.get('Origin')
        if origin and urlparse(origin).netloc != self.headers.get('Host'):
            return self.send_json(403, {'error':'Cross-origin request denied.'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length > 2500000:
                return self.send_json(413, {'error':'Request too large.'})
            body = json.loads(self.rfile.read(length) or '{}')
            if not isinstance(body, dict):
                raise ValueError()
        except (ValueError, json.JSONDecodeError):
            return self.send_json(400, {'error':'Invalid request.'})
        self.api('POST', urlparse(self.path).path, body)

    def api(self, method, path, body):
        try:
            with connect() as db:
                # Serialize mutations, including simultaneous answers from two tabs.
                if method == 'POST':
                    db.execute('BEGIN IMMEDIATE')
                session = self.session(db)
                if path == '/api/health' and method == 'GET':
                    return self.send_json(200, {'ok': True})
                if path == '/api/login' and method == 'POST':
                    role = body.get('role')
                    if role == 'teacher':
                        # Bound login attempts per client over a short window.
                        now = time.time()
                        ip = self.client_address[0]
                        tries = self.server.login_attempts.setdefault(ip, [])
                        tries[:] = [x for x in tries if now-x < 60]
                        if len(tries) >= 10:
                            return self.send_json(429, {'error':'Too many attempts. Try again in one minute.'})
                        tries.append(now)
                        if body.get('username') != 'walaa' or not hmac.compare_digest(str(body.get('password', '')), PASSWORD):
                            return self.send_json(401, {'error':'Incorrect username or password. / بيانات الدخول غير صحيحة'})
                        cookie = self.new_session(db, 'teacher')
                    else:
                        name = str(body.get('name', '')).strip()
                        if not 2 <= len(name) <= 60:
                            return self.send_json(400, {'error':'Enter your name (2–60 characters). / أدخلي اسمك'})
                        if str(body.get('code', '')).strip().upper() != CLASS_CODE:
                            return self.send_json(400, {'error':'Check the class code with your teacher. / تحققي من رمز الصف'})
                        sid = secrets.token_hex(12)
                        db.execute('INSERT INTO students(id,name,created,seen) VALUES(?,?,?,?)', (sid, name, time.time(), time.time()))
                        cookie = self.new_session(db, 'student', sid)
                    db.commit()
                    return self.send_json(200, {'ok': True}, cookie)
                if not session:
                    return self.send_json(401, {'error':'Please sign in. / يرجى تسجيل الدخول'})
                role, sid = session['role'], session['student']
                if path == '/api/logout' and method == 'POST':
                    db.execute('DELETE FROM sessions WHERE token=?', (session['token'],))
                    db.commit()
                    return self.send_json(200, {'ok':True}, 'class_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                if path == '/api/state' and method == 'GET':
                    lesson = settings(db)
                    control = json.loads(db.execute("SELECT value FROM settings WHERE key='control'").fetchone()[0])
                    if role == 'teacher':
                        return self.send_json(200, {'role':role, 'lesson':lesson, 'code':CLASS_CODE, 'bankSize':len(BANK), 'control':control})
                    student = dict(db.execute('SELECT * FROM students WHERE id=?', (sid,)).fetchone())
                    attempts = [public_attempt(advance_expired(db, a)) for a in db.execute('SELECT * FROM attempts WHERE student=? ORDER BY rowid', (sid,)).fetchall()]
                    db.commit()
                    return self.send_json(200, {'role':role,'student':student,'lesson':student_lesson(lesson),'attempts':attempts,'explorations':[dict(e) for e in db.execute('SELECT * FROM explorations WHERE student=?',(sid,))],'samples':[dict(w) for w in db.execute('SELECT * FROM work_samples WHERE student=?',(sid,))],'control':control,'work':dict(db.execute('SELECT * FROM work WHERE student=?',(sid,)).fetchone() or {})})
                if role == 'teacher':
                    if path == '/api/dashboard' and method == 'GET':
                        rows = db.execute('SELECT * FROM attempts').fetchall()
                        attempts = [dict(advance_expired(db,a)) for a in rows]
                        students = [dict(s) for s in db.execute('SELECT * FROM students ORDER BY created')]
                        db.commit()
                        return self.send_json(200, {'students':students,'attempts':[{'student':a['student'],**public_attempt(a)} for a in attempts], 'lesson':settings(db), 'serverNow':time.time()*1000, 'explorations':[dict(e) for e in db.execute('SELECT * FROM explorations')], 'reflection':db.execute('SELECT content FROM reflections WHERE id=1').fetchone()[0], 'samples':[dict(w) for w in db.execute('SELECT * FROM work_samples')], 'work':[dict(w) for w in db.execute('SELECT * FROM work')], 'control':json.loads(db.execute("SELECT value FROM settings WHERE key='control'").fetchone()[0])})
                    if path == '/api/reflection' and method == 'POST':
                        db.execute('UPDATE reflections SET content=? WHERE id=1',(str(body.get('content',''))[:6000],))
                        db.commit()
                        return self.send_json(200,{'ok':True})
                    if path == '/api/control' and method == 'POST':
                        mode = body.get('mode')
                        target = int(body.get('slide',0))
                        if mode not in ('student','teacher') or target not in range(8):
                            raise ValueError('Invalid lesson mode.')
                        db.execute("UPDATE settings SET value=? WHERE key='control'",(json.dumps({'mode':mode,'slide':target}),))
                        db.commit()
                        return self.send_json(200,{'ok':True})
                    if path == '/api/feedback' and method == 'POST':
                        target = str(body.get('student',''))
                        if not db.execute('SELECT id FROM students WHERE id=?',(target,)).fetchone():
                            raise ValueError('Student not found.')
                        db.execute('INSERT OR IGNORE INTO work(student,updated) VALUES(?,?)',(target,time.time()))
                        db.execute('UPDATE work SET feedback=?,help=0 WHERE student=?',(str(body.get('feedback',''))[:2000],target))
                        db.commit()
                        return self.send_json(200,{'ok':True})
                    if path == '/api/materials' and method == 'GET':
                        return self.send_json(200,{'bank':BANK})
                    if path == '/api/lesson' and method == 'POST':
                        vid = str(body.get('videoId', ''))
                        import re
                        if vid and not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid):
                            return self.send_json(400, {'error':'Enter a valid YouTube video link.'})
                        cps = body.get('checkpoints', [])
                        if not isinstance(cps, list) or len(cps) > 15:
                            raise ValueError('Use up to 15 checkpoints.')
                        start=int(body.get('start',0)); end=int(body.get('end',7200))
                        if not 0<=start<end<=7200: raise ValueError('Invalid video segment.')
                        cleaned = []
                        for i,c in enumerate(cps):
                            at = int(c['at'])
                            opts = [str(x).strip()[:180] for x in c['options']]
                            correct = int(c['correct'])
                            if not 0 <= at < end-start or not 2<=len(opts)<=4 or not all(opts) or correct not in range(len(opts)) or not str(c['en']).strip():
                                raise ValueError('Each checkpoint needs a time, question, four options, and correct answer.')
                            cleaned.append({'id':secrets.token_hex(6),'at':at,'en':str(c['en'])[:500],'ar':str(c.get('ar',''))[:500],'options':opts,'correct':correct,'explanation':str(c.get('explanation',''))[:2000]})
                        cleaned.sort(key=lambda c:c['at'])
                        db.execute("UPDATE settings SET value=? WHERE key='lesson'", (json.dumps({'videoId':vid,'start':start,'end':end,'checkpoints':cleaned}),))
                        # Invalidate previous video answers when the material changes.
                        db.execute("UPDATE students SET video='{}'")
                        db.commit()
                        return self.send_json(200, {'ok':True})
                    return self.send_json(404, {'error':'Unknown teacher action.'})
                db.execute('UPDATE students SET seen=? WHERE id=?', (time.time(),sid))
                if path == '/api/classroom' and method == 'GET':
                    control=json.loads(db.execute("SELECT value FROM settings WHERE key='control'").fetchone()[0])
                    work=dict(db.execute('SELECT * FROM work WHERE student=?',(sid,)).fetchone() or {})
                    db.commit()
                    return self.send_json(200,{'control':control,'work':work})
                if path == '/api/work' and method == 'POST':
                    db.execute('INSERT OR IGNORE INTO work(student,updated) VALUES(?,?)',(sid,time.time()))
                    if 'help' in body:
                        db.execute('UPDATE work SET help=?,updated=? WHERE student=?',(int(bool(body['help'])),time.time(),sid))
                    if 'reasoning' in body:
                        strokes=body.get('strokes',[])
                        if not isinstance(strokes,list) or len(strokes)>150:
                            raise ValueError('Drawing limit reached. Clear some work to continue.')
                        for stroke in strokes:
                            if not isinstance(stroke,list) or len(stroke)>400:
                                raise ValueError('Invalid drawing.')
                            for point in stroke:
                                if not isinstance(point,list) or len(point)!=2 or any(not isinstance(v,(int,float)) or not 0<=v<=1 for v in point):
                                    raise ValueError('Invalid drawing coordinates.')
                        db.execute('UPDATE work SET reasoning=?,strokes=?,updated=? WHERE student=?',(str(body.get('reasoning',''))[:3000],json.dumps(strokes),time.time(),sid))
                        page=int(body.get('slide',0))
                        if page not in range(8): raise ValueError('Invalid slide.')
                        db.execute('INSERT OR REPLACE INTO work_samples VALUES(?,?,?,?,?)',(sid,page,str(body.get('reasoning',''))[:3000],json.dumps(strokes),time.time()))
                    db.commit()
                    return self.send_json(200,{'ok':True})
                if path == '/api/explore' and method == 'POST':
                    kind=body.get('kind'); step=int(body.get('step',0))
                    if kind not in ('coin','dice','spinner') or step not in range(5):
                        raise ValueError('Invalid example step.')
                    db.execute('INSERT OR IGNORE INTO explorations(student,kind,updated) VALUES(?,?,?)',(sid,kind,time.time()))
                    row=db.execute('SELECT * FROM explorations WHERE student=? AND kind=?',(sid,kind)).fetchone()
                    seen=json.loads(row['seen'])
                    if step not in seen:seen.append(step)
                    correct=row['correct']; tries=row['tries']; answer_correct=None
                    if 'answer' in body:
                        if step!=4:raise ValueError('Complete the worked steps first.')
                        answer_correct=body['answer']=={'coin':'1/2','dice':'3/6','spinner':'1/4'}[kind]
                        correct=max(correct,int(answer_correct));tries+=1
                    db.execute('UPDATE explorations SET step=?,seen=?,correct=?,tries=?,updated=? WHERE student=? AND kind=?',(step,json.dumps(seen),correct,tries,time.time(),sid,kind))
                    result=dict(db.execute('SELECT * FROM explorations WHERE student=? AND kind=?',(sid,kind)).fetchone())
                    db.commit()
                    return self.send_json(200,{'exploration':result,'answerCorrect':answer_correct})
                if path == '/api/progress' and method == 'POST':
                    slide = int(body.get('slide',0))
                    if slide not in range(8):
                        raise ValueError('Invalid slide.')
                    visited = json.loads(db.execute('SELECT visited FROM students WHERE id=?',(sid,)).fetchone()[0])
                    if slide not in visited:
                        visited.append(slide)
                    db.execute('UPDATE students SET slide=?, visited=? WHERE id=?',(slide,json.dumps(visited),sid))
                    db.commit()
                    return self.send_json(200, {'ok':True})
                if path == '/api/coin' and method == 'POST':
                    correct = body.get('choice') == 1
                    db.execute('UPDATE students SET coin=? WHERE id=?',(int(correct),sid))
                    db.commit()
                    return self.send_json(200, {'correct':correct})
                if path == '/api/poll' and method == 'POST':
                    choice = int(body.get('choice',-1))
                    if choice not in range(4):
                        raise ValueError('Select a confidence level.')
                    db.execute('UPDATE students SET poll=? WHERE id=?',(choice,sid))
                    db.commit()
                    return self.send_json(200, {'ok':True})
                if path == '/api/video-answer' and method == 'POST':
                    cp = next((c for c in settings(db)['checkpoints'] if c['id']==body.get('id')),None)
                    if not cp:
                        raise ValueError('This checkpoint has changed. Reload the lesson.')
                    choice = int(body.get('choice',-1))
                    if choice not in range(len(cp['options'])):
                        raise ValueError('Select an answer.')
                    record = json.loads(db.execute('SELECT video FROM students WHERE id=?',(sid,)).fetchone()[0])
                    if cp['id'] not in record:
                        record[cp['id']] = {'choice':choice,'correct':choice==cp['correct']}
                        db.execute('UPDATE students SET video=? WHERE id=?',(json.dumps(record),sid))
                    db.commit()
                    return self.send_json(200, {'correct':record[cp['id']]['correct'], 'answer':cp['correct'],'explanation':cp.get('explanation','')})
                if path == '/api/start' and method == 'POST':
                    mode = body.get('mode')
                    if mode not in ('race','mastery'):
                        raise ValueError('Unknown game.')
                    existing = db.execute('SELECT * FROM attempts WHERE student=? AND mode=? ORDER BY rowid DESC LIMIT 1',(sid,mode)).fetchone()
                    if existing:
                        existing = advance_expired(db, existing)
                        if not existing['finished'] or (mode=='race'):
                            db.commit()
                            return self.send_json(200, public_attempt(existing))
                    # Balanced selection: coin, dice and spinner in every round.
                    rng = secrets.SystemRandom()
                    coins = rng.sample([q['id'] for q in BANK if q['kind']=='coin'],2)
                    dice = rng.sample([q['id'] for q in BANK if q['kind']=='dice'],4 if mode=='mastery' else 3)
                    spins = rng.sample([q['id'] for q in BANK if q['kind']=='spinner'],6 if mode=='mastery' else 5)
                    ids = coins+dice+spins
                    rng.shuffle(ids)
                    aid = secrets.token_hex(12)
                    db.execute('INSERT INTO attempts(id,student,mode,questions,current_started) VALUES(?,?,?,?,?)',(aid,sid,mode,json.dumps(ids),time.time()))
                    row = db.execute('SELECT * FROM attempts WHERE id=?',(aid,)).fetchone()
                    db.commit()
                    return self.send_json(200, public_attempt(row))
                if path == '/api/resume' and method == 'POST':
                    db.execute('UPDATE attempts SET waiting=0,current_started=? WHERE id=? AND student=? AND waiting=1 AND finished=0',(time.time(),body.get('attempt'),sid))
                    row=db.execute('SELECT * FROM attempts WHERE id=? AND student=?',(body.get('attempt'),sid)).fetchone()
                    if not row:
                        raise ValueError('Game not found.')
                    db.commit()
                    return self.send_json(200,public_attempt(row))
                if path == '/api/answer' and method == 'POST':
                    row = db.execute('SELECT * FROM attempts WHERE id=? AND student=?',(body.get('attempt'),sid)).fetchone()
                    if not row:
                        raise ValueError('Game not found.')
                    row = advance_expired(db,row)
                    answers, ids = json.loads(row['answers']), json.loads(row['questions'])
                    if row['finished'] or row['waiting'] or int(body.get('index',-1)) != len(answers):
                        db.commit()
                        return self.send_json(200, {'attempt':public_attempt(row),'feedback':{'expired':True}})
                    choice = body.get('choice')
                    if choice is not None and (not isinstance(choice,int) or choice not in range(4)):
                        raise ValueError('Invalid answer.')
                    q = BANK[ids[len(answers)]]
                    elapsed = min(40,max(0,time.time()-row['current_started']))
                    correct = choice==q['correct']
                    points = (100+round((40-elapsed)*2.5)) if correct else 0
                    answers.append({'question':q['id'],'choice':choice,'correct':correct,'points':points,'seconds':round(elapsed,1)})
                    db.execute('UPDATE attempts SET answers=?,current_started=?,finished=? WHERE id=?',(json.dumps(answers),time.time(),int(len(answers)==len(ids)),row['id']))
                    db.execute('UPDATE attempts SET waiting=? WHERE id=?',(int(not correct and len(answers)<len(ids)),row['id']))
                    row = db.execute('SELECT * FROM attempts WHERE id=?',(row['id'],)).fetchone()
                    db.commit()
                    return self.send_json(200, {'attempt':public_attempt(row),'feedback':{'correct':correct,'answer':q['choices'][q['correct']],'explanation':q['explanation'],'explanationAr':q['explanationAr'],'points':points,'worked':q}})
                if path == '/api/leaderboard' and method == 'GET':
                    rows = db.execute("SELECT a.*,s.name FROM attempts a JOIN students s ON s.id=a.student WHERE mode='race'").fetchall()
                    leaders=[]
                    for a in rows:
                        pub=public_attempt(advance_expired(db,a))
                        leaders.append({'name':a['name'],'points':pub['points'],'correct':pub['correct'],'answered':pub['index'],'me':a['student']==sid})
                    db.commit()
                    return self.send_json(200, {'leaders':sorted(leaders,key=lambda x:(-x['points'],-x['correct']))[:30]})
                return self.send_json(404, {'error':'Unknown action.'})
        except (ValueError, KeyError, TypeError) as e:
            return self.send_json(400, {'error':str(e) or 'Invalid request.'})
        except Exception:
            return self.send_json(500, {'error':'Could not save this action. Please try again.'})


def student_lesson(lesson):
    return {**lesson,'checkpoints':[{k:v for k,v in c.items() if k!='correct'} for c in lesson['checkpoints']]}


if __name__ == '__main__':
    initialize()
    server = ThreadingHTTPServer((os.environ.get('HOST','0.0.0.0'),int(os.environ.get('PORT','8080'))),Handler)
    server.login_attempts={}
    print(f'Probability Studio running on port {server.server_port}',flush=True)
    server.serve_forever()
