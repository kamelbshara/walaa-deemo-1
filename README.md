# Chance Studio · منصة الاحتمالات

A bilingual Grade 9 girls’ probability lesson prepared for Walaa Falah’s micro-teaching task, supervised by Dr. Jehan Yousif. Includes a lesson plan based on ASSURE and the supplied assignment rubric.

## Run

Python 3.10+; no application packages or build step required.

```sh
cd /workspace/walaa-deemo-1
python3 server.py
```

The app listens on port **8080**. Use the same hosted application origin on teacher and student devices. Teacher login: **walaa** / **uae123** (the requested initial credentials). Students join using their names and class code **WALAA9**. A student’s session resumes in the same browser for 12 hours; clearing cookies or using another browser creates a new record. Names are labels, not verified identities. Duplicate names are kept as separate student records.

The former standalone dice activity is retained in `dice-lab.html` as an optional, untracked lab.

## Classroom features

- Eight bilingual slides: introduction, interactive video, revision card, dirham question, 10-question sprint, 12-question mastery game, exit poll, personal progress.
- Teacher-led slide synchronization or student-paced navigation. Monitoring updates every 4–5 seconds while connected.
- Student text and drawing space, raised hands, private teacher feedback, live work gallery, assessment details, leaderboard.
- YouTube editor: unlisted video link, timestamped MCQs, first-response recording, pause until answer. Checkpoints also appear after seeking past them. Video embedding must be enabled in YouTube Studio. The supplied video KzfWUEJjG18 is preconfigured in lesson-video.json. The player shows source seconds 8–258 (4:10 total). Checkpoints at clip seconds 105, 215, and 227 correspond to source seconds 113, 223, and 235.
- 37-question bank (coin, fair six-sided die, equal-sector spinners). Balanced random samples without duplicate questions inside a round; different rounds may overlap.
- 40-second server-enforced deadlines. A correct answer earns 100 points plus up to 100 speed points. Leaving does not pause the clock. Expired questions are incorrect. Sprint allows one attempt per student session; mastery allows retries, and the best completed attempt is reported. At least 10/12 correct (83.3%) reaches the ≥80% target.
- Printable slide deck, 10- and 12-question sample worksheets and teacher key, personal progress, full class report, Arabic lesson plan, CSV export. Print lesson materials from the teacher account to include worksheets. Generated student data stays out of version control.
- ASSURE plan, 20-minute micro-teaching timeline, 30–35-minute extended lesson, differentiation, questions, assessment decisions, mapping to all 12 assignment rubric criteria, saved teacher reflection.

## Hosting and persistence

**GitHub Pages cannot run this classroom server.** The earlier automatic Pages publishing workflow has been replaced with validation checks so pushing these changes does not publish a nonfunctional, static-only classroom. No public backend deployment has been performed.

Host `server.py` as one Python service, or use the supplied Dockerfile. Put it behind an HTTPS reverse proxy for use outside a trusted local classroom. Forward the original Host and `X-Forwarded-Proto: https` so cookies are marked Secure. Configure a persistent writable data volume; do not deploy with an ephemeral database if reports must survive restarts. The Python standard-library HTTP server is intended for a small classroom deployment, not an internet-scale LMS. Use a production service stack and review authentication/data handling before broader school rollout.

Environment options (set on the server, never in client JavaScript):

| Name | Default | Purpose |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8080` | HTTP port |
| `CLASSROOM_DATA_DIR` | `.classroom` beside server.py | SQLite database location; persist this directory |
| `CLASS_CODE` | `WALAA9` | Classroom join code |
| `TEACHER_PASSWORD` | `uae123` | Replace the supplied initial password for public use |

This version supports one shared classroom per server instance. For a fresh class, use a new data directory and a new code rather than deleting a class report. Back up the SQLite database before changing or removing class data. App files are served from an explicit whitelist; database, server source, tests, and configuration are not served by the backend. Teacher authorization is checked server-side. Sessions use random HttpOnly, SameSite cookies. No login credentials are in the browser bundle. Student drawings and notes are personal classroom records; restrict teacher access and set the school’s retention policy before use.

External optional resources: Google Fonts (`fonts.googleapis.com`, `fonts.gstatic.com`). The app has local font fallbacks. Embedded video requires students’ browsers to reach YouTube and its video/CDN endpoints; those destinations are outside this cloud environment’s current allowlist. The UI handles unavailable playback. The supplied YouTube embed returns HTTP 403 from this environment, so real provider playback has not been verified; checkpoint mechanics were tested with a controlled player double.

The full question bank is not exposed to students before play; active responses exclude answer keys, with review available after completion. This is formative classroom assessment, not a proctored testing system.

## Validation

```sh
python3 -m unittest discover -s tests -v
node --check app.js
```

Seven integration tests cover authentication and static-file privacy, bank correctness, two-device work/feedback/pacing, video first-response rules, scoring and duplicate submissions, 40-second expiry, mastery thresholds/retries, progress, reflection, and logout.

Optional end-to-end test (requires Python Playwright and Chromium): run `python3 tests/browser_check.py`. It starts its own isolated temporary database and server. It writes screenshots and four print PDFs to `/tmp/chance-artifacts`. The test uses real backend requests with separate browser contexts; only external YouTube playback is doubled. Never run it against the live classroom database.

## Lesson materials

See [lesson-plan.md](lesson-plan.md) for the complete Arabic plan. The supplied assignment specifies 15–20 minutes. Both timed games together can take 14 minutes 40 seconds, so the 20-minute presentation introduces mastery and completes it afterward as independent practice; the full lesson takes about 30–35 minutes. This preserves the requested 40-second timing without claiming the whole sequence fits the micro-teaching slot.

## Guided feedback and intervention

Wrong submitted answers open a worked solution and pause the next question until the student continues. Each question still has a 40-second answering window; reading feedback adds untimed review time, so allow more time than the original presentation estimate. Teacher monitoring includes topic accuracy across attempts, timeouts, submitted responses during an active game, work samples, and suggested interventions. Flags need at least two topic responses and do not constitute a diagnosis. Reports include answer-level activity evidence and drawings. MathJax 3.2.2 (Apache 2.0, license in vendor/mathjax) is served locally. Video authors enter their own specific worked explanation in the checkpoint editor.

## Video and roster update

The first checkpoint is true/false (False is correct); the second is P(heads)=1/2; the third is the six outcomes {1,2,3,4,5,6}. After the response is saved, explanatory feedback remains visible for 12 seconds before automatic resume. Students can request more reading time or continue immediately. Feedback remains beneath the video. Time stamps in the editor are relative to the trimmed segment. The original video is embedded with start/end bounds; no downloaded video file was created or altered.

The default teacher view is a roster of slide representations, per-activity progress bubbles, and saved drawings. Student details and printed reports include text/drawing snapshots grouped by slide. Work is saved before moving slides and restored by slide; these are saved samples, not screen recordings.

The new 4:10 video plus three feedback pauses needs more than the old 2-minute video allocation. For a strict 20-minute micro-teaching presentation, move the full games to independent follow-up or shorten discussion time; do not assume the previous timeline still fits unchanged.

## Vercel deployment

Vercel support is now provided by `api/index.py`, `vercel.json`, and `postgres_store.py`. It requires a durable PostgreSQL `DATABASE_URL` and a configured `TEACHER_PASSWORD`; SQLite is only used locally. See [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md) for exact account setup, deployment commands, and verification. No public deployment has been created from this workspace.
