import os
import uuid
import shutil
from typing import Dict, Any, Optional
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Body
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

# Local imports
from app.database import (
    init_db,
    add_document,
    update_document_status,
    get_all_documents,
    delete_document_record,
    create_session,
    get_all_sessions,
    delete_session_record,
    add_message,
    get_session_messages,
)
from app.vector_store import index_document, delete_document_from_index
from app.rag_graph import run_rag_pipeline

# Prometheus metrics endpoint
try:
    # pyrefly: ignore [missing-import]
    from prometheus_client import make_wsgi_app
    # pyrefly: ignore [missing-import]
    from werkzeug.middleware.dispatcher import DispatcherMiddleware
    _prometheus_available = True
except Exception:
    _prometheus_available = False

app = FastAPI(
    title="Intradoc AI API", description="FastAPI Backend for LangGraph RAG application"
)

# Setup CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Uploads directory
UPLOADS_DIR = os.getenv(
    "INTRADOC_UPLOADS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads"),
)
os.makedirs(UPLOADS_DIR, exist_ok=True)


# Mount Prometheus metrics endpoint
if _prometheus_available:

    # pyrefly: ignore [missing-import]
    from werkzeug.middleware.dispatcher import DispatcherMiddleware
    app.mount("/metrics", make_wsgi_app())

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    init_db()


# Pydantic Schemas
class SessionCreate(BaseModel):
    name: str


class ModelConfig(BaseModel):
    provider: str = "gemini"
    model: str = "gemini-1.5-flash"
    temperature: float = 0.3
    k: int = 4


class QueryRequest(BaseModel):
    session_id: str
    question: str
    api_keys: Dict[str, str] = Field(default_factory=dict)
    config: ModelConfig = Field(default_factory=ModelConfig)


# Background task for ingestion
def process_document_indexing(doc_id: str, filename: str, filepath: str):
    try:
        print(f"Starting indexing background task for file: {filename}")
        chunk_count = index_document(doc_id, filename, filepath)
        update_document_status(doc_id, "indexed", chunk_count=chunk_count)
        print(f"Successfully indexed {filename} with {chunk_count} chunks")
    except Exception as e:
        print(f"Error indexing {filename}: {str(e)}")
        update_document_status(doc_id, "error", error_message=str(e))


# Endpoints
@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}


# 1. Document Management Endpoints
@app.post("/api/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks, file: UploadFile = File(...)
):
    doc_id = str(uuid.uuid4())
    filename = file.filename
    filepath = os.path.join(UPLOADS_DIR, f"{doc_id}_{filename}")

    # Save file to disk
    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    file_size = os.path.getsize(filepath)

    # Add to SQLite as 'ingesting'
    add_document(doc_id, filename, filepath, file_size)

    # Trigger background indexing task
    background_tasks.add_task(process_document_indexing, doc_id, filename, filepath)

    return {
        "id": doc_id,
        "filename": filename,
        "status": "ingesting",
        "message": "File upload complete. Parsing and indexing started.",
    }


@app.get("/api/documents")
def get_documents_list():
    return get_all_documents()


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    # Get document info to delete file from disk
    from app.database import get_document

    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from file system
    try:
        if os.path.exists(doc["path"]):
            os.remove(doc["path"])
    except Exception as e:
        print(f"Error removing file from disk: {str(e)}")

    # Delete from ChromaDB
    try:
        delete_document_from_index(doc_id)
    except Exception as e:
        print(f"Error removing vector embeddings: {str(e)}")

    # Delete SQLite record
    delete_document_record(doc_id)

    return {
        "status": "success",
        "message": f"Document '{doc['filename']}' deleted successfully",
    }


# 2. Chat Session Management Endpoints
@app.post("/api/chat/sessions")
def start_chat_session(payload: SessionCreate):
    session_id = str(uuid.uuid4())
    create_session(session_id, payload.name)
    return {"id": session_id, "name": payload.name}


@app.get("/api/chat/sessions")
def list_chat_sessions():
    return get_all_sessions()


@app.delete("/api/chat/sessions/{session_id}")
def delete_chat_session(session_id: str):
    delete_session_record(session_id)
    return {"status": "success", "message": "Session deleted successfully"}


@app.get("/api/chat/sessions/{session_id}/messages")
def get_messages(session_id: str):
    return get_session_messages(session_id)


# 3. Core RAG Query Endpoint
@app.post("/api/chat/query")
def query_rag(payload: QueryRequest):
    session_id = payload.session_id
    question = payload.question
    api_keys = payload.api_keys
    model_config = payload.config.dict()

    # Save User message to database
    user_msg_id = str(uuid.uuid4())
    add_message(user_msg_id, session_id, "user", question)

    # Run the stateful LangGraph RAG pipeline
    result = run_rag_pipeline(question, api_keys, model_config)

    # Save Assistant message to database
    assistant_msg_id = str(uuid.uuid4())
    add_message(
        assistant_msg_id,
        session_id,
        "assistant",
        result["generation"],
        sources=result["documents"],
        steps=result["steps"],
    )

    return {
        "id": assistant_msg_id,
        "role": "assistant",
        "content": result["generation"],
        "sources": result["documents"],
        "steps": result["steps"],
        "success": result["success"],
    }
