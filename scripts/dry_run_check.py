"""PostPilot free-model dry-run scheduler check.

Run by GitHub Actions every 30 minutes (see
.github/workflows/postpilot-scheduler.yml) and runnable locally:

    python3 scripts/dry_run_check.py

What it does:
- Loads data/queue.json if it exists (local runs only; a GitHub
  Actions runner starts with a fresh checkout, so the file is
  normally absent there — see the README "Free hosting plan"
  note on persistent queue storage).
- Uses scheduler.py rules: only posts that are still queued AND
  marked Selected AND whose scheduled time has arrived are due.
- Prints "DRY-RUN: would post ..." lines for due posts.
- NEVER calls TikTok, NEVER needs a client key/secret/token,
  NEVER reads any password, and NEVER posts anything.

This is deliberately a checker, not a poster. The real Content
Posting API call is a separate, post-approval step that must be
reviewed on its own — it is not wired up in v1.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from the repo root: scripts/ imports scheduler.py
# from the postpilot folder.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scheduler import describe_action, due_posts  # noqa: E402


def main() -> int:
    queue_file = ROOT / "data" / "queue.json"
    if not queue_file.exists():
        print("DRY-RUN CHECK: no queue file found (data/queue.json).")
        print("Nothing due. Nothing was sent to TikTok — approval pending.")
        return 0
    try:
        posts = json.loads(queue_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"DRY-RUN CHECK: could not read queue file: {exc}")
        return 0
    if not isinstance(posts, list):
        print("DRY-RUN CHECK: queue file is not a list. Nothing due.")
        return 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # scheduled_iso values are stored as naive local datetimes in v1;
    # comparing against UTC here is only for the dry-run log, and
    # the checker never posts, so a timezone skew cannot cause a
    # real post in this mode.
    due = due_posts(posts, now)
    if not due:
        print(f"DRY-RUN CHECK: {len(posts)} queued post(s), 0 due Selected.")
        print("Nothing was sent to TikTok — approval pending.")
        return 0
    for post in due:
        print(describe_action("dry-run", post))
    print(f"DRY-RUN CHECK: {len(due)} due Selected post(s) logged.")
    print("Nothing was sent to TikTok — approval pending.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
