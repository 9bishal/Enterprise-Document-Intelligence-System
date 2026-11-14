"""
Load test for the Django backend (60-70 concurrent users).

Uses pre-minted JWTs from loadtests/tokens.json (created by
create_test_users.py) so the run exercises the app, not the per-IP
auth rate throttle (10 logins/min from one machine would 429 anyway).

Usage (from repo root):
    # 1. One-time setup: create users + mint tokens
    #    (python path = your backend env, e.g. the conda env running Django)
    cd backend && /path/to/env/bin/python manage.py shell < ../loadtests/create_test_users.py

    # 2. Run headless: 65 users, ramping 2/s, 5 minutes
    ../loadtests/.venv/bin/locust -f loadtests/locustfile.py \
        --headless -u 65 -r 2 --run-time 5m --host http://localhost:8000

Or open the web UI (http://localhost:8089):
    ../loadtests/.venv/bin/locust -f loadtests/locustfile.py --host http://localhost:8000

Env vars:
    LOADTEST_USERS      number of test accounts in tokens.json (default 70)
    LOADTEST_USERNAME   use one existing account instead of generated users
    LOADTEST_PASSWORD   password for that account (default loadtest-Pass1)
"""
import json
import os
import random
import uuid
from itertools import count

from locust import HttpUser, between, task

NUM_USERS = int(os.getenv("LOADTEST_USERS", "70"))
SINGLE_USERNAME = os.getenv("LOADTEST_USERNAME")
SINGLE_PASSWORD = os.getenv("LOADTEST_PASSWORD", "loadtest-Pass1")
TOKENS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tokens.json")

QUESTIONS = [
    "Summarize the key points of the documents in one paragraph.",
    "What are the main topics covered?",
    "Give me a brief overview of the content.",
    "What conclusions can be drawn from the documents?",
    "List the most important dates and numbers mentioned.",
    "Who are the main people or organizations mentioned?",
    "What risks or challenges are described?",
    "What recommendations does the content make?",
    "Compare the different sections and highlight differences.",
    "Explain the methodology described in the documents.",
    "What examples are provided to support the arguments?",
    "What follow-up actions are suggested?",
]

_user_counter = count()

with open(TOKENS_FILE) as f:
    TOKENS = json.load(f)
USERNAMES = list(TOKENS.keys())


class DocumentUser(HttpUser):
    wait_time = between(2, 6)

    def on_start(self):
        if SINGLE_USERNAME:
            self.username = SINGLE_USERNAME
            self.client.headers["Authorization"] = (
                f"Bearer {TOKENS[SINGLE_USERNAME]['access']}"
            )
        else:
            self.username = USERNAMES[next(_user_counter) % NUM_USERS]
            self.client.headers["Authorization"] = (
                f"Bearer {TOKENS[self.username]['access']}"
            )
        self.session_id = None

    @task(4)
    def list_documents(self):
        self.client.get("/api/documents", name="/api/documents [GET]")

    @task(3)
    def list_sessions(self):
        self.client.get("/api/chat/sessions", name="/api/chat/sessions [GET]")

    @task(2)
    def chat_flow(self):
        """Realistic chat flow: create session -> ask RAG question -> read history."""
        with self.client.post(
            "/api/chat/sessions",
            json={"name": f"Load Test {uuid.uuid4().hex[:8]}"},
            name="/api/chat/sessions [POST]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                self.session_id = resp.json().get("id")
                resp.success()
            else:
                resp.failure(f"create session failed: {resp.status_code}")
                return

        with self.client.post(
            "/api/chat/query",
            json={
                "session_id": self.session_id,
                "question": random.choice(QUESTIONS),
            },
            name="/api/chat/query (RAG + LLM)",
            timeout=90,
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"rag query failed: {resp.status_code}")

        self.client.get(
            f"/api/chat/sessions/{self.session_id}/messages",
            name="/api/chat/sessions/:id/messages",
        )

    @task(1)
    def health_check(self):
        self.client.get("/api/health/ready", name="/api/health/ready")
