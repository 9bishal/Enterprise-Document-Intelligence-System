# IntraDoc AI — Document Intelligence Platform

IntraDoc AI is a full-stack document intelligence platform built around **RAG (Retrieval-Augmented Generation)**. It lets teams upload internal documents, search them semantically, and ask natural-language questions with grounded citations.

**Stack:** Django REST Framework · React 19 + Vite · LangGraph RAG · Chroma · Redis Stack · PostgreSQL (Neon) · Groq / Gemini / OpenAI

## Live Deployment

| Service | Link |
|---|---|
| Frontend | https://intradoc-frontend.vercel.app |
| Backend API | https://intradoc-backend.onrender.com/api |
| Health check | https://intradoc-backend.onrender.com/api/health/live |
| Repository | https://github.com/9bishal/Enterprise-Document-Intelligence-System |

> The backend runs on Render's free tier and may take 30–60 seconds to wake after inactivity.


## Overview

IntraDoc AI is designed to help organizations:
- Upload and index documents with semantic understanding
- Query documents using natural language
- Get AI-powered answers with source attribution
- Manage chat sessions and conversation history
- Control access through role-based permissions
- Filter results by department

## Project Structure

```
document_intelligent_system/
├── backend/                    # Django REST API + RAG Pipeline
│   ├── app/                   # Core RAG logic & helpers
│   │   ├── rag_graph.py       # RAG execution pipeline with step tracking
│   │   ├── llm_helper.py      # LLM API interactions (with SSL handling)
│   │   ├── vector_store.py    # Vector database (Chroma) operations
│   │   ├── database.py        # Database connection & setup
│   │   └── main.py            # Main application entry
│   ├── django_backend/        # Django configuration & models
│   │   ├── models.py          # Database models (Document, User, ChatSession, etc.)
│   │   ├── views/             # API endpoints
│   │   │   ├── auth.py        # Authentication endpoints
│   │   │   ├── doc_api.py     # Document CRUD operations
│   │   │   ├── doc_indexing.py # Document indexing & classification
│   │   │   ├── rag.py         # RAG query endpoints
│   │   │   ├── admin.py       # Admin operations
│   │   │   └── admin_*.py     # Specialized admin endpoints
│   │   ├── serializers.py     # DRF serializers
│   │   ├── permissions.py     # Custom permission classes
│   │   ├── middleware.py      # Custom middleware
│   │   ├── settings.py        # Django settings
│   │   ├── urls.py            # URL routing
│   │   └── migrations/        # Database migrations
│   ├── uploads/               # Temporary file uploads
│   ├── data/                  # Vector database & SQLite storage
│   ├── manage.py              # Django management script
│   ├── run.py                 # Application entry point
│   ├── requirements.txt       # Python dependencies (pinned)
│   └── .env                   # Environment variables (not in repo)
│
├── frontend/                   # React 19 + Vite application
│   ├── src/
│   │   ├── pages/            # Page components
│   │   │   ├── QueryPage.jsx      # Chat interface with RAG pipeline
│   │   │   ├── DocumentsPage.jsx  # Document management
│   │   │   ├── SettingsPage.jsx   # Settings & configuration
│   │   │   └── ...
│   │   ├── components/       # Reusable components
│   │   │   ├── ChatWindow.jsx     # Chat UI
│   │   │   ├── Visualizer.jsx     # RAG pipeline visualization
│   │   │   ├── admin/             # Admin components
│   │   │   └── ...
│   │   ├── utils/            # Utility functions
│   │   ├── App.jsx           # Main app component
│   │   └── main.jsx          # Entry point
│   ├── public/               # Static assets
│   ├── index.html            # HTML template
│   ├── package.json          # Node dependencies
│   ├── vite.config.js        # Vite configuration
│   └── README.md             # Frontend README
│
├── loadtests/                  # Locust load tests (65-70 concurrent users)
│   ├── locustfile.py         # Load test definition (user behavior, task weights)
│   ├── create_test_users.py  # Test user + JWT minting script
│   ├── README.md             # Results, percentile guide, how to run
│   └── results_*.csv         # Raw results of past runs
│
├── scripts/
│   └── render_watchdog.py    # Health monitor + auto-restart via Render API
│
├── .github/workflows/
│   ├── ci.yml                # Backend compile/check + frontend build
│   └── keep-backend-alive.yml # Cron: pings health every 10 min (anti-sleep)
│
├── docker-compose.yml         # Local stack: Redis Stack + backend + frontend
├── render.yaml                # Render service blueprint
└── start_redis.sh             # Local Redis Stack launcher (RediSearch module)
```

## Features

### Core Features
- ** Document Management**: Upload (single or batch up to 1000 files), index, preview, and organize documents by department
- ** Semantic Search**: Hybrid RAG (dense vectors + BM25 + RRF fusion + cross-encoder rerank) with true cosine similarity scores
- ** Chat Interface**: Real-time token streaming (SSE) with paced visible stream-out, message history, and deep-linkable threads (`/query/:sessionId`)
- ** Fast Single-Call Pipeline**: 1 LLM call per query (no grading loops); semantic + prompt + embedding caches (Redis + RediSearch)
- ** Deterministic Guards**: Greeting short-circuit, weak-grounding refusal (no LLM, no citations), cited-only source display, weak-grounding amber flag
- ** RAG Pipeline Visualization**: Live stage tracing (retrieve → grade → generate) with real tokens, billed cost, latency, and cache status per answer
- ** Answer Export**: Copy / download (.txt / .md) question + answer, native Share support
- ** Document Versioning**: Same-name re-upload supersedes v1 (chunks deleted, caches invalidated); byte-identical uploads skipped as duplicates; near-duplicate (≥85%) content supersedes by similarity
- ** Department Filtering**: Query documents from specific departments
- ** Role-Based Access Control**: Admin, Editor, Viewer roles with granular permissions

### Chat Session Management (CRUD)
- **Create** new chat threads
- **Read** chat history with full conversation context
- **Delete** chat sessions with confirmation

### Backend Features
- **REST API** with Django REST Framework
- **JWT Authentication** for secure access
- **Vector Database** (Chroma, department-scoped collections) for semantic search
- **LLM Integration** (Groq / Gemini / OpenAI, admin-configured) with real provider-reported token usage and cost
- **Streaming SSE endpoint** (`POST /api/chat/query/stream`: token / citations / done events)
- **Department-based Classification** + LLM risk screening for documents
- **Parallel ingestion** (2-worker pool, `INTRADOC_INDEX_WORKERS`) with batch upload endpoint
- **SSL/TLS Support** for secure LLM API calls
- **Pagination & Filtering** for document queries

### Admin Features
- Document deletion with vector store cleanup, in-app preview
- User management (invite, role/department update, delete with confirmation + full cleanup)
- LLM configuration management
- System metrics and analytics (real tokens, cost, cache hits, latency, errors)

## Tech Stack

Everything below is what the project actually uses (from `backend/requirements.txt`, `frontend/package.json`, and the infra files).

### Backend — Web & API
| Technology | Version | Purpose |
|---|---|---|
| Django | 6.0.7 | Web framework, ORM, admin |
| Django REST Framework | 3.17.1 | REST API, serializers, permissions, throttling |
| djangorestframework-simplejwt | 5.5.1 | JWT auth (access/refresh, token blacklist) |
| django-cors-headers | 4.9.0 | CORS for the Vite frontend |
| django-anymail | 15.2 | Transactional email (invites, password reset) |
| Gunicorn | 26.2.0 | Production WSGI server (Render) |
| Whitenoise | 6.12.0 | Static file serving |
| dj-database-url + psycopg (3) | 3.1.2 / 3.3.8 | Managed Postgres (Neon) connection |
| SQLite | — | Local development database (zero-config) |
| FastAPI + Uvicorn | 0.136.3 / 0.51.0 | Standalone RAG API entry (`app/main.py`) |

### RAG / AI / Retrieval
| Technology | Version | Purpose |
|---|---|---|
| LangGraph | 1.2.9 | RAG pipeline orchestration (retrieve → generate) |
| langchain-text-splitters | 1.1.3 | Document chunking |
| Chroma | 1.5.9 | Vector database (department-scoped collections) |
| sentence-transformers | 3.3.1 | Embeddings: `all-MiniLM-L6-v2` |
| transformers (Hugging Face) | 4.46.3 | Reranker: `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| rank-bm25 | 0.2.2 | Lexical (BM25) retrieval, fused with dense via RRF |
| redisvl | 0.23.0 | Redis semantic cache (`SemanticCache`) + embedding cache |
| groq SDK | 0.37.1 | Primary LLM provider (admin-configured) |
| google-generativeai | 0.8.6 | Gemini provider |
| openai SDK | 2.46.0 | OpenAI provider |

### Document Processing
| Technology | Version | Purpose |
|---|---|---|
| pypdf | 6.14.2 | PDF text extraction |
| pdfplumber | 0.11.10 | Complex/table PDF extraction |
| python-docx + docx2txt | 1.2.0 / 0.9 | Word document extraction |
| python-multipart | 0.0.32 | File upload parsing |

### Caching & Infrastructure
| Technology | Version | Purpose |
|---|---|---|
| Redis Stack (redis-stack-server) | 7.4 | Cache + RediSearch module (required for semantic cache) |
| redis-py | 7.4.1 | Redis client |
| prometheus-client | 0.25.0 | `/metrics` endpoint, app metrics |
| Pydantic | 2.13.4 | Request/response validation |
| python-dotenv | 1.0.1 | Env var loading |
| requests | 2.34.2 | Outbound HTTP |
| cryptography | 49.0.0 | Provider API key encryption at rest |

### Frontend
| Technology | Version | Purpose |
|---|---|---|
| React | 19.2 | UI framework |
| react-router-dom | 7.x | Routing (deep-linkable chat threads) |
| Vite | 8.x | Build tool & dev server |
| ESLint (+ react-hooks, react-refresh plugins) | 10.x | Linting |
| Fetch API | — | HTTP client (native) |
| CSS | — | Styling |

### DevOps & CI/CD
| Tool | Purpose |
|---|---|
| Docker Compose | Local stack: Redis Stack + backend + frontend |
| Render | Backend hosting (blueprint: `render.yaml`) |
| Vercel | Frontend hosting |
| Neon | Managed Postgres in production |
| GitHub Actions — `ci.yml` | Backend compile check + Django system check + frontend build |
| GitHub Actions — `keep-backend-alive.yml` | Cron every 10 min: health ping + auto-restart watchdog (`scripts/render_watchdog.py`) |
| GitHub Releases | Versioned releases (latest: v1.0.0) |

### Testing & Load Testing
| Tool | Purpose |
|---|---|
| Locust | Load testing — **65 concurrent users: 6,339 requests, 0 failures, p95 220ms** (see [`loadtests/`](./loadtests/README.md)) |

## Prerequisites

- Python 3.12+ (backend)
- Node.js 20+ (frontend)
- npm (frontend)
- Redis Stack with the RediSearch module (`./start_redis.sh` handles this locally)
- Git (for version control)

## Installation & Setup

### Backend Setup

1. **Navigate to backend directory**:
   ```bash
   cd backend
   ```

2. **Create and activate virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables** (copy the template and fill in your keys):
    ```bash
    cp .env.example .env
    ```
    Key variables: `SECRET_KEY`, `LLM_PROVIDER=groq`, `GROQ_API_KEY` (or `GEMINI_API_KEY` / `OPENAI_API_KEY`), and optionally `DATABASE_URL` for managed Postgres. Full reference with comments is in [`.env.example`](./backend/.env.example).

5. **Run migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Start the backend server**:
   ```bash
   python run.py
   ```
   Server will be available at `http://localhost:8000`

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Create environment configuration** (create `.env.local`):
   ```env
   VITE_API_BASE=http://localhost:8000/api
   ```

4. **Start development server**:
   ```bash
   npm run dev
   ```
   Application will be available at `http://localhost:5173`

## API Endpoints

### Authentication
- `POST /api/auth/signup` - User signup (requires admin invite code)
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - Logout (blacklists refresh token)
- `GET /api/auth/me` - Current user profile
- `POST /api/auth/forgot-password` - Request password reset email
- `POST /api/auth/reset-password` - Reset password with emailed code
- `POST /api/auth/token/refresh` - Refresh JWT access token

### Chat Sessions (CRUD)
- `GET /api/chat/sessions` - List all chat sessions
- `POST /api/chat/sessions` - Create new chat session
- `DELETE /api/chat/sessions/{id}` - Delete session
- `GET /api/chat/sessions/{id}/messages` - Get session messages

### Chat Query
- `POST /api/chat/query` - Send question and get RAG response (single LLM call)
- `POST /api/chat/query/stream` - Same, streamed as SSE (`token` / `citations` / `done` with real tokens + cost)

### Documents
- `GET /api/documents` - List documents
- `POST /api/documents/upload` - Upload document (auto-supersedes same-name v1, skips byte-duplicates)
- `POST /api/documents/upload/batch` - Upload up to 1000 files at once
- `GET /api/documents/{id}/file` - Preview/download original file (inline, department-scoped)
- `DELETE /api/documents/{id}` - Delete document (admin only)

### Admin
- `GET /api/admin/metrics` - System metrics (real tokens, cost, cache hits, latency, errors, indexed docs)
- `POST /api/admin/invite` - Create user invite (emailed signup link)
- `GET /api/admin/users` - List users
- `PATCH /api/admin/users/{id}` - Update user role/department
- `DELETE /api/admin/users/{id}` - Delete user with confirmation (self-delete and last-admin protected)
- `GET /api/admin/knowledge-graph` - Knowledge graph data
- `DELETE /api/admin/documents/{id}/delete` - Admin document deletion
- `GET /api/admin/llm-config` / `POST /api/admin/llm-config/update` - View/update LLM provider config

### System
- `GET /api/health/live` - Liveness probe (used by the keep-alive watchdog)
- `GET /api/health/ready` - Readiness probe (DB + cache)
- `GET /api/cache/stats` - Cache statistics
- `GET /api/departments` - Department list
- `GET /api/llm-config` - Public LLM config
- `GET /metrics` - Prometheus metrics

## Authentication

The system uses **JWT (JSON Web Token)** authentication:

1. User logs in with credentials
2. Server returns `access_token` and `refresh_token`
3. Token is stored in localStorage as `intradoc_token`
4. All API requests include: `Authorization: Bearer {token}`
5. Token can be refreshed before expiration

## Usage Examples

### Upload a Document
```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer {token}" \
  -F "file=@document.pdf" \
  -F "department=HR"
```

### Send a Chat Query
```bash
curl -X POST http://localhost:8000/api/chat/query \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-uuid",
    "question": "What are the HR policies?",
    "department": "HR"
  }'
```

### Create a Chat Session
```bash
curl -X POST http://localhost:8000/api/chat/sessions \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"name": "Project Discussion"}'
```

## RAG Pipeline Execution

The system shows a visual representation of the RAG pipeline:

1. **Document Retrieval** - Hybrid search (dense + BM25 + RRF) finds top-k chunks with true cosine similarity
2. **Deterministic Guards** - Greetings answered instantly; weak grounding (<20% top similarity) refused locally with zero LLM cost
3. **LLM Generation** - Single streamed call answers in ≤5 short numbered points with inline `[1]`, `[2]` citations
4. **Source Attribution** - Only cited sources displayed; borderline grounding flagged amber
5. **Caching** - Repeat/paraphrased queries served from Redis semantic cache (~ms, zero LLM)

Each step is traced live in the Execution Pipeline panel with real tokens, cost, latency, and cache status.

## Tuning Flags (env vars)

- `INTRADOC_FAST_PATH=1` - Single-call pipeline (0 = legacy grade/regenerate pipeline)
- `INTRADOC_PLAIN_TEXT=1` - Plain-text answers, no markdown artefacts
- `INTRADOC_SHORT_ANSWERS=1` - Max 5 numbered points per answer
- `INTRADOC_MAX_TOKENS=512` - Output token cap (faster + cheaper)
- `INTRADOC_MIN_SIMILARITY=20` - Weak-grounding refusal threshold (cosine %)
- `INTRADOC_INDEX_WORKERS=2` - Parallel document indexing threads
- `INTRADOC_DUP_SIM_THRESHOLD=0.85` - Near-duplicate supersede threshold
- `INTRADOC_REDIS_URL` - Redis endpoint (must load the RediSearch module; `./start_redis.sh` handles it)

## Security Features

- **JWT Authentication**: Secure token-based auth
- **Role-Based Access Control (RBAC)**: Admin/Editor/Viewer roles
- **CORS Protection**: Cross-Origin Resource Sharing configured
- **SSL/TLS Support**: Secure LLM API connections
- **Input Validation**: All inputs validated server-side
- **SQL Injection Protection**: ORM-based queries prevent SQL injection
- **Permission Classes**: Custom DRF permission classes

## Testing

There are no automated unit tests yet (planned: pytest for the backend, Vitest for the frontend). Testing today is **load testing with Locust**:

```bash
# One-time: install Locust + create test users / mint JWTs (see loadtests/README.md)
python3 -m venv loadtests/.venv && loadtests/.venv/bin/pip install locust

# Run: 65 concurrent users, ramp 2/s, 5 minutes
loadtests/.venv/bin/locust -f loadtests/locustfile.py \
  --headless -u 65 -r 2 --run-time 5m --host http://localhost:8000 --csv loadtests/results
```

Latest verified result (65 users, 5 min): **6,339 requests, 0 failures, p50 13ms, p95 220ms**. Full methodology, percentile breakdown, and caveats: [loadtests/README.md](./loadtests/README.md).

CI (`.github/workflows/ci.yml`) additionally runs a backend compile check + Django system check and a frontend production build on every push/PR.

## Deployment

Production is deployed on **Render** (backend) and **Vercel** (frontend):

- Frontend: https://intradoc-frontend.vercel.app
- Backend API: https://intradoc-backend.onrender.com/api
- Step-by-step guide: [DEPLOY_RENDER_VERCEL.md](./DEPLOY_RENDER_VERCEL.md)

The backend uses Neon Postgres for durable user/document metadata and Redis Stack for caching. Render's free tier does not provide persistent disk, so uploaded files and Chroma vectors are ephemeral unless a persistent disk or external object/vector storage is added.

**Keep-alive:** GitHub Actions pings the health endpoint every 10 minutes (`keep-backend-alive.yml` → `scripts/render_watchdog.py`) and auto-restarts the service via the Render API if the health check fails.

**Releases:** see [Releases](https://github.com/9bishal/Enterprise-Document-Intelligence-System/releases) (latest: v1.0.0).

## Troubleshooting

### Backend Issues
- **Import errors**: Ensure virtual environment is activated and requirements.txt is installed
- **Database errors**: Run `python manage.py migrate`
- **SSL errors**: Check `.env` file and LLM API key configuration

### Frontend Issues
- **CORS errors**: Verify `VITE_API_BASE` matches backend URL
- **Token errors**: Clear localStorage and re-login
- **API 404**: Ensure backend is running on correct port

## Documentation

- [Backend README](./backend/README.md) - Backend-specific documentation
- [Frontend README](./frontend/README.md) - Frontend-specific documentation
- [Documentation](./DOCUMENTATION.md) - Architecture, API, and implementation notes
- [Deployment Guide](./DEPLOY_RENDER_VERCEL.md) - Render + Vercel deployment
- [Project Structure](./PROJECT_STRUCTURE.md) - Directory layout

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Team

- **Backend Engineer**: RAG Pipeline & API Development
- **Frontend Engineer**: UI/UX & Chat Interface
- **DevOps**: Deployment & Infrastructure

## Support

For issues, questions, or suggestions:
- Open an Issue on GitHub
- Check existing documentation
- Review the troubleshooting section

## Acknowledgments

- Django REST Framework for excellent REST API framework
- Chroma for vector database capabilities
- React & Vite for modern web development
- Groq for LLM inference

---

**Last Updated**: November 2026
**Release**: [v1.0.0](https://github.com/9bishal/Enterprise-Document-Intelligence-System/releases/tag/v1.0.0)
