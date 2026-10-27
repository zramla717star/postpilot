# PostPilot v1

A small web app for creators to plan and schedule TikTok posts.
It is an independent tool — not affiliated with, endorsed by, or
using the logo of any social-media company.

**Current status: DRAFT / SANDBOX / DRY-RUN.**
The TikTok developer app (PostPilot, platform Web, Category
Productivity, Login Kit + Content Posting API, Direct Post ON)
is **not submitted and not approved**. Nothing in v1 posts,
uploads, or logs in to TikTok. No approval and no timeline is
promised here.

## What it does

- **Picture / carousel post:** 1–35 pictures, caption + hashtags.
- **Video post:** exactly 1 video file, caption + hashtags.
- **Daily capacity — separate per type:** up to **5 video posts
  per day AND 5 picture posts per day** (10 slots per day in
  total). Each post needs a separate time that day, across both
  types, so two posts never clash at the same instant.
- **You pick what to upload.** Every queued item has a
  user-selectable status, changeable before its scheduled time:
  - `Prepared` — the default for a new post. Queued, **not posted**.
  - `Selected` (Selected for upload) — the **only** status that
    is posted at its scheduled time (or logged in dry-run mode).
  - `Skipped` — queued, **not posted**.
  
  Prepared and Skipped items stay in the queue and are never
  auto-posted. Do not rely on a post going out unless you marked
  it Selected. Note: if you mark a past-due item Selected later,
  the scheduler will pick it up on its next check (every
  `SCHEDULER_INTERVAL_SECONDS`, default 60s) — so make your
  choice before the scheduled time for normal use.

## How the queue works

TikTok's native Content Posting API has **no
`scheduled_publish_time`** field, so PostPilot keeps its own
queue and its own timer:

1. You add a picture or video post, caption, hashtags, and a time.
2. It waits in the queue (`data/queue.json`, uploads in
   `data/uploads/`).
3. A background scheduler thread checks for due posts. A post is
   due only if it is still queued, marked **Selected**, and its
   scheduled time has arrived.
4. In dry-run mode the scheduler logs
   `DRY-RUN: would post video at <time>` or
   `DRY-RUN: would post pictures at <time>` to stdout and to
   `data/scheduler_log.txt`, marks the post `dry-run-logged`,
   and sends nothing to TikTok.

Video is the Content Posting API's primary flow. The picture /
carousel flow **must be tested first after approval** — it may
behave differently (for example as a carousel or as a
slideshow-style post), so do not rely on it for daily posting
until that test has passed.

## How to run locally

Requirements: Python 3.12+ only. No Flask, no paid service, no
exotic dependency. The app uses the Python standard library
(`http.server`). Pillow is needed only to regenerate the icon.

```bash
cd ~/workspace/postpilot
python3 app.py
```

Then open <http://127.0.0.1:8000/> — Home, Dashboard (`/app`),
Terms (`/terms`), Privacy (`/privacy`), health (`/health`),
queue JSON (`/api/queue`).

Regenerate the icon (optional):

```bash
python3 make_icon.py   # writes icon.png (1024x1024)
```

Stop with Ctrl+C.

## Environment variables

Copy `.env.example` to `.env` for local use. **Never commit a
real `.env`** (it is in `.gitignore`), never hardcode a key or
secret, and never share a client key/secret in chat or screenshots.

| Variable | Default | Meaning |
|---|---|---|
| `APPROVED` | empty (dry-run) | Set to `true` only after TikTok approval AND a review of the real API call. Anything else = dry-run. |
| `TIKTOK_CLIENT_KEY` | empty | TikTok developer app client key (owner supplies after approval). Placeholder only in this repo. |
| `TIKTOK_CLIENT_SECRET` | empty | TikTok developer app client secret. Never in code. |
| `TIKTOK_REDIRECT_URI` | empty | Must exactly match a Redirect URI configured in the TikTok app (Login Kit, Web). |
| `APP_BASE_URL` | empty | Public base URL of this app once hosted. |
| `HOST` | `127.0.0.1` | Bind address. Set `0.0.0.0` only on a host you control. |
| `PORT` | `8000` | Port to listen on. |
| `SCHEDULER_INTERVAL_SECONDS` | `60` | How often the scheduler checks for due Selected posts (minimum 10). |

## Dry-run vs approved mode

- **Dry-run (default, v1):** `APPROVED` is not `true`, or any
  TikTok credential is missing. Due **Selected** posts are
  logged only. Prepared/Skipped posts are not logged as posting
  at all — they simply stay queued.
- **Approved mode:** requires `APPROVED=true` AND all three
  TikTok credentials set. Even then, v1's real API call is a
  **stub** (`real_api_call_stub` in `app.py`) that only logs and
  sends nothing to TikTok. Wiring the actual Content Posting API
  call is a separate, reviewed step after approval. Never flip
  `APPROVED=true` with placeholder credentials.

## TikTok OAuth routes (safe-fail)

- `GET /auth/tiktok` — if approval/credentials are missing, it
  shows a plain "login is not available yet" message. If both
  are set, v1 still shows "not wired up" and attempts no login.
- `GET /auth/callback` — never logs, stores, or echoes back any
  code or token parameter, and completes no login in v1.

**No TikTok password is ever asked for, stored, or sent by this
app.** Login, when enabled, is TikTok OAuth (Login Kit) only.

## Free hosting plan — approved 28 Oct 2026 (zero investment, no card)

No paid host is used for now. The free model has two parts:

**(a) Public website on GitHub Pages — `docs/`.**
The `docs/` folder holds standalone `index.html`, `terms.html`,
and `privacy.html` with the same honest wording as the app's
Home/Terms/Privacy pages (picture AND video posts, 5 + 5 per
day, user-selected only, TikTok approval pending, no TikTok
password ever stored), linked to each other with relative
links so they work on Pages. Enable Pages from the `docs/`
folder in the repo settings after pushing. The Pages URL is
**not live until Pages is enabled — do not claim one before
then.** The expected pattern to verify once enabled is
`https://<github-username>.github.io/postpilot/` (replace the
placeholder with the real username and check it opens), with
Terms at `.../postpilot/terms.html` and Privacy at
`.../postpilot/privacy.html`. Those verified Pages URLs are
what go into the TikTok developer app as the Web/Desktop URL,
the Terms of Service URL, and the Privacy Policy URL.
This static site presents the product; the scheduling
dashboard itself runs in the full app and is shown in the
demo video — Pages does not run the Python dashboard.

**(b) Schedule check on GitHub Actions — every 30 minutes.**
`.github/workflows/postpilot-scheduler.yml` runs on a cron
(`*/30 * * * *`) plus manual `workflow_dispatch`. It checks
out the repo and runs `scripts/dry_run_check.py`, which
applies the `scheduler.py` rules and logs
`DRY-RUN: would post ...` lines for due Selected posts. It
calls TikTok never, uses no secrets at all, and needs none.
**Honest limits:** Actions cron timing is best-effort — a
run may start a few minutes late, so a post may be checked a
few minutes late. Private-repo Actions minutes are limited
on the free tier, so the job is kept short (one checkout,
one short Python run, standard library only). The workflow
file must be added through the GitHub **website**, not by an
API push: the stored GitHub token has no `workflow` scope,
so API pushes of workflow files fail, and the push helper
must never be run without first reading its source and
confirming the target repo (it has pushed to the wrong /
default repo before — see the workspace lesson in AGENTS.md).

**(c) Later paid upgrade path (only when earnings start).**
When the owner decides to pay, the same code can move to an
always-on host (for example a Render Starter instance) with
`HOST=0.0.0.0` and the host's port behind HTTPS, and the
TikTok URLs updated to the new host. No code change to the
queue rules is needed for that move. Do not pay for anything
now.

**Persistent queue storage — open follow-up, not solved silently.**
In v1 the queue lives in `data/queue.json` (git-ignored) and
uploads in `data/uploads/`. A GitHub Actions runner starts
fresh each run and does not keep `data/` between runs, so
the scheduled check normally finds no queue file and logs
"nothing due" — that is the correct dry-run behaviour for
v1, not a bug to paper over. For the live, post-approval
phase, persistent queue storage must be decided explicitly
(for example a repo-committed queue file, or a small free
database). No service is invented for it here, and no secret
is ever stored in the repo to make it work.

## Deployment notes (generic, no provider lock-in)

1. Choose any generic cloud host that can run a long-lived
   Python process (the scheduler must keep running for timed
   posts, even when the phone is off).
2. Copy this folder to the host, set the environment variables
   above (never bake secrets into the code or the repo), and run
   `python3 app.py` with `HOST=0.0.0.0` and the host's port.
   Put it behind HTTPS before enabling any real login — OAuth
   redirect URIs must use the hosted HTTPS URL.
3. The hosted URL is what goes into the TikTok developer app as
   the Web/Desktop URL, the Terms of Service URL
   (`<host>/terms`), the Privacy Policy URL (`<host>/privacy`),
   and the Login Kit Redirect URI (`<host>/auth/callback`).
4. No account was created, no code was pushed, and nothing was
   deployed by the author of this build — hosting and the GitHub
   repo name are decisions for the owner (see below).

## TikTok review checklist — all still pending

These are **not** done by this local build; they need hosting +
the owner's TikTok dashboard steps:

- [ ] Push non-workflow files to repo `postpilot` (private), add the workflow file via the GitHub website, enable Pages from `docs/`, and verify the live Pages URL (expected pattern in "Free hosting plan" above — do not claim it until it opens)
- [ ] Fill Web/Desktop URL in the TikTok app with the verified Pages URL
- [ ] Fill Terms of Service URL (`.../postpilot/terms.html`) and Privacy Policy URL (`.../postpilot/privacy.html`) from Pages
- [ ] Upload `icon.png` (1024x1024) as the app icon
- [ ] Fill the Login Kit Redirect URI with the hosted callback URL
- [ ] Write the app-review explanation (max 1000 chars, how
      Content Posting works for creators — not vague, not
      personal-only) and record a sandbox demo video (mp4/mov)
      showing the end-to-end flow: login (sandbox), add a
      picture post and a video post, mark items Selected, queue
      them, and the dry-run log
- [ ] Submit for review in the TikTok dashboard (app is Draft now)
- [ ] After approval: test 1 public picture post AND 1 public
      video post, verify the picture flow, then use daily posting

## Files

| File | Purpose |
|---|---|
| `app.py` | Web app: Home, Terms, Privacy, dashboard, queue, scheduler thread, safe-fail OAuth routes. Stdlib only. |
| `scheduler.py` | Pure queue rules: per-type daily quotas (5 + 5), separate times, selection filter, dry-run wording. No network, no TikTok calls. |
| `icon.png` | Original 1024x1024 app icon (generated by `make_icon.py`). No TikTok/social logo. |
| `make_icon.py` | Regenerates `icon.png` with Pillow. |
| `.env.example` | Placeholder env vars. Copy to `.env`; never commit a real one. |
| `.gitignore` | Excludes `.env` and `data/` (queue + uploads) from git. |
| `docs/index.html`, `docs/terms.html`, `docs/privacy.html` | Static public website for GitHub Pages (Home / Terms / Privacy, relative links). No dashboard, no secrets, no TikTok logo. |
| `scripts/dry_run_check.py` | Free-model scheduler checker used by GitHub Actions: due Selected posts only, dry-run log only, no TikTok call, no secrets. |
| `.github/workflows/postpilot-scheduler.yml` | GitHub Actions cron (every 30 min) + manual run. Local file only — add via the GitHub website, never by API push (token has no `workflow` scope). |
| `README.md` | This file. |

## Deliberately left out — and why

- **No phone-control / screen-tap / accessibility code.** That
  route was ruled out; PostPilot uses the official API only.
- **No real TikTok post, upload, or login.** No approval and no
  usable credentials exist yet; v1 is dry-run by design.
- **No GitHub push, no deployment, no TikTok submission.** Those
  need the owner's decisions below, and were not authorised in
  this build.
- **No Android/iOS app or store files.** The TikTok app is
  Web-only; a phone app would need store listings, package /
  bundle IDs, and signatures, and would make review harder.
- **No user email or private identifier** in code, docs, or UI.
- **No hardcoded, guessed, or invented client key, secret,
  redirect URI, website URL, or domain.** All come from env vars.
