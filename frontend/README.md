# IntraDoc AI — Frontend

React + Vite frontend for [IntraDoc AI](https://github.com/9bishal/Enterprise-Document-Intelligence-System-), a RAG-powered document intelligence platform.

## Live App

https://intradoc-frontend.vercel.app

The backend API is deployed at:

https://intradoc-backend.onrender.com/api

> Render's free backend may take 30–60 seconds to wake after inactivity.

## Features

- JWT login, registration, and password reset
- Document upload, batch upload, preview, and department filtering
- Streaming chat with citations and RAG pipeline visualization
- Chat session CRUD
- Admin user management, LLM configuration, and system metrics
- Responsive light interface

## Local Development

```bash
npm install
npm run dev
```

The app runs at `http://localhost:5173` by default.

Create `frontend/.env.local` if you need a custom API URL:

```env
VITE_API_BASE=http://localhost:8000/api
```

## Production Build

```bash
npm run build
npm run preview
```

Vercel uses `VITE_API_BASE=https://intradoc-backend.onrender.com/api`.

## Related Docs

- [Root README](../README.md)
- [Deployment guide](../DEPLOY_RENDER_VERCEL.md)
- [Backend README](../backend/README.md)
