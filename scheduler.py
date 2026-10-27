"""PostPilot scheduler / queue rules.

This module is pure logic on purpose: it never talks to TikTok,
never opens another app, and never performs a screen-tap or any
phone-control action. PostPilot uses the official TikTok
Content Posting API route only, and in v1 that route is stubbed
(see app.py): nothing is sent to TikTok.

Why an own queue exists
-----------------------
TikTok's native Content Posting API has no ``scheduled_publish_time``
field. So PostPilot keeps its own queue and its own timer: a post
is stored with a chosen time, and the scheduler thread in app.py
checks for due posts and acts on them at that time.

Modes
-----
* Dry-run (default): APPROVED is not "true", or TikTok credentials
  are missing. A due post is logged as "would post at <time>" and
  marked ``dry-run-logged``. Nothing leaves this server.
* Approved mode (not enabled in v1): APPROVED=true AND
  TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET / TIKTOK_REDIRECT_URI
  are all set. Even then, v1 only logs that a real API call would
  be made; the actual Content Posting API call is a stub that must
  be reviewed and explicitly wired up after TikTok approval.
  See app.py: ``real_api_call_stub``.
"""

from __future__ import annotations

from datetime import datetime

MAX_VIDEOS_PER_DAY = 5
MAX_PICTURES_PER_DAY = 5
MAX_IMAGES_PER_POST = 35
MAX_VIDEOS_PER_POST = 1
# Daily capacity is SEPARATE per type (updated 28 Oct 2026, replacing
# the earlier combined 5-per-day rule): up to 5 video posts per day
# AND up to 5 picture posts per day (10 slots per day in total).
# Each post still needs a separate time that day, across both types,
# so two posts never clash at the same instant.
#
# Selection (user-controlled, changeable before the scheduled time):
#   Prepared  — default for a new post; queued but NOT posted.
#   Selected  — the only selection that is posted at its time.
#   Skipped   — queued but NOT posted.
# Only items that are both still queued AND marked Selected are
# due. Prepared/Skipped items stay in the queue and are never
# auto-posted. Nothing is posted unless the user selected it.


def posts_on_day(posts, day: str) -> list:
    """Posts scheduled on a given YYYY-MM-DD day, in queue order."""
    return [p for p in posts if p.get("scheduled_date") == day]


def validate_new_post(posts, scheduled_date: str, scheduled_time: str,
                      image_count: int = 0, post_type: str = "pictures",
                      video_count: int = 0) -> str | None:
    """Return an error message, or None if the new post is allowed.

    ``post_type`` is "pictures" (1-35 pictures) or "video" (exactly
    1 video file). The daily quota counts both types together.
    """
    if post_type == "video":
        if video_count < 1:
            return "Add 1 video file."
        if video_count > MAX_VIDEOS_PER_POST:
            return f"Max {MAX_VIDEOS_PER_POST} video per post."
    elif post_type == "pictures":
        if image_count < 1:
            return "Add at least 1 picture."
        if image_count > MAX_IMAGES_PER_POST:
            return f"Max {MAX_IMAGES_PER_POST} pictures per post."
    else:
        return "Unknown post type. Choose pictures or video."
    if not scheduled_date or not scheduled_time:
        return "Pick a schedule date and time."
    day_posts = posts_on_day(posts, scheduled_date)
    active = [p for p in day_posts if p.get("status") == "queued"]
    # Quota is per type: 5 videos AND 5 picture posts per day.
    # Queued items of that type count towards the quota whatever
    # their selection is, because they occupy a slot for that day.
    limit = (MAX_VIDEOS_PER_DAY if post_type == "video"
             else MAX_PICTURES_PER_DAY)
    same_type = [p for p in active if p.get("post_type") == post_type]
    if len(same_type) >= limit:
        kind = "video" if post_type == "video" else "picture"
        return (f"Max {limit} {kind} posts per day. "
                "Pick another day, or delete a queued post.")
    if any(p.get("scheduled_time") == scheduled_time for p in active):
        return "That time is already used that day. Pick a separate time."
    return None


SELECTIONS = ("Prepared", "Selected", "Skipped")


def due_posts(posts, now: datetime) -> list:
    """Due posts: still queued, marked Selected, and time has come.

    Prepared and Skipped posts are deliberately excluded — they
    stay in the queue and are never auto-posted.
    """
    due = []
    for post in posts:
        if post.get("status") != "queued":
            continue
        if post.get("selection") != "Selected":
            continue
        try:
            when = datetime.fromisoformat(post["scheduled_iso"])
        except (KeyError, ValueError):
            continue
        if when <= now:
            due.append(post)
    return due


def action_for(approved: bool, credentials_configured: bool) -> str:
    """What the scheduler is allowed to do for a due post."""
    if approved and credentials_configured:
        return "approved-stub"
    return "dry-run"


def describe_action(action: str, post) -> str:
    when = post.get("scheduled_iso", "?")
    if post.get("post_type") == "video":
        what = "would post video at"
        detail = f"({post.get('video') or '1 video'}, "
    else:
        what = "would post pictures at"
        detail = f"({len(post.get('images', []))} picture(s), "
    detail += f"caption: {post.get('caption', '')[:80]!r}). "
    if action == "dry-run":
        return (f"DRY-RUN: {what} {when} {detail}"
                "Nothing was sent to TikTok — approval pending.")
    return (f"APPROVED-STUB: real TikTok Content Posting API call "
            f"is NOT wired up in v1 for post scheduled at {when}. "
            "Nothing was sent to TikTok.")
