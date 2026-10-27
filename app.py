#!/usr/bin/env python3
"""PostPilot v1 — a small web app for planning TikTok posts.

Official TikTok API route ONLY. This app never controls a phone,
never opens the TikTok app, and never taps, clicks, or automates
anything on a user's device. There is no screen-tap, accessibility,
or phone-control code anywhere in this project.

Status: DRAFT / SANDBOX / DRY-RUN by default.
  * The TikTok developer app is not approved yet.
  * No real post, upload, or OAuth login is attempted.
  * The scheduler logs "would post ..." instead of calling TikTok.
  * The real Content Posting API call is a stub, gated behind
    APPROVED=true AND all TikTok env credentials being set.
    Even with that gate on, v1 does not send anything to TikTok;
    wiring the real call is a separate, reviewed step after approval.
  * No TikTok password is ever asked for, stored, or sent anywhere.
    Login, when it exists, is TikTok OAuth (Login Kit) only.

Run:
    python3 app.py
Then open http://127.0.0.1:8000/

Environment (see .env.example; all TikTok values are placeholders
until the owner supplies them after approval):
    PORT, HOST, SCHEDULER_INTERVAL_SECONDS, APPROVED,
    TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REDIRECT_URI,
    APP_BASE_URL

Post types (separate daily quotas, updated 28 Oct 2026):
  * pictures — 1 to 35 pictures (carousel), caption + hashtags,
    up to 5 picture posts per day
  * video    — exactly 1 video file, caption + hashtags,
    up to 5 video posts per day
That is 10 scheduled slots per day in total, each at a separate
time. Every queued item has a user-selectable status — Prepared,
Selected for upload, or Skipped — changeable before its scheduled
time. ONLY items marked Selected are posted (or, in dry-run mode,
logged as "would post …"). Prepared and Skipped items stay in
the queue and are never auto-posted.
Video is the Content Posting API's primary flow; the picture /
carousel flow must be tested first after approval, because it
may behave differently (for example as a carousel or as a
slideshow-style post). Dry-run logs say which type would post,
and only for Selected items.
"""

from __future__ import annotations

import cgi
import html
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

from scheduler import (
    SELECTIONS,
    action_for,
    describe_action,
    due_posts,
    validate_new_post,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
QUEUE_FILE = os.path.join(DATA_DIR, "queue.json")
LOG_FILE = os.path.join(DATA_DIR, "scheduler_log.txt")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def load_dotenv() -> None:
    """Load a local .env file if present (simple parser, no secrets
    are ever written by this app — .env is the owner's own file)."""
    path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


load_dotenv()


def is_approved() -> bool:
    return os.environ.get("APPROVED", "").strip().lower() == "true"


def credentials_configured() -> bool:
    return all(
        os.environ.get(k, "").strip()
        for k in (
            "TIKTOK_CLIENT_KEY",
            "TIKTOK_CLIENT_SECRET",
            "TIKTOK_REDIRECT_URI",
        )
    )


def mode_name() -> str:
    if is_approved() and credentials_configured():
        return "approved-stub (real API call NOT wired up in v1)"
    return "sandbox / dry-run — TikTok approval pending"


# ---------------------------------------------------------------- queue
_queue_lock = threading.Lock()


def load_queue() -> list:
    if not os.path.exists(QUEUE_FILE):
        return []
    try:
        with open(QUEUE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_queue(posts: list) -> None:
    tmp = QUEUE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2)
    os.replace(tmp, QUEUE_FILE)


def log_scheduler(message: str) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}\n"
    print(line, end="")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def real_api_call_stub(post: dict) -> None:
    """Placeholder for the real Content Posting API call.

    Deliberately does nothing network-related in v1. It is only
    reached when APPROVED=true AND credentials are set, and even
    then it only logs. The real call must be reviewed and wired
    up after TikTok approval — never enabled blindly.
    """
    log_scheduler(
        "APPROVED-STUB: real TikTok API call NOT sent in v1 for post "
        f"{post.get('id')} scheduled at {post.get('scheduled_iso')}."
    )


def scheduler_loop() -> None:
    interval = int(os.environ.get("SCHEDULER_INTERVAL_SECONDS", "60"))
    while True:
        time.sleep(max(10, interval))
        try:
            with _queue_lock:
                posts = load_queue()
                due = due_posts(posts, datetime.now())
                if not due:
                    continue
                action = action_for(is_approved(), credentials_configured())
                for post in due:
                    log_scheduler(describe_action(action, post))
                    if action == "approved-stub":
                        real_api_call_stub(post)
                        post["status"] = "approved-stub-logged"
                    else:
                        post["status"] = "dry-run-logged"
                save_queue(posts)
        except Exception as exc:  # scheduler must never crash the app
            log_scheduler(f"Scheduler error (safe, continuing): {exc}")


# ---------------------------------------------------------------- HTML
def esc(text) -> str:
    return html.escape(str(text or ""))


def page(title: str, body: str) -> bytes:
    banner = (
        "<div style='background:#fff3cd;border:1px solid #e6c87a;"
        "padding:10px 14px;border-radius:8px;margin-bottom:16px'>"
        f"<b>Mode: {esc(mode_name())}.</b> Nothing is posted to TikTok "
        "in this mode. Approval is pending, and no TikTok password "
        "is ever stored here.</div>"
    )
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — PostPilot</title>
<style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:32px auto;
padding:0 16px;line-height:1.5;color:#1c2430}}a{{color:#0b5cab}}
input,textarea,select{{width:100%;padding:8px;margin:4px 0 12px;box-sizing:border-box}}
button{{padding:10px 18px;background:#0b2a4a;color:#fff;border:0;border-radius:8px;cursor:pointer}}
.card{{border:1px solid #d5dce5;border-radius:10px;padding:14px;margin:12px 0}}
nav a{{margin-right:14px}}</style></head><body>
<nav><a href="/">Home</a><a href="/app">Dashboard</a>
<a href="/terms">Terms</a><a href="/privacy">Privacy</a></nav>
<h1>PostPilot</h1>{banner}{body}
<p><small>PostPilot is an independent scheduling tool. It is not
affiliated with, endorsed by, or using the logo of any social-media
company.</small></p></body></html>"""
    return doc.encode("utf-8")


HOME_BODY = """
<p>PostPilot helps creators plan and schedule picture posts and
video posts with captions in one place — up to 5 video posts per
day AND up to 5 picture posts per day, each at a separate time.</p>
<h2>Two post types, separate daily quotas</h2>
<ul>
<li><b>Picture / carousel post:</b> up to 35 pictures, caption + hashtags — max 5 per day.</li>
<li><b>Video post:</b> one video file, caption + hashtags — max 5 per day.</li>
</ul>
<p>That is 10 scheduled slots per day in total. You pick what to
upload: every queued item is marked Prepared, Selected for upload,
or Skipped, and you can change that choice before its scheduled
time. Only Selected items are posted at their time; Prepared and
Skipped items stay in the queue and are never auto-posted.</p>
<p>The queue runs on this app's own timer, because TikTok's Content
Posting API has no scheduled-publish time of its own: PostPilot
stores the time you choose and triggers the post at that time.</p>
<p><b>Important:</b> video is the Content Posting API's primary flow.
The picture / carousel flow is to be tested first after TikTok
approval, before relying on it for daily posting.</p>
<h2>How it works (official route only)</h2>
<ol>
<li>You add pictures or a video, a caption, hashtags, and a time.</li>
<li>The post waits in your queue (max 5 per day, separate times).</li>
<li>At the scheduled time, in dry-run mode, PostPilot logs
"would post video at …" or "would post pictures at …" — nothing
is sent to TikTok until approval and credentials are in place.</li>
<li>After approval, you connect your TikTok account through TikTok's
own OAuth login. Your TikTok password is never typed into, stored
by, or sent through PostPilot.</li>
</ol>
<p><a href="/app"><button>Open the dashboard</button></a></p>
"""

TERMS_BODY = """
<h2>Terms of Service</h2>
<p>PostPilot is a scheduling tool for creators. It lets you prepare
picture posts (up to 35 pictures) and video posts (one video),
with captions and hashtags, and queue up to 5 video posts per day
AND up to 5 picture posts per day at separate times. You choose
what to upload: each queued item is Prepared, Selected for upload,
or Skipped, and only Selected items are posted at their time.</p>
<p><b>TikTok approval.</b> Posting to TikTok through PostPilot
requires TikTok's approval of this app and your consent through
TikTok's own login. Until approval is granted, PostPilot runs in
sandbox / dry-run mode and sends nothing to TikTok.</p>
<p><b>Your content.</b> You are responsible for the pictures,
videos, captions, and hashtags you upload. Only upload content you
have the right to post, and follow TikTok's rules for the account
you connect.</p>
<p><b>No password storage.</b> PostPilot never asks for, stores,
or transmits your TikTok password. Any TikTok connection uses
TikTok's OAuth login only.</p>
<p><b>No guarantees.</b> PostPilot does not guarantee TikTok
approval, posting times after approval, reach, or monetisation.
Scheduled times are best-effort: the app's own queue triggers
posts at the chosen times once the approved connection is live.</p>
<p><b>Video vs pictures.</b> Video is the Content Posting API's
primary flow. The picture / carousel flow is to be tested first
after approval, and may behave differently from video posting.</p>
"""

PRIVACY_BODY = """
<h2>Privacy Policy</h2>
<p><b>What PostPilot stores:</b> the scheduled posts you create —
post type (pictures or video), uploaded picture/video files for
scheduling, captions, hashtags, and scheduled times — plus your
choice for each post (Prepared, Selected for upload, or Skipped)
and the queue status (queued, dry-run-logged, and so on).</p>
<p><b>TikTok login.</b> When TikTok approval is in place, you may
connect your TikTok account through TikTok's own OAuth login.
PostPilot never asks for or stores your TikTok password. Any
OAuth token issued by TikTok would be stored only to keep your
connection working and to refresh it, and only after approval
and your consent. In v1 (dry-run mode) no OAuth token is stored,
because the login flow is not enabled.</p>
<p><b>What PostPilot does not do:</b> it does not sell your data,
does not read your TikTok password, and does not control your
phone or any other app. Nothing is posted to TikTok in dry-run
mode.</p>
<p><b>Deleting your data.</b> You can delete a queued post from
the dashboard. To fully remove your scheduled posts, delete all
queued posts and, after any future TikTok connection, revoke
PostPilot's access in your TikTok settings.</p>
<p><b>Hosting.</b> In v1 this app runs locally or on a generic
cloud host chosen by the owner. The host's own privacy terms
apply to server logs in addition to this policy.</p>
"""


def dashboard_body(error: str = "") -> str:
    with _queue_lock:
        posts = load_queue()
    err = f"<div style='color:#a00'><b>{esc(error)}</b></div>" if error else ""
    cards = ""
    if not posts:
        cards = "<p>No posts in the queue yet.</p>"
    for p in posts:
        if p.get("post_type") == "video":
            media = f"Video: {esc(p.get('video') or '1 video')}"
        else:
            media = f"{len(p.get('images', []))} picture(s)"
        current = p.get("selection") or "Prepared"
        options = "".join(
            f"<option value='{s}'{' selected' if s == current else ''}>{s}</option>"
            for s in SELECTIONS
        )
        cards += (
            "<div class='card'>"
            f"<b>{esc(p.get('post_type', 'pictures'))}</b> — {media}<br>"
            f"Scheduled: {esc(p.get('scheduled_iso'))} "
            f"(queue: {esc(p.get('status'))})<br>"
            f"Caption: {esc(p.get('caption'))}<br>"
            f"Hashtags: {esc(p.get('hashtags'))}<br>"
            "<form method='post' action='/app/selection' style='margin-top:8px'>"
            f"<input type='hidden' name='id' value='{esc(p.get('id'))}'>"
            f"<label>Your choice: <select name='selection'>{options}</select></label>"
            "<button type='submit'>Save choice</button></form>"
            "<form method='post' action='/app/delete' style='margin-top:8px'>"
            f"<input type='hidden' name='id' value='{esc(p.get('id'))}'>"
            "<button type='submit'>Delete</button></form></div>"
        )
    return f"""
<h2>Dashboard — sandbox / demo queue</h2>
<p>This is a demo queue. In dry-run mode, due posts are logged as
"would post …" and nothing is sent to TikTok.</p>
<p><b>You pick what to upload.</b> New posts start as
<i>Prepared</i> — they are NOT posted. Change a post to
<i>Selected for upload</i> before its scheduled time and only
then will it post (or be logged in dry-run mode). <i>Skipped</i>
posts stay in the queue and are never posted. Daily limits:
5 videos + 5 picture posts per day, separate times.</p>
{err}
<form method="post" action="/app/add" enctype="multipart/form-data">
<label>Post type</label>
<select name="post_type">
<option value="pictures">Picture / carousel (up to 35 pictures)</option>
<option value="video">Video (one video file)</option>
</select>
<label>Pictures (for a picture post)</label>
<input type="file" name="pictures" multiple accept="image/*">
<label>Video (for a video post)</label>
<input type="file" name="video" accept="video/*">
<label>Caption</label>
<textarea name="caption" rows="3"></textarea>
<label>Hashtags</label>
<input type="text" name="hashtags" placeholder="#example #postpilot">
<label>Schedule date and time</label>
<input type="datetime-local" name="scheduled" required>
<button type="submit">Add to queue (max 5 videos + 5 pictures per day, separate times)</button>
</form>
<h2>Queue ({len(posts)} post(s))</h2>
{cards}
<p><a href="/auth/tiktok">Connect TikTok (currently disabled:
approval pending / credentials not set in v1)</a></p>
"""


def safe_filename(name: str) -> str:
    name = os.path.basename(name or "file")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name or "file"


def save_uploaded(field, post_id: str, index: int) -> str | None:
    """Save one uploaded file, return its stored filename or None."""
    if field is None or not getattr(field, "filename", None):
        return None
    stored = f"{post_id}_{index}_{safe_filename(field.filename)}"
    path = os.path.join(UPLOAD_DIR, stored)
    # FieldStorage file may be a real file or in-memory stream.
    data = field.file.read()
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)
    return stored


# ---------------------------------------------------------------- handler
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep stdout for scheduler logs only
        pass

    def send_html(self, body: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/":
            self.send_html(page("Home", HOME_BODY))
        elif path == "/terms":
            self.send_html(page("Terms of Service", TERMS_BODY))
        elif path == "/privacy":
            self.send_html(page("Privacy Policy", PRIVACY_BODY))
        elif path == "/app":
            error = query.get("error", [""])[0]
            self.send_html(page("Dashboard", dashboard_body(error)))
        elif path == "/health":
            body = (
                f"ok mode={mode_name()} "
                f"approved={is_approved()} "
                f"credentials_configured={credentials_configured()}\n"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/queue":
            with _queue_lock:
                posts = load_queue()
            body = json.dumps(posts, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/auth/tiktok":
            if not credentials_configured() or not is_approved():
                body = (
                    "<h2>TikTok login is not available yet</h2>"
                    "<p>TikTok approval is pending and/or TikTok "
                    "credentials are not configured. PostPilot stays "
                    "in sandbox / dry-run mode until both are in place. "
                    "Your TikTok password is never requested here.</p>"
                    "<p><a href='/app'>Back to dashboard</a></p>"
                )
            else:
                body = (
                    "<h2>TikTok login — not wired up in v1</h2>"
                    "<p>Approval and credentials are set, but the real "
                    "OAuth flow is deliberately not enabled in v1 until "
                    "it is reviewed. No login was attempted and no token "
                    "was stored.</p>"
                    "<p><a href='/app'>Back to dashboard</a></p>"
                )
            self.send_html(page("Connect TikTok", body))
        elif path == "/auth/callback":
            # Never log, store, or echo back any code/token parameter.
            body = (
                "<h2>TikTok login callback — not completed in v1</h2>"
                "<p>No token was stored and no password was requested. "
                "The OAuth callback flow will only be enabled after "
                "TikTok approval and a review of the login code.</p>"
                "<p><a href='/app'>Back to dashboard</a></p>"
            )
            self.send_html(page("TikTok callback", body))
        else:
            self.send_html(page("Not found", "<p>Page not found.</p>"), 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/app/selection":
            length = int(self.headers.get("Content-Length", "0"))
            data = parse_qs(self.rfile.read(length).decode("utf-8"))
            post_id = data.get("id", [""])[0]
            selection = data.get("selection", [""])[0]
            if selection not in SELECTIONS:
                self.redirect("/app")
                return
            with _queue_lock:
                posts = load_queue()
                for p in posts:
                    if p.get("id") == post_id and p.get("status") == "queued":
                        p["selection"] = selection
                save_queue(posts)
            self.redirect("/app")
            return
        if parsed.path == "/app/delete":
            length = int(self.headers.get("Content-Length", "0"))
            data = parse_qs(self.rfile.read(length).decode("utf-8"))
            post_id = data.get("id", [""])[0]
            with _queue_lock:
                posts = [p for p in load_queue() if p.get("id") != post_id]
                save_queue(posts)
            self.redirect("/app")
            return
        if parsed.path != "/app/add":
            self.send_html(page("Not found", "<p>Page not found.</p>"), 404)
            return
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            },
        )

        def field(name: str) -> str:
            item = form.getvalue(name)
            return item if isinstance(item, str) else ""

        post_type = field("post_type") or "pictures"
        caption = field("caption").strip()
        hashtags = field("hashtags").strip()
        scheduled = field("scheduled").strip()  # e.g. 2026-10-28T14:30
        if "T" in scheduled:
            scheduled_date, scheduled_time = scheduled.split("T", 1)
        else:
            scheduled_date, scheduled_time = scheduled, ""
        scheduled_time = scheduled_time[:5]  # HH:MM

        post_id = uuid.uuid4().hex[:12]
        images: list[str] = []
        video: str | None = None
        if post_type == "pictures":
            raw = form["pictures"] if "pictures" in form else []
            items = raw if isinstance(raw, list) else [raw]
            for i, item in enumerate(items):
                stored = save_uploaded(item, post_id, i)
                if stored:
                    images.append(stored)
            image_count, video_count = len(images), 0
        elif post_type == "video":
            stored = save_uploaded(
                form["video"] if "video" in form else None, post_id, 0
            )
            if stored:
                video = stored
            image_count, video_count = 0, 1 if video else 0
        else:
            self.redirect("/app?error=" + urlencode({"x": "Unknown post type"})[2:])
            return

        with _queue_lock:
            posts = load_queue()
            error = validate_new_post(
                posts, scheduled_date, scheduled_time,
                image_count=image_count, post_type=post_type,
                video_count=video_count,
            )
            if error:
                self.redirect("/app?error=" + urlencode({"x": error})[2:])
                return
            post = {
                "id": post_id,
                # New posts start as Prepared: never auto-posted
                # until the user explicitly marks them Selected.
                "selection": "Prepared",
                "post_type": post_type,
                "images": images,
                "video": video,
                "caption": caption,
                "hashtags": hashtags,
                "scheduled_date": scheduled_date,
                "scheduled_time": scheduled_time,
                "scheduled_iso": f"{scheduled_date}T{scheduled_time}",
                "status": "queued",
            }
            posts.append(post)
            save_queue(posts)
        self.redirect("/app")


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    threading.Thread(target=scheduler_loop, daemon=True).start()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"PostPilot v1 running at http://{host}:{port}/  mode={mode_name()}")
    print("Press Ctrl+C to stop. TikTok approval pending — dry-run only.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
