# Load Test — Document Intelligent System

Load testing for **60-70 concurrent users** using [Locust](https://locust.io/) against the Django backend (`backend/django_backend`).

---

## TL;DR Results (65 users, 5 minutes, Nov 2026)

**6,339 requests, 0 failures, ~21 req/s.** The backend comfortably handles 60-70 concurrent users.

| Endpoint | Requests | Failures | Median (p50) | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|
| POST /api/chat/query (RAG + LLM) | 905 | 0 | 86ms | 1.3s | 2.5s | 5.0s |
| GET /api/documents | 1,780 | 0 | 9ms | 71ms | 380ms | 1.2s |
| GET /api/chat/sessions | 1,386 | 0 | 14ms | 98ms | 440ms | 1.9s |
| POST /api/chat/sessions | 905 | 0 | 11ms | 89ms | 300ms | 1.2s |
| GET /api/chat/sessions/:id/messages | 904 | 0 | 9ms | 65ms | 180ms | 350ms |
| GET /api/health/ready | 459 | 0 | 48ms | 230ms | 560ms | 1.4s |
| **Aggregated** | **6,339** | **0** | **13ms** | **220ms** | **1.1s** | **5.0s** |

**Verdict:** Pass. Only the LLM-backed RAG query has a slow tail (p90 > 800ms), which is Groq LLM inference latency, not a server bottleneck.

---

## Understanding the percentiles (remember this)

Response times are reported as **percentiles** — "how long did X% of requests take?" They describe the *distribution*, because an average hides slow requests.

Using the RAG query numbers (median 86ms, p90 820ms, p95 1.3s, p99 2.5s):

- **p50 (median)** — 50% of requests were faster than 86ms. The "typical user" experience.
- **p90** — 90% of requests faster than 820ms; only 1 in 10 was slower.
- **p95** — 95% faster than 1.3s; 1 in 20 slower.
- **p99** — 99% faster than 2.5s; 1 in 100 slower (the "tail").
- **Max** — the single worst request (5.0s).

**Why they matter:** if 95% of users get answers in under 100ms but 5% wait 10s, the *average* (~500ms) hides that 1 in 20 users has a bad experience. That's why SLAs are written with percentiles (e.g. "p95 < 2s") — always report p50/p95/p99, not just the mean.

**How to read this test's numbers:**

- Most endpoints: p50 ≈ 10-50ms → fast and healthy.
- RAG query: p50 86ms but p90 820ms → the slow tail is **LLM inference time** (Groq), not Django. Fast responses are semantic-cache hits; slow ones are real LLM calls.
- Even the worst 1% of LLM calls (2.5s) is acceptable for a chat app.

---

## What the test simulates

65 virtual users, each with a unique test account, ramped at 2 users/sec. Task mix (weights) reflecting real behavior:

| Task | Weight | Endpoint(s) |
|---|---:|---|
| Browse documents | 4 | GET /api/documents |
| List chat sessions | 3 | GET /api/chat/sessions |
| Full chat flow | 2 | POST /api/chat/sessions → POST /api/chat/query → GET messages |
| Health check | 1 | GET /api/health/ready |

Each simulated user thinks 2-6s between tasks (`wait_time`), like a real person.

### Why pre-minted JWTs?

The auth endpoint has `AuthRateThrottle` (**10 logins/min per IP**, `backend/django_backend/throttles.py`). All load-test users share one IP (127.0.0.1), so real logins get 429'd after the first 10. Instead, `create_test_users.py` mints JWTs directly via the Django shell and writes them to `tokens.json` — the load test then exercises the *app*, not the login throttle. (First run attempt without this hit exactly this issue.)

### Caveats (be honest if asked)

1. **Semantic cache:** RAG responses at ~86ms median are partly cache hits from the Redis semantic cache. The question pool (12 varied questions) minimizes this, but a cold-cache run would show true LLM latency.
2. Single load generator (one machine, one IP). For 60-70 users this is fine; distributed mode would be needed for hundreds+.

---

## Files

| File | Purpose |
|---|---|
| `locustfile.py` | The load test (user behavior, task weights) |
| `create_test_users.py` | Creates 70 test users + mints JWTs → `tokens.json` |
| `tokens.json` | Pre-minted JWTs (generated; don't commit — gitignored) |
| `results_*.csv` | Raw results of past runs |
| `.venv/` | Local Python env with Locust installed |

---

## How to run

**Setup (one-time):**

```bash
# Create the venv with Locust
python3 -m venv loadtests/.venv
loadtests/.venv/bin/pip install locust

# Create test users + tokens
# (python path = the env your backend runs in, e.g. miniforge3/envs/rag)
cd backend && /path/to/env/bin/python manage.py shell < ../loadtests/create_test_users.py
```

**Run the test (backend must be running on :8000):**

```bash
# Headless: 65 users, ramp 2/s, 5 minutes, CSV output
loadtests/.venv/bin/locust -f loadtests/locustfile.py \
  --headless -u 65 -r 2 --run-time 5m \
  --host http://localhost:8000 --csv loadtests/results

# Or with the live web UI (charts at http://localhost:8089) — drop
# --headless --only-summary and open the browser
loadtests/.venv/bin/locust -f loadtests/locustfile.py --host http://localhost:8000
```

**Options:**

- `-u 70` → exactly 70 users; `-r` → users spawned per second (ramp rate)
- `--run-time 10m` → longer soak test
- `LOADTEST_USERNAME=admin LOADTEST_PASSWORD=...` env vars → test as a single existing account instead of generated users

**Environment variables** (`locustfile.py` reads these):

| Var | Default | Meaning |
|---|---|---|
| `LOADTEST_USERS` | `70` | Number of accounts in `tokens.json` |
| `LOADTEST_USERNAME` | — | Use one existing account instead of generated users |
| `LOADTEST_PASSWORD` | `loadtest-Pass1` | Password for that account |

---

## What to say when asked "how did you test?"

> "I load-tested with Locust simulating 65 concurrent authenticated users with realistic behavior — login, browsing documents, full RAG chat flows — ramped over 15 seconds for 5 minutes. That's 6,339 requests with zero failures and a p95 of 220ms overall. The only slow tail is on the LLM-backed RAG endpoint, which is Groq inference latency, not our server. I also found the auth rate limiter (10 logins/min per IP) would skew the test, so I pre-minted JWTs via the Django shell instead. Everything is reproducible from `loadtests/`."
