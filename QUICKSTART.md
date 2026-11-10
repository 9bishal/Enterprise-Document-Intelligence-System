# IntraDoc AI — Quick Start

Get IntraDoc AI running locally or use the hosted deployment.

## Live Deployment

- **Frontend:** https://intradoc-frontend.vercel.app
- **Backend API:** https://intradoc-backend.onrender.com/api
- **Health:** https://intradoc-backend.onrender.com/api/health/live

The Render free backend may take 30–60 seconds to wake after inactivity.

## Local Setup

Get IntraDoc AI running locally in minutes!

## 5-Minute Setup

### 1. Clone & Navigate

```bash
git clone https://github.com/9bishal/Enterprise-Document-Intelligence-System-.git
cd document_intelligent_system
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Run migrations
python manage.py migrate

# Start backend
python run.py
```

Backend available at: `http://localhost:8000`

### 3. Frontend Setup (new terminal)

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend available at: `http://localhost:5173`

### 4. Login

1. Open `http://localhost:5173` in your browser
2. Create account or use demo credentials
3. Start chatting!

---

## Essential Environment Variables

Create `.env` in the `backend/` directory:

```env
# Django
DEBUG=False
SECRET_KEY=change-me-to-something-secret

# LLM (admin LLMConfig in DB takes precedence when enforced)
GROQ_API_KEY=gsk-your-key-here

# Redis (required for semantic cache; must load RediSearch - see below)
INTRADOC_REDIS_URL=redis://localhost:6379/0

# RAG tuning (all optional, defaults shown)
INTRADOC_FAST_PATH=1
INTRADOC_SHORT_ANSWERS=1
INTRADOC_MAX_TOKENS=512
INTRADOC_MIN_SIMILARITY=20
INTRADOC_INDEX_WORKERS=2
```

Start Redis with the search module (semantic cache stays disabled without it):

```bash
./start_redis.sh
```

---

## First Steps After Setup

### 1. Create Admin Account

```bash
cd backend
python manage.py createsuperuser
```

### 2. Upload a Document

1. Open Documents, click Upload (single file or multi-select, up to 1000 per batch)
2. Select PDF, DOCX, TXT, or MD files
3. Choose a department
4. Click Upload - indexing runs 2-at-a-time in the background; re-uploading the
   same file supersedes the old version, byte-identical content is skipped

### 3. Start a Chat

1. Click "New Chat" button (each thread gets its own `/query/:id` URL)
2. Enter a question about your documents
3. Watch points stream in with live pipeline stages and cited sources
4. Repeat questions return from semantic cache in milliseconds

### 4. Manage Chat Sessions

Each chat in the sidebar has a **3-dot menu** (⋮) with:
- **Rename** - Rename the chat session
- **Delete** - Delete the chat session

---

## Troubleshooting

### Backend Won't Start

```bash
# Check Python version
python3 --version  # Should be 3.10+

# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Check port 8000 is available
lsof -i :8000  # Kill if needed: kill -9 PID
```

### Frontend Won't Load

```bash
# Clear cache
rm -rf node_modules package-lock.json
npm install

# Check port 5173
lsof -i :5173

# Check environment variables
echo $VITE_API_BASE  # Should point to backend
```

### Database Locked

```bash
# Reset database
cd backend
rm data/app.db
python manage.py migrate
```

### LLM API Errors

```bash
# Groq key lives in admin LLM Config (DB) or env
# Test a Groq key
curl https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $GROQ_API_KEY"
```

### Semantic Cache Disabled

```bash
# The RAG worker logs nothing but caching silently stays off when either
# condition fails: redisvl vectorizer mismatch, or Redis without RediSearch.
redis-cli module list  # must show the 'search' module
./start_redis.sh       # restarts Redis with RediSearch loaded
```

---

## Common Tasks

### Run Tests

```bash
# Backend
cd backend
python manage.py test

# Frontend
cd frontend
npm test
```

### View Database

```bash
cd backend
python manage.py dbshell
sqlite> .tables
sqlite> SELECT * FROM django_backend_user;
```

### Check API Endpoints

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/chat/sessions
```

### Build for Production

```bash
# Backend (no build needed - Django is ready)

# Frontend
cd frontend
npm run build
# Output in dist/ directory
```

---

## Next Steps

1. **Read the Documentation**
   - See [README.md](./README.md) for full documentation
   - See [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) for architecture
   - See [backend/README.md](./backend/README.md) for backend details

2. **Explore the Code**
   - Start with `frontend/src/pages/QueryPage.jsx` (main chat interface)
   - Check `backend/app/rag_graph.py` (RAG pipeline)
   - Review `backend/django_backend/views/rag.py` (API endpoints)

3. **Contribute**
   - See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines
   - Pick an issue to work on
   - Submit a pull request

4. **Deploy**
   - Use Docker for containerization
   - Deploy backend to AWS/Heroku/DigitalOcean
   - Deploy frontend to Vercel/Netlify

---

## Pro Tips

### Development Tips
- Use `django-debug-toolbar` for query optimization
- Use React DevTools browser extension
- Enable verbose logging: `DEBUG=True` in .env

### Testing Tips
- Test with different document types
- Try complex queries to see RAG in action
- Check the pipeline visualization

### Performance Tips
- Answers stream from a single LLM call with a 512-token cap; repeats hit semantic cache
- Tune `INTRADOC_INDEX_WORKERS` for big batch uploads
- Index important documents first

---

## 🆘 Getting Help

- **Issues**: Open a GitHub issue
- **Discussions**: Check GitHub Discussions
- **Docs**: Read the comprehensive documentation
- **Code**: Check existing implementation

---

## You're Ready!

The system is now running. Start uploading documents and asking questions!

Questions? Check the troubleshooting section or open an issue.
