"""Starts an isolated test server; uses separate teacher/student contexts."""
import json
import tempfile, threading, atexit
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from playwright.sync_api import sync_playwright
OUT=Path('/tmp/chance-artifacts');OUT.mkdir(exist_ok=True)
test_data=tempfile.TemporaryDirectory()
server.DB=Path(test_data.name)/'browser.sqlite3'
server.initialize()
http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
http.login_attempts={}
threading.Thread(target=http.serve_forever,daemon=True).start()
atexit.register(lambda:(http.shutdown(),http.server_close(),test_data.cleanup()))
BASE=f'http://127.0.0.1:{http.server_port}'
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    tc=b.new_context(viewport={'width':1440,'height':1000})
    sc=b.new_context(viewport={'width':1440,'height':1000})
    for ctx in (tc,sc):
        ctx.route('https://**/*',lambda route:route.abort())
        ctx.add_init_script('window.print=()=>{window.didPrint=true}')
    t,s=tc.new_page(),sc.new_page();errors=[]
    t.on('pageerror',lambda e:errors.append('teacher: '+str(e)))
    s.on('pageerror',lambda e:errors.append('student: '+str(e)))
    t.goto(BASE);t.locator('[data-role=teacher]').click();t.locator('[name=username]').fill('walaa');t.locator('[name=password]').fill('uae123');t.locator('button[type=submit]').click()
    t.wait_for_selector('[data-tab=plan]');t.locator('.teacher-tabs [data-tab=plan]').click();t.wait_for_selector('.lesson-plan')
    assert 'ASSURE' in t.locator('.lesson-plan').inner_text()
    t.locator('#reflectionText').fill('Observed students counting all outcomes; revisit unequal sectors.');t.locator('[data-action=save-reflection]').click()
    t.locator('[data-action=print-plan]').click();t.wait_for_function('window.didPrint===true');t.emulate_media(media='print');t.pdf(path=str(OUT/'lesson-plan.pdf'),format='A4',landscape=True,print_background=True);t.emulate_media(media='screen')
    t.locator('.teacher-tabs [data-tab=video]').click();t.locator('#videoURL').fill('https://youtu.be/abcdefghijk');
    while t.locator('[data-action=remove-checkpoint]').count():t.locator('[data-action=remove-checkpoint]').first.click()
    t.locator('#videoStart').fill('0');t.locator('#videoEnd').fill('7200');t.locator('[data-action=add-checkpoint]').click()
    for name,value in [('at','1'),('en','How many outcomes does a fair coin have?'),('ar','كم عدد نواتج العملة العادلة؟'),('option0','1 / ١'),('option1','2 / ٢'),('option2','3 / ٣'),('option3','4 / ٤')]:t.locator(f'[name={name}]').fill(value)
    t.locator('[name=explanation]').fill('Two equally likely faces; count both before choosing. وجهان متساويا الاحتمال.');t.locator('[name=correct]').select_option('1');t.locator('#videoForm button[type=submit]').click();t.wait_for_selector('#videoForm')
    def student_nav(index):
        if 'open' not in (s.locator('.sidebar').get_attribute('class') or ''):s.locator('[data-action=menu]').click()
        s.locator(f'.lesson-nav [data-action=navigate][data-slide="{index}"]').click()
    s.goto(BASE);s.locator('[name=name]').fill('Mariam · مريم');s.locator('[name=code]').fill('WALAA9');s.locator('button[type=submit]').click();s.wait_for_selector('.cover')
    s.wait_for_timeout(400);s.screenshot(path=str(OUT/'student-cover.png'),full_page=True)
    assert s.locator('.cover').inner_text().find('Walaa Falah')==-1 # credit strip is separate
    student_nav(2);s.wait_for_selector('#chancePlayground')
    for kind,selection,n,d in [('coin',[0],1,2),('dice',[1,3,5],3,6),('spinner',[0,1,2],3,4)]:
        s.locator('[data-story=map]').click()
        s.locator(f'[data-play=choose][data-kind="{kind}"]').click()
        assert s.locator('.story-speech').is_visible()
        if kind=='coin':
            s.screenshot(path=str(OUT/'story-dialogue.png'),full_page=True,animations='disabled')
            s.set_viewport_size({'width':390,'height':844})
            assert s.evaluate('document.documentElement.scrollWidth<=innerWidth')
            s.screenshot(path=str(OUT/'story-dialogue-mobile.png'),full_page=True,animations='disabled')
            s.set_viewport_size({'width':1440,'height':1000})
        assert s.locator('#playNumerator').count()==0
        s.locator('[data-story=advance]').click();s.locator('[data-story=advance]').click()
        if kind=='spinner':s.locator('[data-play=red][data-red="3"]').click()
        assert s.locator('[data-play=trial][data-count="1"]').is_disabled()
        s.locator('[data-play=predict][data-prediction=yes]').click()
        s.locator('[data-play=trial][data-count="1"]').click()
        s.wait_for_function('!playBusy')
        assert s.evaluate('JSON.parse(playRecord().counts).reduce((a,b)=>a+b,0)')==1
        s.locator('[data-story=advance]').click()
        s.locator('[data-story=count]').click()
        s.wait_for_function('state.journey.selection_error===1')
        for i in selection:s.locator(f'[data-play=select][data-index="{i}"]').click()
        s.locator('[data-story=count]').click()
        s.wait_for_function('storyScene===3')
        assert s.locator('.story-equation').count()==0
        s.locator('[data-story=advance]').click();s.locator('[data-story=advance]').click()
        s.wait_for_selector('.story-equation mjx-container svg')
        s.locator('[data-story=advance]').click()
        s.wait_for_function('state.journey.scene===4')
        s.reload();s.wait_for_selector('#playNumerator')
        assert s.evaluate('playKind')==kind
        s.locator('#playNumerator').fill(str(n));s.locator('#playDenominator').fill('1')
        s.locator('[data-play=check]').click();s.wait_for_selector('.mission-retry')
        assert s.locator('#playNumerator').count()==0
        s.locator('[data-story=explain]').click()
        for _ in range(3):s.locator('[data-story=advance]').click()
        s.locator('#playNumerator').fill(str(n));s.locator('#playDenominator').fill(str(d))
        s.locator('[data-play=check]').click();s.wait_for_selector('.mission-won')
    assert s.evaluate('playWins()')==3
    s.screenshot(path=str(OUT/'chance-playground.png'),full_page=True,animations='disabled')
    s.set_viewport_size({'width':390,'height':844})
    assert s.evaluate('document.documentElement.scrollWidth<=innerWidth')
    s.screenshot(path=str(OUT/'chance-playground-mobile.png'),full_page=True,animations='disabled')
    s.set_viewport_size({'width':1440,'height':1000})
    s.locator('.story-resources>summary').click()
    s.locator('.guide-details').first.locator('summary').first.click();s.wait_for_selector('.discovery-studio')
    for kind,answer in [('coin','1/2'),('dice','3/6'),('spinner','1/4')]:
        s.locator(f'[data-studio=example][data-kind="{kind}"]').click()
        for step in range(1,5):
            with s.expect_response(lambda r:'/api/explore' in r.url and r.request.method=='POST'):
                s.locator(f'[data-studio=step][data-step="{step}"]').click()
        s.wait_for_selector('.equation-build mjx-container svg')
        s.locator(f'[data-studio=answer][data-answer="{answer}"]').click()
        s.wait_for_function('(kind)=>state.explorations.some(e=>e.kind===kind&&e.correct)',arg=kind)
    assert s.evaluate('state.explorations.length')==3
    s.screenshot(path=str(OUT/'worked-studio.png'),full_page=True,animations='disabled')
    s.set_viewport_size({'width':390,'height':844})
    assert s.evaluate('document.documentElement.scrollWidth<=innerWidth')
    s.screenshot(path=str(OUT/'worked-studio-mobile.png'),full_page=True,animations='disabled')
    s.set_viewport_size({'width':1440,'height':1000})
    student_nav(0);s.wait_for_selector('.cover')
    obj=s.locator('.cover-art .coin-obj');obj.focus();obj.press('ArrowRight');assert 'translate' in obj.get_attribute('style')
    s.locator('[data-action=thinking]').first.click();s.locator('#reasoning').fill('There are 2 equally likely outcomes, so P(heads) = 1/2.')
    canvas=s.locator('#thinkingCanvas').bounding_box();s.mouse.move(canvas['x']+20,canvas['y']+20);s.mouse.down();s.mouse.move(canvas['x']+130,canvas['y']+70,steps=8);s.mouse.up();s.locator('[data-action=save-work]').click();s.locator('[data-action=raise-hand]').click();s.wait_for_timeout(600)
    t.locator('.teacher-tabs [data-tab=monitor]').click();t.wait_for_selector('[data-action=student-detail]');t.wait_for_selector('.work-tile');t.screenshot(path=str(OUT/'teacher-gallery.png'),full_page=True)
    t.locator('[data-action=student-detail]').first.click();t.wait_for_selector('#studentCanvas');assert 'equally likely' in t.locator('#studentLiveWork').inner_text();t.locator('#studentFeedback').fill('Excellent sample space. Explain why the coin must be fair.');t.locator('[data-action=send-feedback]').click();t.locator('[data-action=close-modal]').click()
    s.wait_for_function("document.querySelector('#teacherFeedback').textContent.includes('Excellent')",timeout=12000)
    s.locator('#thinkingPanel [data-action=thinking]').click()
    t.locator('[data-action=pace][data-mode=teacher]').click();t.wait_for_selector('#controlSlide:not([disabled])');t.locator('#controlSlide').select_option('3')
    s.wait_for_selector('.coin-stage',timeout=12000);s.locator('[data-action=next]').click();assert s.locator('.coin-stage').count()==1
    t.locator('[data-action=pace][data-mode=student]').click();s.wait_for_timeout(6000)
    s.locator('[data-action=coin-answer][data-choice="1"]').click();s.wait_for_selector('#coinFeedback .feedback');assert 'Exactly' in s.locator('#coinFeedback').inner_text()
    # Test checkpoint UI with a controlled player double. Real YouTube is external.
    s.evaluate("""window.YT={Player:function(id,opts){this.getCurrentTime=()=>2;this.pauseVideo=()=>{};this.playVideo=()=>{};this.destroy=()=>{};setTimeout(()=>opts.events.onReady(),10)}}""")
    student_nav(1);s.wait_for_selector('#videoQuestion:not([hidden])');s.locator('[data-action=video-answer][data-choice="1"]').click();s.wait_for_selector('[data-action=video-continue]');s.locator('[data-action=video-continue]').click();assert s.locator('#videoQuestion').is_hidden()
    student_nav(4);s.locator('[data-action=start-game]').click();s.wait_for_selector('#timer')
    for i in range(10):
        s.wait_for_selector('[data-action=game-answer]')
        qid=s.evaluate('activeGame.question.id');correct=server.BANK[qid]['correct']
        s.locator(f'[data-action=game-answer][data-choice="{correct}"]').click()
        s.wait_for_function('(i)=>activeGame.index>i',arg=i)
    assert '100%' in s.locator('#gamePanel').inner_text();s.locator('#gamePanel summary').click();assert 'undefined' not in s.locator('#gamePanel').inner_text()
    student_nav(5);s.locator('[data-action=start-game]').click()
    for i in range(12):
        if s.locator('[data-action=resume-game]').count():
            s.wait_for_selector('.worked mjx-container svg')
            assert s.evaluate('activeGame.waiting')
            assert s.locator('#timer').count()==0
            s.locator('[data-action=resume-game]').click()
        s.wait_for_selector('[data-action=game-answer]');qid=s.evaluate('activeGame.question.id');correct=server.BANK[qid]['correct'];choice=correct if i<10 else (correct+1)%4
        s.locator(f'[data-action=game-answer][data-choice="{choice}"]').click();s.wait_for_function('(i)=>activeGame.index>i',arg=i)
    assert '83.3%' in s.locator('#gamePanel').inner_text();assert 'goal' in s.locator('#gamePanel').inner_text()
    student_nav(6);s.locator('[data-action=poll][data-choice="1"]').click();s.wait_for_selector('#pollFeedback .feedback')
    student_nav(7);s.wait_for_selector('[data-action=print-progress]');assert '83.3%' in s.locator('#slideContent').inner_text();s.locator('[data-action=print-progress]').click();s.wait_for_selector('#printRoot .print-report',state='attached');s.emulate_media(media='print');s.pdf(path=str(OUT/'student-progress.pdf'),format='A4',landscape=True,print_background=True);s.emulate_media(media='screen')
    t.locator('.teacher-tabs [data-tab=report]').click();t.wait_for_selector('.report-header');assert 'Mariam' in t.locator('#teacherPanel').inner_text();assert 'Observed students' in t.locator('#teacherPanel').inner_text()
    t.locator('[data-action=print-report]').click();t.wait_for_selector('#printRoot .print-report',state='attached');t.emulate_media(media='print');t.pdf(path=str(OUT/'class-report.pdf'),format='A4',landscape=True,print_background=True);t.emulate_media(media='screen')
    t.locator('[data-action=print-lesson]').click();t.wait_for_selector('#printRoot .print-page',state='attached');assert t.locator('#printRoot .print-question').count()>=22;t.emulate_media(media='print');t.pdf(path=str(OUT/'lesson-materials.pdf'),format='A4',landscape=True,print_background=True);t.emulate_media(media='screen')
    # Requested trim and all three checkpoint offsets against a controlled player.
    preset=json.loads((Path(__file__).resolve().parents[1]/'lesson-video.json').read_text())
    assert tc.request.post(BASE+'/api/lesson',data=preset).ok
    s.reload();s.wait_for_selector('.workspace')
    s.evaluate("""window.clipTime=8;window.clipPaused=false;window.YT={Player:function(id,opts){window.clipConfig=opts.playerVars;this.getCurrentTime=()=>window.clipTime;this.seekTo=(t)=>{window.clipTime=t};this.pauseVideo=()=>{window.clipPaused=true};this.playVideo=()=>{window.clipPaused=false};this.destroy=()=>{};setTimeout(()=>opts.events.onReady(),10)}}""")
    s.locator('[data-action=menu]').count() # keep desktop navigation
    student_nav(1)
    s.wait_for_function('window.clipConfig?.start===8 && window.clipConfig.end===258')
    for i,(absolute,answer) in enumerate([(113,1),(223,0),(235,2)]):
        s.evaluate('(t)=>window.clipTime=t',absolute)
        s.wait_for_selector('#videoQuestion:not([hidden])')
        assert s.evaluate('window.clipPaused')
        assert s.locator('.video-screen #videoQuestion').is_visible()
        assert s.locator('#modal').is_hidden()
        assert s.locator('#videoQuestion .option').count()==(2 if i==0 else 4)
        s.locator(f'[data-action=video-answer][data-choice="{answer}"]').click()
        s.wait_for_selector('[data-action=video-continue]')
        if i==0:
            s.wait_for_function('!window.clipPaused && document.querySelector("#videoQuestion").hidden',timeout=16000)
        else:s.locator('[data-action=video-continue]').click()
    s.evaluate('window.clipTime=258');s.wait_for_function('window.clipPaused')
    assert 'Segment complete' in s.locator('#videoStatus').inner_text()
    saved=sc.request.get(BASE+'/api/state').json()['student']['video']
    assert len(json.loads(saved))==3
    print('PASS: requested 8–258 segment, 105/215/227 relative checkpoints, true/false, auto-resume, end boundary, and saved responses.')
    # Small screen coverage and resume through the session cookie.
    s.set_viewport_size({'width':390,'height':844});s.reload();s.wait_for_selector('.workspace');s.locator('[data-action=menu]').click();student_nav(0);s.wait_for_selector('.cover');s.screenshot(path=str(OUT/'student-mobile.png'),full_page=True)
    assert s.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    s.locator('[data-action=menu]').click();student_nav(5);s.wait_for_selector('#gamePanel');assert '83.3%' in s.locator('#gamePanel').inner_text()
    assert not errors,errors
    print('PASS: separate teacher/student sessions, lesson plan, editor, video checkpoint double, saved drawing/text, help, feedback, teacher-led pacing, student-paced navigation, both complete games, mastery, review, exit poll, resume, four print exports, desktop/mobile layout; no JavaScript errors.')
    b.close()
