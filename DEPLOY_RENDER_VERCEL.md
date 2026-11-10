# Deploy IntraDoc AI on Render + Vercel

> **Tracking note:** the previous `.gitignore` block that hid deployment files
> has been removed. `render.yaml`, `frontend/vercel.json`, `.github/`, and
> `backend/render_start.sh` now need to be committed and pushed before Render,
> Vercel, and GitHub Actions can use them.

This guide deploys the **backend on Render** and the **frontend on Vercel**, then enables a watchdog that pings the backend and restarts the Render service when it is unhealthy.

Files added for this deployment:

| File | Purpose |
|---|---|
| `render.yaml` | Render Blueprint for the backend and a free Key Value cache |
| `backend/render_start.sh` | Migrates, collects static files, and starts Gunicorn |
| `frontend/vercel.json` | SPA rewrites and security headers for Vercel |
| `scripts/render_watchdog.py` | Health check + Render restart bot |
| `.github/workflows/keep-backend-alive.yml` | Runs the watchdog every 10 minutes |

---

## 1. Push the deployment files

The repository previously ignored `.github/`; this has been changed so the watchdog workflow is tracked. Commit and push:

```bash
git add render.yaml backend/render_start.sh backend/requirements.txt \
  backend/django_backend/settings.py backend/django_backend/middleware.py \
  backend/django_backend/views.py backend/django_backend/views/documents.py \
  backend/django_backend/views/doc_api.py backend/app/main.py \
  frontend/vercel.json scripts/render_watchdog.py \
  .github/workflows/keep-backend-alive.yml .gitignore \
  DEPLOY_RENDER_VERCEL.md
git commit -m "Add Render/Vercel deployment and backend watchdog"
git push origin main
```

Do not commit `backend/.env`, `backend/data/`, `backend/uploads/`, or `frontend/dist/`.

---

## 2. Deploy the backend on Render

### 2.1 Create the Blueprint

1. Open the Render Dashboard.
2. Select **New > Blueprint**.
3. Connect the GitHub repository.
4. Render detects `render.yaml` and shows two resources:
   - `intradoc-backend` (web service)
   - `intradoc-cache` (Key Value)
5. Apply the Blueprint.

### 2.2 Fill the secrets

Render prompts for every `sync: false` variable:

| Variable | Value |
|---|---|
| `ALLOWED_HOSTS` | Optional. Leave blank to use `RENDER_EXTERNAL_HOSTNAME` automatically. Add a custom domain if you use one. |
| `CORS_ALLOWED_ORIGINS` | Your Vercel URL, e.g. `https://your-app.vercel.app,https://*.vercel.app` |
| `CSRF_TRUSTED_ORIGINS` | Add your backend and frontend origins, e.g. `https://YOUR-SERVICE.onrender.com,https://your-app.vercel.app`. |
| `FRONTEND_URL` | Your deployed Vercel URL, e.g. `https://your-app.vercel.app`. Used in invite/reset emails. |
| `INTRADOC_ENCRYPTION_KEY` | Recommended. Stable random value used to encrypt provider keys stored in the DB. Generate once and keep it. |
| `DATABASE_URL` | Recommended for durable data. Managed Postgres URL (Render/Neon/Supabase). Leave blank to use SQLite (ephemeral on free). |
| `ALLOW_FIRST_USER_BOOTSTRAP` | `True` only for the first deploy so the first signup becomes Admin; switch to `False` afterwards. |
| `GROQ_API_KEY` | Your Groq key (required if `LLM_PROVIDER=groq`) |
| `GEMINI_API_KEY` | Optional |
| `OPENAI_API_KEY` | Optional |
| `BREVO_API_KEY` | Brevo API key (free 300 emails/day). Required for invitations/reset emails on Render free. |
| `DEFAULT_FROM_EMAIL` | A sender verified in Brevo, e.g. `IntraDoc <no-reply@yourdomain.com>`. |
| `INTRADOC_REDIS_URL` | Auto-wired to Render Key Value. Replace with a Redis Stack URL for semantic cache. |

`SECRET_KEY` is generated automatically by Render.

**First admin:** deploy with `ALLOW_FIRST_USER_BOOTSTRAP=True`, open the frontend, and sign up the first account (it becomes Admin). Then set `ALLOW_FIRST_USER_BOOTSTRAP=False` and redeploy. Alternatively, use the Render Shell to create a user and `UserProfile(role='Admin')`.

### 2.2.1 Email provider: use Brevo on free Render

Render free web services block outbound SMTP ports `25`, `465`, and `587`, so **Gmail SMTP and other SMTP relays will time out** on the free plan. Use an HTTPS email API instead.

Recommended free option: **Brevo**
- 300 emails/day, no credit card required, permanent free plan.
- Works over HTTPS (port `443`), so Render's SMTP block does not apply.
- The app uses `django-anymail` and `anymail.backends.brevo.EmailBackend`.
- Free-plan emails include a small “Sent with Brevo” footer.

Setup:
1. Create a free Brevo account and verify a sender email or domain.
2. In Brevo, open **SMTP & API → API Keys** and create an API key with only the permissions it needs.
   - If Brevo’s **Block unknown IPs** security is enabled, Render requests will fail with `401`. Either disable it or add every CIDR range from Render’s **service → Connect → Outbound** tab. Free Render uses shared regional ranges that can change, so disabling it is simpler for a free deployment; use a scoped API key if you do.
3. Set these Render variables:
   ```env
   EMAIL_BACKEND=anymail.backends.brevo.EmailBackend
   BREVO_API_KEY=<your Brevo API key>
   DEFAULT_FROM_EMAIL=IntraDoc <no-reply@your-verified-sender>
   ```
4. Redeploy and test the password-reset flow.

Alternative: **Resend** (3,000/month, 100/day). Set `EMAIL_BACKEND=anymail.backends.resend.EmailBackend` and `RESEND_API_KEY`; you must verify a domain to send to arbitrary users. Remove `EMAIL_BACKEND` if you want the app to auto-select Brevo or Resend from whichever API key is present.

### 2.3 Wait for the first deploy

The build installs CPU-only PyTorch first, then `requirements.txt` (including `gunicorn`, `sentence-transformers`, `chromadb`, and the cross-encoder dependencies). The first build can take several minutes.

After the deploy:

```bash
curl https://YOUR-SERVICE.onrender.com/api/health/live
curl https://YOUR-SERVICE.onrender.com/api/health/ready
```

- `/api/health/live` should return `{"status": "ok"}`.
- `/api/health/ready` should return `200` with `redis`, `chromadb`, and `database` set to `true`.
- If `/api/health/ready` returns `503`, check the Render logs and the Redis/Chroma paths.

### 2.4 Important free-plan limitations

- **Sleep:** Free Render web services sleep after about 15 minutes without traffic. The watchdog below prevents this by pinging every 10 minutes.
- **SMTP blocked:** Free Render web services cannot open outbound connections to SMTP ports `25`, `465`, or `587` (since September 2025). Use Brevo/Resend HTTPS APIs as described above, or upgrade to a paid Render instance to use SMTP.
- **No persistent disk:** Chroma (`backend/data/chroma`) and uploads (`backend/uploads`) are lost on every deploy or restart. SQLite can be replaced by setting `DATABASE_URL` to managed Postgres, but vector data and uploaded files still need a paid Render persistent disk (or external object storage plus a managed vector database). Re-upload documents after a restart on the free plan.
- **Memory:** The free plan has 512 MB RAM. Loading SentenceTransformer, the cross-encoder, Chroma, and Django may exceed this. If Render shows `OOMKilled` or repeated 502s, upgrade to a paid plan.
- **Semantic cache:** Render's free Key Value instance is Redis-compatible but does **not** include RediSearch. The RBAC-aware semantic cache (RedisVL) initialization can fail as a result, which disables the cache/cost/metrics integration. The application still serves queries, but without caching. For the full semantic cache, point `INTRADOC_REDIS_URL` at a Redis Stack instance with the `search` module, or deploy Redis Stack as a private service (paid).
- **Model downloads:** On first query, `all-MiniLM-L6-v2` and the cross-encoder are downloaded. On an ephemeral filesystem this repeats after every restart, increasing cold-start time.
- **Single worker:** `backend/render_start.sh` runs one Gunicorn worker with four threads because SQLite and Chroma `PersistentClient` are not safe for multiple writer processes. Do not raise `GUNICORN_WORKERS` without migrating those stores.

### 2.5 Optional paid persistent disk

On a paid plan, attach a persistent disk to `intradoc-backend`:

```yaml
disk:
  name: intradoc-data
  mountPath: /opt/render/project/src/backend/data
  sizeGB: 5
```

Then add:

```env
INTRADOC_UPLOADS_DIR=/opt/render/project/src/backend/data/uploads
```

The application reads `INTRADOC_UPLOADS_DIR`, so SQLite, Chroma, and uploads share the same persistent disk. A disk cannot be attached to a free service, and a service with a disk cannot be horizontally scaled.

---

## 3. Deploy the frontend on Vercel

### 3.1 Import the project

1. Open Vercel and select **Add New > Project**.
2. Import the same GitHub repository.
3. Set **Root Directory** to `frontend`.
4. Framework preset: **Vite**.
5. Build command: `npm run build`.
6. Output directory: `dist`.

### 3.2 Set the API URL

Add an environment variable in Vercel:

```env
VITE_API_BASE=https://YOUR-SERVICE.onrender.com/api
```

`VITE_API_BASE` is baked into the frontend at build time. If you change the backend URL, redeploy the frontend.

### 3.3 Deploy and update CORS

After Vercel gives you a production URL, go back to Render and set:

```env
CORS_ALLOWED_ORIGINS=https://your-app.vercel.app,https://*.vercel.app
```

Redeploy the backend if Render does not restart automatically after the environment change. The wildcard supports Vercel preview deployments; remove it if you want to allow only the production domain.

### 3.4 SPA routing

`frontend/vercel.json` rewrites all paths to `index.html`, so deep links such as `/query/:sessionId` work on refresh.

---

## 4. The watchdog bot

The watchdog runs on a GitHub Actions schedule every 10 minutes. It:

1. Calls the backend health endpoint with retries and a 120-second timeout (cold starts can take a while).
2. If the backend is healthy, exits successfully.
3. If the backend is unhealthy, calls the Render API to restart the service.
4. Waits and checks for recovery.
5. Optionally sends a Slack/Discord-style webhook notification.

### 4.1 Create a Render API key

1. Render Dashboard > **Account Settings** > **API Keys**.
2. Create a key and copy it.

### 4.2 Find the Render service ID

1. Open the `intradoc-backend` service.
2. The service ID looks like `srv-xxxxxxxxxxxx` and appears in the URL and service settings.

### 4.3 Add GitHub Actions secrets

In GitHub: **Settings > Secrets and variables > Actions > New repository secret**.

| Secret | Value |
|---|---|
| `BACKEND_HEALTH_URL` | `https://YOUR-SERVICE.onrender.com/api/health/live` |
| `RENDER_API_KEY` | The Render API key |
| `RENDER_SERVICE_ID` | `srv-xxxxxxxxxxxx` |
| `NOTIFY_WEBHOOK_URL` | Optional Slack/Discord webhook |

### 4.4 Test the bot manually

1. GitHub > **Actions** > **Keep Backend Alive** > **Run workflow**.
2. Confirm the job succeeds.
3. To test the restart path, temporarily set `BACKEND_HEALTH_URL` to an invalid URL, run the workflow, and confirm it requests a restart. Restore the correct URL afterward.

### 4.5 Important scheduling caveats

- GitHub Actions scheduled workflows have a minimum interval of 5 minutes and can be delayed under load. A 10-minute interval is chosen to stay below Render's ~15-minute sleep threshold.
- Scheduled workflows only run on the default branch.
- GitHub disables scheduled workflows after 60 days of repository inactivity. Push a commit or manually run the workflow periodically.
- GitHub Actions is not a real-time monitor. For stricter uptime monitoring, also configure UptimeRobot, cron-job.org, or Better Stack to ping `/api/health/live` every 5 minutes.
- Keeping a free service awake 24/7 consumes the monthly free instance hours. One always-on free service fits within the monthly allowance, but leave room for other free services.

### 4.6 Local test of the watchdog

```bash
export BACKEND_HEALTH_URL="https://YOUR-SERVICE.onrender.com/api/health/live"
export RENDER_API_KEY="..."
export RENDER_SERVICE_ID="srv-..."
python3 scripts/render_watchdog.py
```

---

## 5. Post-deployment verification

- [ ] `https://YOUR-SERVICE.onrender.com/api/health/live` returns 200.
- [ ] `https://YOUR-SERVICE.onrender.com/api/health/ready` returns 200 or a known degraded status.
- [ ] Vercel frontend loads over HTTPS.
- [ ] `VITE_API_BASE` is set in Vercel and points at the Render `/api` URL.
- [ ] First admin account exists and `ALLOW_FIRST_USER_BOOTSTRAP` is `False`.
- [ ] Login and logout work.
- [ ] Password reset email / admin invitation email is delivered.
- [ ] Document upload works for `.pdf`, `.docx`, `.txt`, `.md`; `.exe` and empty files are rejected.
- [ ] A query returns an answer with citations.
- [ ] Streaming works through the browser and Render.
- [ ] The Vercel origin appears in `CORS_ALLOWED_ORIGINS`; PATCH preflight succeeds.
- [ ] RBAC department isolation works.
- [ ] If `DATABASE_URL` is set, data survives a redeploy; otherwise accept SQLite loss.
- [ ] The watchdog workflow runs successfully.
- [ ] Render logs show no OOM or repeated 502 errors.
- [ ] If using the free plan, accept that Chroma/uploads are lost on restart; if not, attach a persistent disk.

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| 502 after idle | Free service asleep | The watchdog should wake it; confirm `BACKEND_HEALTH_URL` is correct |
| `DisallowedHost` | `ALLOWED_HOSTS` missing the Render/Vercel host | Leave `ALLOWED_HOSTS` blank to use `RENDER_EXTERNAL_HOSTNAME`, or add the domain |
| CORS error | Vercel URL not in `CORS_ALLOWED_ORIGINS` | Add the exact production URL and redeploy backend |
| `FT._LIST` errors / no semantic cache | Render Key Value lacks RediSearch | Use Redis Stack or accept semantic-cache disablement |
| `database is locked` | Multiple backend processes | Keep `GUNICORN_WORKERS=1` |
| Chroma errors | Multiple processes or missing path | Keep one worker; verify `backend/data/chroma` |
| Uploads lost after deploy | Free plan ephemeral filesystem | Use a paid persistent disk or external object storage |
| OOMKilled | 512 MB free plan is too small | Upgrade the Render plan |
| Vercel 404 on refresh | SPA rewrite missing | Confirm `frontend/vercel.json` is deployed |
| Frontend calls localhost | `VITE_API_BASE` missing at build time | Set it in Vercel and redeploy |
| Watchdog cannot restart | Missing/incorrect Render API key or service ID | Check GitHub secrets and Render API key scope |

---

## 7. Security notes

- `SECRET_KEY` is generated by Render; the app now refuses to start with `DEBUG=False` if the insecure repository fallback is still in use.
- `INTRADOC_ENCRYPTION_KEY` should be set and kept stable; provider API keys stored through the admin UI are encrypted at rest.
- `DEBUG=False` is set in `render.yaml`.
- `ALLOWED_HOSTS` is restricted in `settings.py`; add custom domains explicitly.
- CORS is environment-driven and supports `*` wildcards for Vercel previews; `PATCH` is allowed for admin user updates.
- Login, signup, forgot-password, and reset-password endpoints are rate limited (`AUTH_THROTTLE_RATE`, default `10/min` per IP).
- Passwords are validated with Django's validators; password-reset OTPs expire after 15 minutes and unknown emails are not enumerated.
- Uploads are restricted to `.pdf`, `.docx`, `.txt`, `.md` with a 25 MB default limit (`INTRADOC_MAX_UPLOAD_MB`).
- The API uses JWT in the `Authorization` header, not cookies. The custom middleware exempts `/api/` from CSRF checks; review this if you add cookie-based sessions.
- JWTs are stored in browser `localStorage`, so XSS is the main residual risk; the Vercel config now ships CSP and security headers.
- Store the Render API key only in GitHub Actions secrets. It can restart services, so treat it as sensitive.
- Rotate LLM provider keys and the Render API key periodically.
- Do not commit `.env` files or the `backend/data`/`backend/uploads` directories.
