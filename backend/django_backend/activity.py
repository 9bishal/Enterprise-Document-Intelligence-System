import json
import logging
import os
import queue
import threading
import time
import urllib.request

WEBHOOK_URL = os.getenv("DISCORD_ACTIVITY_WEBHOOK_URL", "").strip()
ENABLED = os.getenv("DISCORD_ACTIVITY_ENABLED", "1").lower() not in ("0", "false", "no")
_QUEUE: "queue.Queue[str]" = queue.Queue(maxsize=200)
_WORKER_STARTED = False
_LOCK = threading.Lock()
_LOGGER = logging.getLogger(__name__)


def _worker() -> None:
    while True:
        message = _QUEUE.get()
        try:
            payload = {
                "content": message[:1900],
                "username": "IntraDoc Activity",
                "allowed_mentions": {"parse": []},
            }
            request = urllib.request.Request(
                WEBHOOK_URL,
                data=json.dumps(payload).encode("utf-8"),
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "IntraDoc-Activity/1.0",
                },
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status >= 300:
                    _LOGGER.warning("Discord activity webhook returned %s", response.status)
        except Exception as exc:
            _LOGGER.warning("Discord activity webhook failed: %s", exc)
        finally:
            _QUEUE.task_done()
            time.sleep(1.5)


def _ensure_worker() -> None:
    global _WORKER_STARTED
    if _WORKER_STARTED:
        return
    with _LOCK:
        if not _WORKER_STARTED:
            threading.Thread(target=_worker, name="discord-activity", daemon=True).start()
            _WORKER_STARTED = True


def _clean(value: str, limit: int = 160) -> str:
    return str(value or "").replace("`", "'").replace("\n", " ").strip()[:limit]


def notify_activity(action: str, username: str = "", detail: str = "") -> None:
    """Queue a user/admin activity event for the Discord activity webhook."""
    if not ENABLED or not WEBHOOK_URL:
        return
    lines = [f"**[IntraDoc]** `{_clean(action, 60)}`"]
    if username:
        lines.append(f"User: `{_clean(username, 60)}`")
    if detail:
        lines.append(_clean(detail, 500))
    message = "\n".join(lines)
    _ensure_worker()
    try:
        _QUEUE.put_nowait(message)
    except queue.Full:
        _LOGGER.warning("Discord activity queue is full; dropping event %s", action)
