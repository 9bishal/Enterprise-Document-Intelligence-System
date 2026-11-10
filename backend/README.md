# IntraDoc AI — Backend

Django REST Framework backend for IntraDoc AI, with a RAG pipeline, department-scoped vector search, JWT auth, and LLM integration.

## Live API

- API base: https://intradoc-backend.onrender.com/api
- Health: https://intradoc-backend.onrender.com/api/health/live
- Readiness: https://intradoc-backend.onrender.com/api/health/ready

Production uses **Neon Postgres** for user/document metadata and **Redis Stack** for caching. Render's free tier has no persistent disk, so uploaded files and Chroma vectors are ephemeral unless external storage is added.


## 📁 Backend Structure

```
backend/
├── app/                          # Core RAG & LLM Logic
│   ├── rag_graph.py             # RAG pipeline execution with step tracking
│   ├── llm_helper.py            # LLM API calls with SSL support
│   ├── vector_store.py          # Chroma vector database operations
│   ├── database.py              # Database initialization
│   └── main.py                  # Application startup
├── django_backend/              # Django Configuration
│   ├── models.py                # SQLAlchemy/Django ORM models
│   ├── serializers.py           # DRF serializers for API responses
│   ├── permissions.py           # Custom permission classes (RBAC)
│   ├── middleware.py            # Custom middleware (logging, auth)
│   ├── settings.py              # Django settings & configuration
│   ├── urls.py                  # URL routing configuration
│   ├── views/                   # API Views (endpoints)
│   │   ├── auth.py              # Authentication (login, register, refresh)
│   │   ├── doc_api.py           # Document CRUD endpoints
│   │   ├── doc_indexing.py      # Document indexing & classification
│   │   ├── documents.py         # Additional document operations
│   │   ├── rag.py               # RAG query endpoints
│   │   ├── rag_query.py         # Query-specific logic
│   │   ├── admin.py             # Admin operations
│   │   ├── admin_graph.py       # Admin graph/analytics
│   │   ├── admin_llm.py         # Admin LLM config
│   │   ├── admin_metrics.py     # System metrics
│   │   ├── admin_users.py       # User management
│   │   └── __init__.py          # Exports for easy importing
│   ├── migrations/              # Database schema migrations
│   └── __pycache__/             # Python bytecode cache
├── uploads/                     # Temporary file uploads
├── data/                        # Persistent data storage
│   ├── app.db                   # SQLite database
│   └── chroma/                  # Vector database (Chroma)
├── venv/                        # Python virtual environment
├── manage.py                    # Django management script
├── run.py                       # Application entry point (WSGI)
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables (git-ignored)
└── .env.example                 # Example environment template
```

## 🔧 Key Components

### 1. RAG Pipeline (`app/rag_graph.py`)

Handles the complete Retrieval-Augmented Generation flow:

```python
# Steps executed:
1. Document Retrieval   - Semantic search in vector store
2. Context Processing   - Format retrieved documents
3. Prompt Engineering   - Combine context with user question
4. LLM Generation       - Generate response from LLM
5. Response Formatting  - Add sources and metadata
```

**Features:**
- Step-by-step tracking for visualization
- Error handling and fallback mechanisms
- Source attribution with document references
- Department-based filtering

### 2. LLM Helper (`app/llm_helper.py`)

Manages LLM API interactions:

```python
# Supported Providers:
- OpenAI (GPT-3.5, GPT-4)
- Anthropic Claude
- Local LLMs (with proper setup)
```

**Features:**
- SSL/TLS certificate handling
- Configurable API keys per deployment
- Request/response formatting
- Error handling and retries
- Token counting and cost estimation

### 3. Vector Store (`app/vector_store.py`)

Manages semantic search using Chroma:

```python
# Operations:
- add_documents()     - Index new documents
- search()            - Semantic similarity search
- delete()            - Remove indexed documents
- update()            - Update document embeddings
```

**Features:**
- Chroma vector database integration
- Multiple distance metrics
- Batch processing support
- Metadata preservation

### 4. Django Models (`django_backend/models.py`)

Core database models:

```python
- User               # User accounts (with roles)
- Document          # Document metadata
- ChatSession       # Chat conversation sessions
- ChatMessage       # Individual chat messages
- LLMConfig        # LLM API configuration
- PasswordResetOTP # Two-factor authentication
```

### 5. REST API Views

#### Chat Session Endpoints (`views/rag.py`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/chat/sessions` | List all user's chat sessions |
| POST | `/api/chat/sessions` | Create new chat session |
| GET | `/api/chat/sessions/{id}` | Get session details |
| PUT | `/api/chat/sessions/{id}` | Update/rename session |
| DELETE | `/api/chat/sessions/{id}` | Delete chat session |
| GET | `/api/chat/sessions/{id}/messages` | Get all messages in session |
| POST | `/api/chat/query` | Send question & get RAG response |

#### Document Endpoints (`views/doc_api.py`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/documents` | List documents |
| POST | `/api/documents/upload` | Upload new document |
| GET | `/api/documents/{id}` | Get document details |
| DELETE | `/api/documents/{id}` | Delete document |
| GET | `/api/documents/search` | Search documents |

#### Admin Endpoints (`views/admin.py`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/admin/documents/delete` | Admin delete document |
| GET | `/api/admin/metrics` | System metrics |
| GET | `/api/admin/users` | Manage users |
| POST | `/api/admin/llm/config` | Configure LLM |

## 🚀 Setup & Installation

### 1. Environment Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

Create `.env` file:

```env
# Django
DEBUG=False
SECRET_KEY=your-super-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///data/app.db

# LLM Configuration
OPENAI_API_KEY=sk-xxxxxxxxxxxx
OPENAI_MODEL=gpt-4
LLM_TEMPERATURE=0.7

# Chroma Vector DB
CHROMA_HOST=localhost
CHROMA_PORT=8000

# JWT
JWT_SECRET=your-jwt-secret
JWT_ALGORITHM=HS256

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

### 4. Database Setup

```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files (production)
python manage.py collectstatic
```

### 5. Start Backend Server

```bash
# Development
python run.py

# Or using Django directly
python manage.py runserver 0.0.0.0:8000

# Production (Gunicorn)
gunicorn django_backend.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

## 📚 API Documentation

### Authentication Flow

1. **Register User**
   ```bash
   POST /api/auth/register
   {
     "username": "user@example.com",
     "password": "secure_password",
     "department": "HR"
   }
   ```

2. **Login**
   ```bash
   POST /api/auth/login
   {
     "username": "user@example.com",
     "password": "secure_password"
   }
   
   Response:
   {
     "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
     "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
     "user": { "id": 1, "role": "viewer" }
   }
   ```

3. **Use Token**
   ```bash
   Authorization: Bearer {access_token}
   ```

### Chat Session Management

**Create Session**
```bash
POST /api/chat/sessions
Header: Authorization: Bearer {token}
{
  "name": "Project Discussion"
}

Response: { "id": "uuid", "name": "Project Discussion", "created_at": "..." }
```

**Send Query**
```bash
POST /api/chat/query
Header: Authorization: Bearer {token}
{
  "session_id": "uuid",
  "question": "What are the HR policies?",
  "department": "HR",
  "api_keys": { "openai": "sk-..." },
  "config": { "model": "gpt-4", "temperature": 0.7 }
}

Response:
{
  "id": "message_uuid",
  "content": "Based on the documents...",
  "steps": [
    { "name": "retrieval", "status": "completed", "duration": 125 },
    { "name": "processing", "status": "completed", "duration": 45 },
    ...
  ],
  "sources": [
    { "document_id": "doc1", "title": "HR Handbook", "relevance": 0.95 }
  ]
}
```

## 🔐 Permission System

### Role-Based Access Control (RBAC)

| Role | Permissions |
|------|-------------|
| **Admin** | Full access, user management, document deletion |
| **Editor** | Create/edit documents, manage own chats |
| **Viewer** | Read documents, chat queries only |

### Permission Classes

```python
# Built-in permission classes
IsViewerOrAbove      # Viewer, Editor, Admin
IsEditorOrAbove      # Editor, Admin
IsAdmin              # Admin only
IsOwnerOrAdmin       # Owner or Admin
```

## 🧪 Testing

### Run Tests

```bash
# All tests
python manage.py test

# Specific test file
python manage.py test django_backend.tests.test_auth

# With coverage
coverage run --source='.' manage.py test
coverage report
```

### Test Structure

```
django_backend/tests/
├── test_auth.py          # Authentication tests
├── test_documents.py     # Document CRUD tests
├── test_rag.py           # RAG pipeline tests
└── test_permissions.py   # Permission system tests
```

## 🐛 Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Solution: Ensure venv is activated
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Database Locked**
   ```bash
   # Solution: Remove database and migrate again
   rm data/app.db
   python manage.py migrate
   ```

3. **Vector Store Connection Failed**
   ```bash
   # Ensure Chroma is running
   docker run -p 8000:8000 chromadb/chroma
   ```

4. **SSL Certificate Verification Failed**
   ```bash
   # Set environment variable
   export PYTHONHTTPSVERIFY=0  # (development only!)
   # Or fix certificate in production
   ```

5. **LLM API Key Issues**
   ```bash
   # Verify in .env
   OPENAI_API_KEY=sk-xxxxxxxx
   # Check API key validity
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

## 📊 Performance Optimization

### Database Indexing

```python
# Models have optimized indexes on:
- User.username (unique)
- Document.user_id (foreign key)
- ChatSession.user_id (foreign key)
- ChatMessage.session_id (foreign key)
```

### Caching Strategy

```python
# Implemented caching for:
- Document metadata (1 hour TTL)
- User permissions (30 min TTL)
- LLM responses (12 hours TTL)
```

### Query Optimization

```python
# Use select_related() for foreign keys
# Use prefetch_related() for reverse relationships
# Use only() to fetch specific fields
# Use values() for simple queries
```

## 🔍 Logging & Monitoring

### Logging Configuration

```python
# Logs location: logs/
# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

# Example usage:
logger.info("Document indexed", extra={"doc_id": doc_id})
logger.error("LLM API failed", exc_info=True)
```

### Monitoring Endpoints

```bash
# Health check
GET /api/health

# Metrics
GET /api/admin/metrics

# System status
GET /api/admin/status
```

## 📦 Dependencies Overview

### Core
- `django` - Web framework
- `djangorestframework` - REST API
- `django-cors-headers` - CORS support
- `django-environ` - Environment variables

### Data & Search
- `chromadb` - Vector database
- `sqlalchemy` - ORM
- `psycopg2-binary` - PostgreSQL support

### LLM & NLP
- `openai` - OpenAI API
- `langchain` - LLM orchestration
- `sentence-transformers` - Embeddings
- `pydantic` - Data validation

### Authentication
- `djangorestframework-simplejwt` - JWT auth
- `bcrypt` - Password hashing

### Utilities
- `python-dotenv` - .env loading
- `requests` - HTTP client
- `celery` - Async tasks (optional)

## 🚀 Deployment

### Production Checklist

```bash
# [ ] Set DEBUG=False in .env
# [ ] Update SECRET_KEY
# [ ] Set ALLOWED_HOSTS
# [ ] Configure database (PostgreSQL)
# [ ] Enable HTTPS
# [ ] Setup CORS properly
# [ ] Configure logging
# [ ] Setup monitoring
# [ ] Run migrations
# [ ] Collect static files
```

### Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "django_backend.wsgi:application", \
     "--bind", "0.0.0.0:8000"]
```

```bash
# Build and run
docker build -t doc-intelligent-system-backend .
docker run -p 8000:8000 doc-intelligent-system-backend
```

## 📞 Support & Documentation

- **Issues**: GitHub Issues
- **Docs**: See ../README.md for full documentation
- **API Docs**: Available at `/api/docs` (when enabled)
- **Database Schema**: See models.py

## 🎯 Future Enhancements

- [ ] Add webhook support for document events
- [ ] Implement advanced caching with Redis
- [ ] Add GraphQL API alongside REST
- [ ] Support for async document processing
- [ ] Multi-language support
- [ ] Advanced analytics dashboard
- [ ] Document versioning system

---

**Last Updated**: May 2026  
**Backend Version**: 1.0.0  
**Python Version**: 3.10+  
**Django Version**: 4.x+
# Enterprise-Document-Intelligence-System-
