import os
import uuid
import time
from functools import partial

# DRF Imports
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

# Custom imports
from django_backend.models import Document, DEPT_CHOICES
from django_backend.permissions import IsViewerOrAbove, IsEditorOrAbove
from django_backend.serializers import DocumentSerializer
from app.vector_store import delete_document_from_index
from .doc_indexing import process_document_indexing

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOADS_DIR = os.getenv("INTRADOC_UPLOADS_DIR", os.path.join(BASE_DIR, "uploads"))
os.makedirs(UPLOADS_DIR, exist_ok=True)

_REDIS_URL = os.getenv("INTRADOC_REDIS_URL", "redis://localhost:6379/0")

_INGESTION_POOL = None
_MAX_CONCURRENT_INDEXING = int(os.getenv("INTRADOC_INDEX_WORKERS", "2"))

def _get_pool():
    global _INGESTION_POOL
    if _INGESTION_POOL is None:
        from concurrent.futures import ThreadPoolExecutor
        _INGESTION_POOL = ThreadPoolExecutor(max_workers=_MAX_CONCURRENT_INDEXING, thread_name_prefix="ingest")
    return _INGESTION_POOL

def _rq_worker_alive(conn):
    try:
        import rq
        workers = [w for w in rq.Worker.all(connection=conn) if "ingestion" in w.queue_names()]
        return len(workers) > 0
    except Exception:
        return False

def _get_queue():
    try:
        import redis as _redis
        from rq import Queue
        _conn = _redis.from_url(_REDIS_URL)
        _conn.ping()
        return Queue("ingestion", connection=_conn, default_timeout=600)
    except Exception:
        return None

def _schedule_indexing(doc_id, filename, filepath, department):
    q = _get_queue()
    # Only use RQ when a worker is actually consuming the queue; otherwise run
    # in-process so uploads never get stuck in "ingesting".
    if q is not None and _rq_worker_alive(q.connection):
        from rq import Retry
        q.enqueue(process_document_indexing, doc_id, filename, filepath, department,
                  retry=Retry(max=3, interval=[10, 30, 60]),
                  job_timeout=600)
    else:
        _get_pool().submit(process_document_indexing, doc_id, filename, filepath, department)


def _normalize_text(text: str) -> str:
    import re
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _dedupe_by_content(filepath, filename, department, new_doc_id):
    """Content-based version handling for same-info/different-name uploads.

    Returns (action, matched_doc) where action is:
      'duplicate'   — byte-identical content exists: skip indexing entirely.
      'superseded'  — near-identical content (>= threshold): retire the old doc.
      None          — genuinely new content: index normally.
    All local (hash + text compare), zero LLM calls.
    """
    import hashlib
    from difflib import SequenceMatcher

    with open(filepath, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()

    try:
        candidates = Document.objects.filter(
            department=department, status__in=("indexed", "ingesting"),
        ).exclude(id=new_doc_id)
    except Exception as e:
        print(f"[dedupe] db lookup failed: {e}")
        return None, None
    if not candidates:
        return None, None

    # 1. Exact byte match: same info, different name — nothing to index.
    for doc in candidates:
        try:
            if not doc.path or not os.path.exists(doc.path):
                continue
            h = hashlib.sha256()
            with open(doc.path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            if h.hexdigest() == digest:
                print(f"[dedupe] {filename} is byte-identical to {doc.filename}; skipping index.")
                return "duplicate", doc
        except Exception:
            continue

    # 2. Near-duplicate: same info with edits (e.g. renamed v2). Compare
    # extracted text; threshold tunable via INTRADOC_DUP_SIM_THRESHOLD.
    try:
        threshold = float(os.getenv("INTRADOC_DUP_SIM_THRESHOLD", "1"))
    except ValueError:
        threshold = 1
    try:
        from app.vector_store import extract_text_from_file, get_department_collection
        pages = extract_text_from_file(filepath) or []
        new_text = _normalize_text(" ".join(p.get("text", "") for p in pages))[:20000]
    except Exception as e:
        print(f"[dedupe] extraction failed for {filename}: {e}")
        return None, None
    if len(new_text) < 500:
        return None, None  # too short to judge reliably

    best, best_ratio = None, 0.0
    try:
        coll = get_department_collection(department)
    except Exception as e:
        print(f"[dedupe] collection open failed: {e}")
        return None, None
    for doc in candidates:
        try:
            r = coll.get(where={"doc_id": str(doc.id)})
            old_text = _normalize_text(" ".join(r.get("documents", []) or []))[:20000]
            if len(old_text) < 500:
                continue
            ratio = SequenceMatcher(None, old_text, new_text, autojunk=False).ratio()
            if ratio > best_ratio:
                best, best_ratio = doc, ratio
        except Exception:
            continue

    if best is not None and best_ratio >= threshold:
        print(f"[dedupe] {filename} ~{best_ratio:.2f} similar to {best.filename}; superseding it.")
        try:
            delete_document_from_index(str(best.id), department=best.department)
        except Exception as e:
            print(f"[dedupe] chunk delete failed: {e}")
        best.status = "superseded"
        best.save(update_fields=["status"])
        try:
            from django_backend.cache.semantic_cache import SemanticResponseCache
            SemanticResponseCache().invalidate_for_document(str(new_doc_id), reason="document_superseded")
        except Exception as e:
            print(f"[dedupe] semantic cache invalidate failed: {e}")
        return "superseded", best
    return None, None


def _supersede_previous(filename, department, new_doc_id):
    """Version handling: a newly uploaded v2 retires the previous v1 with the
    same filename in the same department. The old row is kept for history but
    marked 'superseded' (retrieval only uses status='indexed'), its chunks are
    deleted from the vector store, and cached answers are invalidated so no
    stale v1 answer is ever served again."""
    try:
        old_docs = Document.objects.filter(
            filename=filename, department=department,
            status__in=("indexed", "ingesting"),
        ).exclude(id=new_doc_id)
        for old in old_docs:
            try:
                delete_document_from_index(str(old.id), department=old.department)
            except Exception as e:
                print(f"[version] chunk delete failed for superseded {filename}: {e}")
            old.status = "superseded"
            old.save(update_fields=["status"])
            print(f"[version] {filename} v1 ({old.id}) superseded by v2 ({new_doc_id})")
        if old_docs:
            try:
                from django_backend.cache.semantic_cache import SemanticResponseCache
                SemanticResponseCache().invalidate_for_document(str(new_doc_id), reason="document_superseded")
            except Exception as e:
                print(f"[version] semantic cache invalidate failed: {e}")
    except Exception as e:
        print(f"[version] supersede check failed for {filename}: {e}")

def _save_uploaded_file(file, doc_id, filename):
    filepath = os.path.join(UPLOADS_DIR, f"{doc_id}_{filename}")
    with open(filepath, "wb") as destination:
        for chunk in file.chunks():
            destination.write(chunk)
    return filepath

def _get_user_context(request):
    try:
        return request.user.profile.department, request.user.profile.role
    except Exception:
        return 'General', 'Viewer'

def _resolve_department(user_role, user_department, request):
    if user_role == 'Admin':
        requested_dept = request.data.get("department")
        if requested_dept and requested_dept != "All Departments":
            return requested_dept
    return user_department


ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}
MAX_UPLOAD_BYTES = int(os.getenv("INTRADOC_MAX_UPLOAD_MB", "25")) * 1024 * 1024
MAX_BATCH_BYTES = int(os.getenv("INTRADOC_MAX_BATCH_MB", "100")) * 1024 * 1024


def _validate_upload(file):
    """Return (safe_filename, error). Only supported document types are allowed."""
    filename = os.path.basename(file.name or "upload")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return filename, (
            f"Unsupported file type '{ext or 'unknown'}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}."
        )
    size = getattr(file, "size", 0) or 0
    if size <= 0:
        return filename, "Empty files are not accepted."
    if size > MAX_UPLOAD_BYTES:
        return filename, (
            f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit."
        )
    return filename, None


@api_view(['POST'])
@permission_classes([IsEditorOrAbove])
def upload_document(request):
    if 'file' not in request.FILES:
        return Response({"detail": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

    file = request.FILES['file']
    filename, upload_error = _validate_upload(file)
    if upload_error:
        return Response({"detail": upload_error}, status=status.HTTP_400_BAD_REQUEST)

    doc_id = str(uuid.uuid4())
    user_department, user_role = _get_user_context(request)
    user_department = _resolve_department(user_role, user_department, request)

    try:
        filepath = _save_uploaded_file(file, doc_id, filename)
    except Exception as e:
        return Response({"detail": f"Failed to save file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    file_size = os.path.getsize(filepath)

    Document.objects.create(
        id=doc_id,
        user=request.user,
        filename=filename,
        path=filepath,
        file_size=file_size,
        status="ingesting",
        classification="General",
        risk_status="Clean",
        department=user_department
    )

    _dup_action, _dup_matched = _dedupe_by_content(filepath, filename, user_department, doc_id)
    if _dup_action == "duplicate":
        Document.objects.filter(id=doc_id).update(status="duplicate")
        return Response({
            "id": doc_id,
            "filename": filename,
            "status": "duplicate",
            "department": user_department,
            "message": f"Same content is already indexed as '{_dup_matched.filename}'. Skipped indexing."
        })

    _supersede_previous(filename, user_department, doc_id)
    _schedule_indexing(doc_id, filename, filepath, user_department)

    return Response({
        "id": doc_id,
        "filename": filename,
        "status": "ingesting",
        "department": user_department,
        "message": f"File upload complete. Background parsing and vector indexing started for {user_department} department."
    })

@api_view(['POST'])
@permission_classes([IsEditorOrAbove])
def upload_documents_batch(request):
    files = request.FILES.getlist("files")
    if not files:
        return Response({"detail": "No files uploaded. Send as form-data with key 'files' (multiple)."}, status=status.HTTP_400_BAD_REQUEST)

    user_department, user_role = _get_user_context(request)
    user_department = _resolve_department(user_role, user_department, request)

    if len(files) > 1000:
        return Response({"detail": "Batch size limited to 1000 files per request."}, status=status.HTTP_400_BAD_REQUEST)

    total_size = sum(getattr(file, "size", 0) or 0 for file in files)
    if total_size > MAX_BATCH_BYTES:
        return Response(
            {"detail": f"Batch exceeds the {MAX_BATCH_BYTES // (1024 * 1024)} MB total upload limit."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    results = []
    errors = []
    for file in files:
        doc_id = str(uuid.uuid4())
        filename, upload_error = _validate_upload(file)
        if upload_error:
            errors.append({"filename": filename, "error": upload_error})
            continue
        try:
            filepath = _save_uploaded_file(file, doc_id, filename)
            file_size = os.path.getsize(filepath)
            Document.objects.create(
                id=doc_id,
                user=request.user,
                filename=filename,
                path=filepath,
                file_size=file_size,
                status="ingesting",
                classification="General",
                risk_status="Clean",
                department=user_department
            )
            _dup_action, _dup_matched = _dedupe_by_content(filepath, filename, user_department, doc_id)
            if _dup_action == "duplicate":
                Document.objects.filter(id=doc_id).update(status="duplicate")
                results.append({"id": doc_id, "filename": filename, "status": "duplicate",
                                "note": f"Same content already indexed as '{_dup_matched.filename}'"})
                continue
            _supersede_previous(filename, user_department, doc_id)
            _schedule_indexing(doc_id, filename, filepath, user_department)
            results.append({"id": doc_id, "filename": filename, "status": "ingesting"})
        except Exception as e:
            errors.append({"filename": filename, "error": str(e)})

    return Response({
        "dispatched": len(results),
        "errors": len(errors),
        "documents": results,
        "error_details": errors,
        "department": user_department,
        "message": f"{len(results)} files queued for indexing (concurrency={_MAX_CONCURRENT_INDEXING})."
    })

@api_view(['GET'])
@permission_classes([IsViewerOrAbove])
def get_documents_list(request):
    try:
        profile = request.user.profile
        user_role = profile.role
        user_department = profile.department
    except Exception:
        user_role = 'Viewer'
        user_department = 'General'

    # Admins see ALL documents, others see only their department
    if user_role == 'Admin':
        requested_dept = request.GET.get('department')
        if requested_dept and requested_dept != "All Departments":
            docs = Document.objects.filter(department=requested_dept).order_by("-created_at")
        else:
            docs = Document.objects.all().order_by("-created_at")
    else:
        docs = Document.objects.filter(department=user_department).order_by("-created_at")

    serializer = DocumentSerializer(docs, many=True)
    return Response(serializer.data)

@api_view(['DELETE'])
@permission_classes([IsEditorOrAbove])
def delete_document(request, doc_id):
    try:
        user_role = request.user.profile.role
        user_department = request.user.profile.department
    except Exception:
        user_role = 'Viewer'
        user_department = 'General'

    # Admins can delete any document, others only their department
    if user_role == 'Admin':
        doc = Document.objects.filter(id=doc_id).first()
    else:
        doc = Document.objects.filter(id=doc_id, department=user_department).first()

    if not doc:
        return Response({"detail": "Document not found or unauthorized."}, status=status.HTTP_404_NOT_FOUND)

    doc_department = doc.department

    # Delete from file system
    try:
        if os.path.exists(doc.path):
            os.remove(doc.path)
    except Exception as e:
        print(f"Error removing file from disk: {str(e)}")

    # Delete from ChromaDB vector store (department-scoped)
    try:
        delete_document_from_index(doc_id, department=doc_department)
    except Exception as e:
        print(f"Error removing vector embeddings: {str(e)}")

    # Delete SQLite metadata record
    doc.delete()
    return Response({"status": "success", "message": f"Document '{doc.filename}' deleted successfully."})

@api_view(['GET'])
@permission_classes([AllowAny])
def get_departments(request):
    return Response({"departments": [value for value, label in DEPT_CHOICES]})


_PREVIEW_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@api_view(['GET'])
@permission_classes([IsViewerOrAbove])
def preview_document(request, doc_id):
    """Serve the original uploaded file inline for in-app preview.
    Same department scoping as delete: admins any doc, others own department."""
    import mimetypes
    from django.http import FileResponse, Http404

    try:
        user_role = request.user.profile.role
        user_department = request.user.profile.department
    except Exception:
        user_role = 'Viewer'
        user_department = 'General'

    if user_role == 'Admin':
        doc = Document.objects.filter(id=doc_id).first()
    else:
        doc = Document.objects.filter(id=doc_id, department=user_department).first()
    if not doc:
        return Response({"detail": "Document not found or unauthorized."}, status=status.HTTP_404_NOT_FOUND)

    if not doc.path or not os.path.exists(doc.path):
        return Response({"detail": "File no longer available on the server."}, status=status.HTTP_404_NOT_FOUND)

    ext = os.path.splitext(doc.filename)[1].lower()
    content_type = _PREVIEW_CONTENT_TYPES.get(ext) or mimetypes.guess_type(doc.filename)[0] or "application/octet-stream"
    try:
        return FileResponse(open(doc.path, "rb"), content_type=content_type, filename=doc.filename, as_attachment=False)
    except Exception as e:
        raise Http404(f"Cannot serve file: {e}")
