# Deploy Chance Studio to Vercel

The app supports a Vercel Python function with durable PostgreSQL storage and an explicitly selected static asset directory. Local development continues to use SQLite unless DATABASE_URL is set. The PostgreSQL path passed the same seven integration tests against a real temporary PostgreSQL server.

## Required account setup

1. Create/link the Vercel project. Use Framework Preset **Other** and keep the build/output settings from `vercel.json`.
2. Provision a PostgreSQL database, for example through the Neon integration in Vercel Marketplace. Use the provider's pooled connection URL with TLS enabled.
3. Set these in Vercel Project Settings → Environment Variables, for both Preview and Production as needed:
   - `DATABASE_URL`: PostgreSQL connection URL. Enter securely; do not commit it.
   - `TEACHER_PASSWORD`: the teacher password. Required on Vercel; the server will not silently fall back to a default.
   - `CLASS_CODE`: `WALAA9` or the class code you choose.
4. Deploy from the directory containing `vercel.json` with `npx vercel` (preview), sign in when prompted, then `npx vercel --prod` after validating the preview. Or connect a Git repository containing these changes and deploy from the dashboard. These workspace changes have not been pushed to GitHub.

No Vercel account/token or hosted database connection is configured in this workspace, so no deployment URL has been created. Never paste account tokens or database passwords into chat.

## What gets published

`scripts/build_static.py` copies only the HTML, JS, CSS, lesson plan, and local MathJax into `public/`. Classroom data, source files, tests, and reports are not public assets. `/api/*` routes to `api/index.py`; it initializes the schema on first use and fails with HTTP 503 if required configuration is missing. Teacher username remains `walaa`.

Use a fresh database for the first hosted classroom. Existing local SQLite records are not migrated by deployment. Keep the local database as a backup; do not delete it. All new hosted student records persist in PostgreSQL across Vercel function instances and deployments. The supplied video and three checkpoints are loaded only when a new database is initialized; existing teacher edits are preserved.

## Release verification

- `/api/health` returns HTTP 200 with `{"ok":true}`.
- Teacher login succeeds with the configured password.
- A student in a separate browser joins and appears in the roster.
- Text/drawing, feedback, video responses, and quiz progress survive a page reload and a new serverless instance.
- Verify actual YouTube playback on the deployed domain, trimming from 8 to 258 source seconds, and pauses at relative 105/215/227 seconds. The development environment blocks the YouTube embed with HTTP 403; its player logic was tested using a controlled player.
- Print a class report and inspect Arabic, math, drawings, and answer evidence.

The shared transaction lock preserves consistent classroom scoring across instances. This is suitable for the current small-class workflow; measure database latency and polling volume before scaling to multiple classrooms. Login throttling is currently per function instance.
