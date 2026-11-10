# Project Structure & Architecture

## Live Deployment

- Frontend: https://intradoc-frontend.vercel.app
- Backend API: https://intradoc-backend.onrender.com/api
- Health: https://intradoc-backend.onrender.com/api/health/live
- Repository: https://github.com/9bishal/Enterprise-Document-Intelligence-System-


## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Web Browser (User)                           │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/HTTPS
┌────────────────────────────▼────────────────────────────────────┐
│              Frontend (React + Vite)                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ - Chat Interface (QueryPage)                           │    │
│  │ - Document Management (DocumentsPage)                  │    │
│  │ - Settings & Configuration (SettingsPage)              │    │
│  │ - Admin Dashboard (AdminDashboard)                     │    │
│  │ - RAG Pipeline Visualizer                              │    │
│  └─────────────────────────────────────────────────────────┘    │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST API (JSON)
                             │ JWT Authentication
┌────────────────────────────▼────────────────────────────────────┐
│           Backend (Django REST Framework)                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ API Routes Layer                                         │   │
│  │ - Authentication endpoints (/api/auth)                   │   │
│  │ - Chat endpoints (/api/chat)                             │   │
│  │ - Document endpoints (/api/documents)                    │   │
│  │ - Admin endpoints (/api/admin)                           │   │
│  └──────────┬───────────────────────────────────────────────┘   │
│  ┌──────────▼───────────────────────────────────────────────┐   │
│  │ Business Logic Layer                                     │   │
│  │ - Permission & Authorization                            │   │
│  │ - User Management                                        │   │
│  │ - Chat Session Management                               │   │
│  │ - Document Processing                                   │   │
│  └──────────┬───────────────────────────────────────────────┘   │
│  ┌──────────▼───────────────────────────────────────────────┐   │
│  │  RAG Pipeline Layer (app/)                                │   │
│  │  - Hybrid retrieval (dense + BM25 + RRF + rerank)        │   │
│  │  - Deterministic guards (greeting / weak grounding)      │   │
│  │  - Single-call streamed LLM orchestration                │   │
│  │  - Real token usage + cost tracking                      │   │
│  └──────────┬───────────────────────────────────────────────┘   │
│  ┌──────────▼───────────────────────────────────────────────┐   │
│  │ Data Access Layer                                        │   │
│  │ - SQLAlchemy ORM                                         │   │
│  │ - Database Models                                        │   │
│  │ - Query Optimization                                     │   │
│  └──────────┬───────────────────────────────────────────────┘   │
└────────────────────────────┬───────────────────────────────────┘
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
    ┌───────┐         ┌──────────┐       ┌──────────┐
    │ SQLite│         │  Chroma  │       │   LLM    │
    │ (DB)  │         │(Vector)  │       │   API    │
    └───────┘         └──────────┘       └──────────┘
```

## Directory Structure (Detailed)

```
document_intelligent_system/
│
├── README.md                    # Main project documentation
├── CONTRIBUTING.md              # Contribution guidelines
├── PROJECT_STRUCTURE.md         # This file
├── LICENSE                      # MIT License
├── .gitignore                   # Git ignore rules
│
├── backend/                     # Django REST Backend
│   │
│   ├── app/                     # Core RAG Logic
│   │   ├── __init__.py
│   │   ├── main.py              # Application startup
│   │   ├── database.py          # Database initialization
│  │  ├── rag_graph.py         # ★ RAG Pipeline execution
│  │  │                        #   - Hybrid retrieval + rerank
│  │  │                        #   - Greeting / grounding guards
│  │  │                        #   - Single-call streamed generation
│  │  │                        #   - Classic + stream entry points
│  │  ├── llm_helper.py        # ★ LLM API Integration
│  │  │                        #   - Groq/Gemini/OpenAI calls + SSE stream
│  │  │                        #   - Real provider token usage capture
│  │  │                        #   - Plain-text enforcement
│  │  │                        #   - SSL certificate handling
│  │  │                        #   - Error handling
│  │  └── vector_store.py      # ★ Vector Database (Chroma)
│  │                            #   - True cosine similarity
│  │                            #   - Department collections
│  │                            #   - Document indexing / deletion
│   │
│   ├── django_backend/          # Django Configuration
│   │   ├── __init__.py
│   │   ├── settings.py          # Django settings, middleware
│   │   ├── urls.py              # URL routing configuration
│   │   ├── wsgi.py              # WSGI entry point
│   │   ├── asgi.py              # ASGI entry point (async)
│   │   ├── middleware.py        # Custom middleware
│   │   │                        #   - Auth middleware
│   │   │                        #   - Request logging
│   │   │                        #   - CORS handling
│   │   ├── models.py            # ★ Database Models
│   │   │                        #   - User
│   │   │                        #   - Document
│   │   │                        #   - ChatSession
│   │   │                        #   - ChatMessage
│   │   │                        #   - LLMConfig
│   │   ├── serializers.py       # DRF Serializers
│   │   │                        #   - UserSerializer
│   │   │                        #   - DocumentSerializer
│   │   │                        #   - ChatSessionSerializer
│   │   │                        #   - ChatMessageSerializer
│   │   ├── permissions.py       # ★ Permission Classes
│   │   │                        #   - IsViewerOrAbove
│   │   │                        #   - IsEditorOrAbove
│   │   │                        #   - IsAdmin
│   │   │                        #   - IsOwnerOrAdmin
│   │   │
│   │   ├── views/               # ★ API Endpoints
│   │   │   ├── __init__.py      # Exports for easy importing
│   │   │   ├── auth.py          # Authentication
│   │   │   │                    #   - login
│   │   │   │                    #   - register
│   │   │   │                    #   - refresh token
│   │   │   ├── doc_api.py       # Document CRUD
│   │   │   │                    #   - list documents
│   │   │   │                    #   - upload document
│   │   │   │                    #   - delete document
│   │   │   ├── doc_indexing.py  # Document Indexing
│   │   │   │                    #   - index documents
│   │   │   │                    #   - classify by department
│   │   │   ├── documents.py     # Additional document ops
│  │  │   ├── rag.py           # ★ Chat & RAG Endpoints
│  │  │   │                    #   - GET /chat/sessions
│  │  │   │                    #   - POST /chat/sessions
│  │  │   │                    #   - DELETE /chat/sessions/{id}
│  │  │   │                    #   - GET messages
│  │  │   │                    #   - POST /chat/query (single call)
│  │  │   │                    #   - POST /chat/query/stream (SSE)
│   │   │   ├── rag_query.py     # Query-specific logic
│   │   │   ├── admin.py         # Admin Operations
│   │   │   │                    #   - delete documents
│   │   │   │                    #   - system management
│   │   │   ├── admin_graph.py   # Admin Analytics
│   │   │   ├── admin_llm.py     # Admin LLM Config
│   │   │   ├── admin_metrics.py # System Metrics
│   │   │   └── admin_users.py   # User Management
│   │   │
│   │   ├── migrations/          # Database Migrations
│   │   │   ├── __init__.py
│   │   │   ├── 0001_initial.py
│   │   │   ├── 0002_document_classification_...
│   │   │   ├── 0003_userinvitation_document_...
│   │   │   ├── 0004_passwordresetotp.py
│   │   │   └── 0005_llmconfig.py
│   │   │
│   │   └── __pycache__/         # Python bytecode cache
│   │
│   ├── uploads/                 # Temporary file uploads
│   │   ├── document1.pdf
│   │   ├── document2.docx
│   │   └── ...
│   │
│   ├── data/                    # Persistent Data Storage
│   │   ├── app.db               # SQLite database
│   │   └── chroma/              # Chroma Vector Database
│   │       ├── chroma.sqlite3
│   │       ├── uuid1/           # Document embeddings
│   │       └── uuid2/           # Document embeddings
│   │
│   ├── manage.py                # Django CLI
│   ├── run.py                   #  Application Entry Point
│   ├── requirements.txt         # Python Dependencies
│   ├── .env                     # Environment Variables (git-ignored)
│   ├── .env.example             # Example environment template
│   ├── README.md                # Backend Documentation
│   └── venv/                    # Virtual Environment
│
├── frontend/                    # React + Vite Application
│   │
│   ├── src/                     # Source Code
│   │   ├── pages/               # Page Components
│   │   │   ├── QueryPage.jsx    #  Main Chat Interface
│   │   │   │                    #   - Chat window
│   │   │   │                    #   - Chat history sidebar
│   │   │   │                    #   - Department filter
│   │   │   │                    #   - Session CRUD (3-dot menu)
│   │   │   │                    #   - RAG pipeline visualizer
│   │   │   ├── DocumentsPage.jsx # Document Management
│   │   │   ├── SettingsPage.jsx  # Settings & Configuration
│   │   │   ├── AdminAnalytics.jsx # Admin Dashboard
│   │   │   ├── AdminMetrics.jsx   # Metrics & Analytics
│   │   │   └── ...
│   │   │
│   │   ├── components/          # Reusable Components
│   │   │   ├── ChatWindow.jsx   #  Chat UI Component
│   │   │   │                    #   - Message display
│   │   │   │                    #   - Input area
│   │   │   │                    #   - Session selector
│   │   │   ├── Visualizer.jsx   #  RAG Pipeline Visualizer
│   │   │   │                    #   - Step visualization
│   │   │   │                    #   - Source highlighting
│   │   │   │                    #   - Step tracking
│   │   │   ├── LoginScreen.jsx  # Authentication
│   │   │   ├── Navbar.jsx       # Navigation
│   │   │   ├── Sidebar.jsx      # Sidebar Navigation
│   │   │   ├── admin/           # Admin Components
│   │   │   │   ├── AdminAnalytics.jsx
│   │   │   │   ├── AdminUsers.jsx
│   │   │   │   └── AdminSettings.jsx
│   │   │   ├── Icons.jsx        # Icon Components
│   │   │   ├── KnowledgeGraphVisualizer.jsx
│   │   │   └── ...
│   │   │
│   │   ├── utils/               # Utility Functions
│   │   │   ├── api.js           # API client functions
│   │   │   ├── auth.js          # Authentication helpers
│   │   │   ├── formatters.js    # Date/time formatting
│   │   │   └── ...
│   │   │
│   │   ├── assets/              # Static Assets
│   │   │   ├── hero.png
│   │   │   ├── react.svg
│   │   │   └── ...
│   │   │
│   │   ├── App.jsx              # Main App Component
│   │   ├── App.css              # App Styles
│   │   ├── index.css            # Global Styles
│   │   └── main.jsx             # Entry Point
│   │
│   ├── public/                  # Public Static Files
│   │   ├── favicon.svg
│   │   ├── icons.svg
│   │   └── ...
│   │
│   ├── index.html               # HTML Template
│   ├── package.json             # Node Dependencies
│   ├── package-lock.json        # Dependency Lock File
│   ├── vite.config.js           # Vite Configuration
│   ├── eslint.config.js         # ESLint Configuration
│   ├── .gitignore               # Git Ignore Rules
│   ├── README.md                # Frontend Documentation
│   └── node_modules/            # Dependencies
│
└── .venv/                       # Root Python Virtual Environment

 ★ = Core/Important files
```

## Data Flow

### Chat Query Flow (streamed, single LLM call)

```
User Input (QueryPage, thread URL /query/:sessionId)
    ↓
ChatWindow Component (paged visible stream-out)
    ↓
handleSendMessage() in QueryPage
    ↓
POST /api/chat/query/stream (SSE: token / citations / done)
    ↓
Django Backend (rag.py query_rag_stream view)
    ↓
Permission Check (IsViewerOrAbove) + department scoping
    ↓
run_rag_stream() [app/rag_graph.py]
    ├─ greeting guard → instant fixed reply (zero LLM)
    ├─ semantic cache lookup (Redis + RediSearch, RBAC-scoped)
    │  └─ hit → instant answer, zero LLM
    ├─ retrieval step
    │  └─ Hybrid search: dense + BM25 + RRF fusion
    ├─ rerank + token-budget context build
    ├─ weak-grounding guard (<20% top cosine → local refusal)
    ├─ llm_generation step (ONE streamed call, ≤5 points)
    │  └─ Real billed tokens captured from provider usage
    └─ persist message + tokens + cost + cache flag
    ↓
Frontend appends tokens live, stages light up progressively
    ↓
Visualizer renders steps + real cost/latency/cache panel
    ↓
User sees pointed answer + cited-only sources
```

### Document Upload Flow (single or batch up to 1000 files)

```
User selects file(s) (DocumentsPage, multi-select)
    ↓
POST /api/documents/upload[/batch] (REST API)
    ↓
Django Backend (doc_api.py)
    ↓
Permission Check (IsEditorOrAbove)
    ↓
Save file(s) to uploads/ + create DB rows
    ↓
Version + content checks per file (zero LLM)
    ├─ Same filename in dept → previous version superseded
    │  (status retired, chunks deleted, caches invalidated)
    ├─ Byte-identical content → skipped as duplicate
    └─ Near-duplicate (>=85% text) → old doc superseded
    ↓
2-worker pool runs doc_indexing.py per document
    ├─ Extract text + split into chunks
    ├─ Generate embeddings (serialized lock) + LLM classification (parallel)
    └─ Race guard: superseded docs stay retired
    ↓
Store in vector_store.py (department Chroma collection)
    ↓
Save document metadata to SQLite
    ↓
Frontend updates document list (status: ingesting → indexed)
```

### Session Management CRUD Flow

```
Create Session
    ├─ User clicks " New Chat"
    ├─ handleCreateSession() prompts for name
    ├─ POST /api/chat/sessions
    ├─ Backend creates ChatSession object
    └─ Frontend adds to sessions list

Read Sessions
    ├─ QueryPage useEffect fetches sessions
    ├─ GET /api/chat/sessions
    ├─ Backend queries ChatSession table
    └─ Frontend displays in sidebar

Update Session (Rename)
    ├─ User clicks 3-dot menu → " Rename"
    ├─ Inline edit form appears
    ├─ handleEditSessionSave()
    ├─ PUT /api/chat/sessions/{id}
    ├─ Backend updates ChatSession.name
    └─ Frontend updates UI

Delete Session
    ├─ User clicks 3-dot menu → " Delete"
    ├─ Confirmation dialog
    ├─ handleDeleteSession()
    ├─ DELETE /api/chat/sessions/{id}
    ├─ Backend deletes ChatSession + messages
    └─ Frontend removes from list
```

## Authentication & Authorization Flow

```
Login Page
    ↓
User enters credentials
    ↓
POST /api/auth/login
    ↓
Backend validates credentials
    ↓
Generate JWT tokens
    ├─ access_token (15 min expiry)
    └─ refresh_token (7 day expiry)
    ↓
Frontend stores token in localStorage
    ↓
All subsequent requests include header:
    Authorization: Bearer {access_token}
    ↓
Backend validates token
    ↓
Permission class checks role
    ├─ Viewer: Read-only access
    ├─ Editor: Create/edit access
    └─ Admin: Full access
    ↓
Request proceeds or returns 403 Forbidden
```

## Database Schema Overview

```
User Table
├─ id (PK)
├─ username (unique)
├─ email (unique)
├─ password_hash
├─ role (viewer/editor/admin)
├─ department
└─ created_at

Document Table
├─ id (PK)
├─ user_id (FK → User)
├─ title
├─ file_path
├─ department
├─ classification
├─ file_size
├─ upload_date
└─ metadata (JSON)

ChatSession Table
├─ id (PK)
├─ user_id (FK → User)
├─ name
├─ created_at
└─ updated_at

ChatMessage Table
├─ id (PK)
├─ session_id (FK → ChatSession)
├─ role (user/assistant)
├─ content
├─ steps (JSON) [for RAG tracking]
├─ sources (JSON) [cited documents]
├─ input_tokens / output_tokens (provider-reported, 0 = local reply)
├─ estimated_cost_usd (pricing x real tokens)
├─ latency_ms, cache_hit, model_used
└─ created_at

LLMConfig Table
├─ id (PK)
├─ user_id (FK → User)
├─ model_name
├─ api_key (encrypted)
├─ temperature
├─ max_tokens
└─ created_at
```

## API Structure

```
REST Endpoints:

/api/auth/
├─ POST   login          # Authenticate user
├─ POST   register       # Create account
└─ POST   refresh        # Refresh JWT token

/api/chat/
├─ GET    sessions       # List sessions
├─ POST   sessions       # Create session
├─ GET    sessions/{id}  # Get session
├─ PUT    sessions/{id}  # Update session
├─ DELETE sessions/{id}  # Delete session
├─ GET    sessions/{id}/messages
├─ POST   query          # Send chat query (single LLM call)
└─ POST   query/stream   # Streamed query (SSE token/citations/done)

/api/documents/
├─ GET    .              # List documents
├─ POST   upload         # Upload document (versioning + dedupe)
├─ POST   upload/batch   # Upload up to 1000 files
├─ GET    {id}/file      # Preview/download original (dept-scoped)
└─ DELETE {id}           # Delete document

/api/admin/
├─ GET    metrics        # Real tokens, cost, cache hits, latency, errors
├─ DELETE documents/{id} # Force delete
├─ GET    users          # Manage users
├─ PATCH/DELETE users/{id} # Update or delete user (self/last-admin guarded)
└─ POST   llm/config     # Configure LLM
```

## Key Design Patterns

### 1. MVC Pattern (Backend)
- **Models**: Django ORM models (models.py)
- **Views**: DRF API views (views/*.py)
- **Controllers**: Business logic in views

### 2. Component-Based Architecture (Frontend)
- Reusable React components
- Props drilling minimized with Context
- State management with React Hooks

### 3. RAG Pipeline Architecture
- Modular steps (retrieval, processing, generation)
- Step tracking for visualization
- Error handling and fallbacks

### 4. Permission-Based Access Control
- Granular role-based permissions
- Permission classes in views
- Serializer-level filtering

## State Management

### Backend State
- SQLite database (persistent)
- Redis + RediSearch (semantic/embedding/retrieval/rerank/prompt caches)
- Session variables (request scope)

### Frontend State
- React hooks (useState)
- localStorage (persistence)
- sessionStorage (temporary)

## Scalability Considerations

### Horizontal Scaling
- Stateless backend (can run multiple instances)
- Load balancer required
- Shared database needed

### Vertical Scaling
- Increase server resources
- Optimize queries
- Implement caching

### Optimization
- Database indexing
- Query pagination
- Lazy loading components
- Image optimization

---

This structure provides a clear separation of concerns and allows for easy maintenance and scalability.
