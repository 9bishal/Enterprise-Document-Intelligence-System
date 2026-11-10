#!/usr/bin/env python3
"""Watchdog for the IntraDoc AI backend on Render.

Environment variables:
  BACKEND_HEALTH_URL   Full health-check URL (required unless BACKEND_BASE_URL is set)
  BACKEND_BASE_URL     Base URL; /api/health/live is appended
  RENDER_API_KEY       Render API key with permission to restart the service
  RENDER_SERVICE_ID    Render service ID (srv-...)
  RENDER_API_BASE      Default: https://api.render.com/v1
  HEALTH_RETRIES       Default: 3
  HEALTH_RETRY_DELAY   Seconds, default: 20
  HEALTH_TIMEOUT       Seconds, default: 120
  RESTART_GRACE_SECONDS Default: 30
  RECOVERY_CHECKS      Default: 6
  RECOVERY_DELAY       Seconds, default: 30
  NOTIFY_WEBHOOK_URL   Optional Slack/Discord-style webhook
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def health_url() -> str:
    explicit = os.getenv("BACKEND_HEALTH_URL", "").strip()
    if explicit:
        return explicit
    base = os.getenv("BACKEND_BASE_URL", "").strip().rstrip("/")
    if base:
        return f"{base}/api/health/live"
    raise SystemExit("Set BACKEND_HEALTH_URL or BACKEND_BASE_URL")


def request(url: str, method: str = "GET", headers=None, body=None, timeout: int = 120):
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers=headers or {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def check_health(url: str) -> bool:
    retries = env_int("HEALTH_RETRIES", 3)
    delay = env_int("HEALTH_RETRY_DELAY", 20)
    timeout = env_int("HEALTH_TIMEOUT", 120)

    for attempt in range(1, retries + 1):
        try:
            status, payload = request(url, timeout=timeout)
            if 200 <= status < 300:
                print(f"[watchdog] healthy (attempt {attempt}): {payload[:200]}")
                return True
            print(f"[watchdog] unhealthy status {status} (attempt {attempt}): {payload[:200]}")
        except Exception as exc:
            print(f"[watchdog] health request failed (attempt {attempt}): {exc}")
        if attempt < retries:
            time.sleep(delay)
    return False


def restart_render() -> bool:
    api_key = os.getenv("RENDER_API_KEY", "").strip()
    service_id = os.getenv("RENDER_SERVICE_ID", "").strip()
    if not api_key or not service_id:
        print("[watchdog] RENDER_API_KEY/RENDER_SERVICE_ID not set; skipping restart")
        return False

    base = os.getenv("RENDER_API_BASE", "https://api.render.com/v1").rstrip("/")
    url = f"{base}/services/{service_id}/restart"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        status, payload = request(url, method="POST", headers=headers, body=b"{}", timeout=60)
    except Exception as exc:
        print(f"[watchdog] restart request failed: {exc}")
        return False

    if 200 <= status < 300:
        print(f"[watchdog] restart requested successfully (status {status})")
        return True
    print(f"[watchdog] restart failed (status {status}): {payload[:300]}")
    return False


def wait_for_recovery(url: str) -> bool:
    checks = env_int("RECOVERY_CHECKS", 6)
    delay = env_int("RECOVERY_DELAY", 30)
    timeout = env_int("HEALTH_TIMEOUT", 120)

    for attempt in range(1, checks + 1):
        time.sleep(delay)
        try:
            status, payload = request(url, timeout=timeout)
            if 200 <= status < 300:
                print(f"[watchdog] recovered after {attempt} check(s)")
                return True
            print(f"[watchdog] recovery check {attempt}: status {status}")
        except Exception as exc:
            print(f"[watchdog] recovery check {attempt} failed: {exc}")
    return False


def notify(message: str) -> None:
    webhook = os.getenv("NOTIFY_WEBHOOK_URL", "").strip()
    if not webhook:
        return
    payload = json.dumps({"text": message, "content": message}).encode("utf-8")
    try:
        request(
            webhook,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=payload,
            timeout=30,
        )
    except Exception as exc:
        print(f"[watchdog] notification failed: {exc}")


def main() -> int:
    url = health_url()
    if check_health(url):
        return 0

    print("[watchdog] backend is down; requesting a Render restart")
    notify("[IntraDoc] Backend health check failed; requesting restart.")
    if not restart_render():
        notify("[IntraDoc] Backend is down and could not be restarted automatically.")
        return 1

    time.sleep(env_int("RESTART_GRACE_SECONDS", 30))
    if wait_for_recovery(url):
        notify("[IntraDoc] Backend recovered after restart.")
        return 0

    notify("[IntraDoc] Backend did not recover after restart. Manual action required.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
