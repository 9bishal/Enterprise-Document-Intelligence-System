import os
import uuid
import threading
# pyrefly: ignore [missing-import]
import docx2txt
# pyrefly: ignore [missing-import]
from pypdf import PdfReader
# pyrefly: ignore [missing-import]
from langchain_text_splitters import RecursiveCharacterTextSplitter
# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer
# pyrefly: ignore [missing-import]
import chromadb


# Serializes encode calls so concurrent ingest threads don't race on the
# shared model (MPS/GPU encode is not thread-safe).
_EMBED_LOCK = threading.Lock()


# Department list for multi-tenant vector isolation
DEPARTMENTS = ['HR', 'Legal', 'Finance', 'Technical', 'General']


# Cache integration (lazy initialized)
_cache_enabled = False
_vector_cache = {}

def _init_vector_cache():
    """Lazy init of embedding/retrieval caches - avoids import errors if optional deps missing."""
    global _cache_enabled, _vector_cache
    if _cache_enabled:
        return
    try:
        from django_backend.cache.embedding_cache import EmbeddingCache
        from django_backend.cache.domain_caches import RetrievalCache
        _vector_cache["embedding"] = EmbeddingCache()
        _vector_cache["retrieval"] = RetrievalCache()
        _cache_enabled = True
    except Exception:
        _cache_enabled = False

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

class LocalSentenceTransformerEmbeddings:
    """Wrapper for sentence-transformers to match LangChain Embeddings interface."""
    def __init__(self, model_name=EMBEDDING_MODEL_NAME):
        # CPU is the safe default: MPS/GPU crashes when encode runs in a
        # background ingestion thread. Override with INTRADOC_EMBED_DEVICE.
        device = os.getenv("INTRADOC_EMBED_DEVICE", "cpu")
        self.model = SentenceTransformer(model_name, device=device)

    def embed_documents(self, texts):
        """Batch encode documents for indexing - thread-safe with lock."""
        with _EMBED_LOCK:
            embeddings = self.model.encode(texts, show_progress_bar=False, batch_size=64)
        return [list(map(float, e)) for e in embeddings]

    def embed_query(self, text):
        """Encode single query - uses embedding cache if available."""
        _init_vector_cache()
        if _cache_enabled:
            try:
                ec = _vector_cache["embedding"]
                cached = ec.get_embedding(text, EMBEDDING_MODEL_NAME)
                if cached is not None:
                    return cached
            except Exception:
                pass
        with _EMBED_LOCK:
            embedding = self.model.encode(text, show_progress_bar=False)
        result = list(map(float, embedding))
        if _cache_enabled:
            try:
                ec = _vector_cache["embedding"]
                ec.set_embedding(text, EMBEDDING_MODEL_NAME, result)
            except Exception:
                pass
        return result


# Initialize ChromaDB client and local embeddings
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
CHROMA_PATH = os.path.join(DATA_DIR, "chroma")

chroma_client = chromadb.PersistentClient(
    path=CHROMA_PATH, settings=chromadb.Settings(anonymized_telemetry=False)
)

# Default fallback collection for backward compatibility
collection = chroma_client.get_or_create_collection("intradoc_rag")

embeddings_model = LocalSentenceTransformerEmbeddings()


def get_department_collection(department_name):
    """Get or create a department-specific ChromaDB collection."""
    safe_name = department_name.strip().lower()
    return chroma_client.get_or_create_collection(f"intradoc_{safe_name}")


def _table_to_markdown(table: list[list]) -> str:
    """Convert 2D array to markdown pipe table. First row = header."""
    if not table or not any(table):
        return ""
    # Clean cells
    cleaned = [[(c or "").strip().replace("\n", " ").replace("|", "/") for c in row] for row in table]
    # Remove empty rows
    cleaned = [r for r in cleaned if any(c for c in r)]
    if not cleaned:
        return ""
    header = cleaned[0]
    # Ensure header has content, else generic
    if not any(header):
        header = [f"Col{i+1}" for i in range(len(cleaned[0]))]
    md = "| " + " | ".join(header) + " |\n"
    md += "| " + " | ".join(["---"] * len(header)) + " |\n"
    for row in cleaned[1:]:
        # Pad row to header length
        row = (row + [""] * len(header))[:len(header)]
        md += "| " + " | ".join(row) + " |\n"
    return md.strip()


def extract_text_from_file(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    pages_text = []  # list of dicts: {"text": str, "page": int, "is_table": bool}

    if ext == ".pdf":
        # Try pdfplumber for table-aware extraction, fallback to pypdf
        try:
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                for i, page in enumerate(pdf.pages):
                    # 1. Extract tables first as markdown (structure preserved)
                    try:
                        tables = page.extract_tables() or []
                    except Exception:
                        tables = []
                    for table in tables:
                        md = _table_to_markdown(table)
                        if md:
                            pages_text.append({"text": md, "page": i + 1, "is_table": True})
                    # 2. Extract remaining text (pdfplumber text preserves layout better than pypdf)
                    try:
                        text = page.extract_text() or ""
                    except Exception:
                        text = ""
                    # Avoid duplicating table text already captured - pdfplumber text includes table cells,
                    # but we keep it as plain text fallback for non-tabular content
                    if text and text.strip():
                        # Deduplicate: if text is just table cells, skip if we already have tables
                        pages_text.append({"text": text.strip(), "page": i + 1, "is_table": False})
            # Fallback if pdfplumber yielded nothing (e.g. scanned PDF)
            if not pages_text:
                raise ValueError("pdfplumber yielded no text")
        except ImportError:
            # pdfplumber not installed - fallback to pypdf
            reader = PdfReader(filepath)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    pages_text.append({"text": text, "page": i + 1, "is_table": False})
        except Exception as e:
            # If pdfplumber failed, fallback to pypdf
            if not pages_text:
                try:
                    reader = PdfReader(filepath)
                    for i, page in enumerate(reader.pages):
                        text = page.extract_text()
                        if text and text.strip():
                            pages_text.append({"text": text, "page": i + 1, "is_table": False})
                except Exception:
                    # Re-raise original if both fail
                    if not pages_text:
                        raise e
    elif ext == ".docx":
        # Try python-docx for table-aware extraction, fallback to docx2txt
        try:
            from docx import Document
            doc = Document(filepath)
            # Extract tables as markdown
            for table in doc.tables:
                data = [[cell.text for cell in row.cells] for row in table.rows]
                md = _table_to_markdown(data)
                if md:
                    pages_text.append({"text": md, "page": 1, "is_table": True})
            # Extract paragraphs (non-table text)
            para_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            if para_text.strip():
                pages_text.append({"text": para_text.strip(), "page": 1, "is_table": False})
            # Fallback if nothing extracted
            if not pages_text:
                raise ValueError("python-docx yielded no text")
        except ImportError:
            text = docx2txt.process(filepath)
            if text and text.strip():
                pages_text.append({"text": text, "page": 1, "is_table": False})
        except Exception:
            # Fallback to docx2txt
            try:
                text = docx2txt.process(filepath)
                if text and text.strip():
                    # Avoid duplicate if we already have content
                    if not pages_text:
                        pages_text.append({"text": text, "page": 1, "is_table": False})
            except Exception:
                if not pages_text:
                    raise
    elif ext in [".txt", ".md", ".markdown"]:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        if text and text.strip():
            pages_text.append({"text": text, "page": 1, "is_table": False})
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    return pages_text


def index_document(doc_id, filename, filepath, department='General'):
    """Index document chunks into the department-specific ChromaDB collection.
    Table blocks are kept intact (not split) so column headers stay with values: | Price | 100 |
    """
    from app.semantic_chunk import semantic_chunk

    pages_data = extract_text_from_file(filepath)
    if not pages_data:
        raise ValueError("No text could be extracted from the file.")

    # Separate table blocks (preserve structure) from plain text
    table_blocks = [p for p in pages_data if p.get("is_table")]
    text_blocks = [p for p in pages_data if not p.get("is_table")]

    raw_chunks: list[str] = []
    chunk_pages: list[int] = []  # parallel page tracking
    chunk_is_table: list[bool] = []

    # 1. Add table blocks as-is (one chunk per table, or split by rows if too large with header repeat)
    for tb in table_blocks:
        md = tb["text"].strip()
        if not md:
            continue
        # If table is very large (>600 tokens), split row-wise keeping header
        lines = md.split("\n")
        # header = lines[0], separator = lines[1], rows = lines[2:]
        if len(md) // 4 > 600 and len(lines) > 4:
            header = lines[0]
            separator = lines[1]
            rows = lines[2:]
            # Chunk rows in groups of ~15 rows (~300 tokens)
            max_rows_per_chunk = 15
            for i in range(0, len(rows), max_rows_per_chunk):
                chunk_md = "\n".join([header, separator] + rows[i:i+max_rows_per_chunk])
                raw_chunks.append(chunk_md)
                chunk_pages.append(tb["page"])
                chunk_is_table.append(True)
        else:
            raw_chunks.append(md)
            chunk_pages.append(tb["page"])
            chunk_is_table.append(True)

    # 2. Semantic chunk remaining plain text
    if text_blocks:
        full_text = "\n\n".join(p["text"] for p in text_blocks)
        text_chunks = semantic_chunk(full_text, target_tokens=300, overlap_sentences=2)
        for tc in text_chunks:
            stripped = tc.strip()
            if not stripped:
                continue
            raw_chunks.append(stripped)
            # Map page for text chunks via first 80 chars
            first_sentence = stripped[:80].lower()
            page = 1
            for p in text_blocks:
                if first_sentence in p["text"].lower():
                    page = p["page"]
                    break
            chunk_pages.append(page)
            chunk_is_table.append(False)

    if not raw_chunks:
        raise ValueError("No text chunks generated.")

    # Build final chunks with metadata
    chunks = []
    chunk_metadatas = []
    chunk_ids = []

    for chunk_index, text_chunk in enumerate(raw_chunks):
        stripped = text_chunk.strip()
        if not stripped:
            continue
        chunks.append(stripped)
        chunk_metadatas.append({
            "doc_id": doc_id,
            "filename": filename,
            "page": chunk_pages[chunk_index] if chunk_index < len(chunk_pages) else 1,
            "chunk_index": chunk_index,
            "department": department,
            "is_table": chunk_is_table[chunk_index] if chunk_index < len(chunk_is_table) else False,
        })
        chunk_ids.append(f"{doc_id}_chunk_{chunk_index}")

    if not chunks:
        raise ValueError("No text chunks generated.")

    chunk_embeddings = embeddings_model.embed_documents(chunks)

    target_collection = get_department_collection(department)
    target_collection.add(
        ids=chunk_ids,
        embeddings=chunk_embeddings,
        metadatas=chunk_metadatas,
        documents=chunks,
    )

    return len(chunks)


def query_vector_store(query_text, n_results=4, doc_ids=None, department=None, admin_all=False, use_hybrid=True):
    """
    Query the vector store with department scoping.
    - admin_all=True: query ALL department collections, merge and sort results
    - department specified: query only that department's collection
    - neither: fall back to default collection (backward compat)
    - use_hybrid=True: fuse dense + BM25 via Reciprocal Rank Fusion
    """
    if doc_ids is not None and len(doc_ids) == 0:
        return []

    _init_vector_cache()
    cache_filters = {"n_results": n_results, "doc_ids": doc_ids, "department": department, "admin_all": admin_all}
    if _cache_enabled:
        rc = _vector_cache["retrieval"]
        cached = rc.get_results(query_text, cache_filters)
        if cached is not None:
            return cached

    query_embedding = embeddings_model.embed_query(query_text)

    where_clause = None
    if doc_ids is not None:
        if len(doc_ids) == 1:
            where_clause = {"doc_id": doc_ids[0]}
        else:
            where_clause = {"doc_id": {"$in": doc_ids}}

    # For hybrid search, fetch more candidates for RRF fusion
    dense_n = max(n_results * 3, 20) if use_hybrid else n_results

    def _query_single(coll, n):
        """Query a single ChromaDB collection with vector embedding."""
        c = coll.count()
        if c == 0:
            return []
        r = coll.query(query_embeddings=[query_embedding], n_results=min(n, c), where=where_clause)
        out = []
        if r and r["ids"] and len(r["ids"][0]) > 0:
            for i in range(len(r["ids"][0])):
                dist = r["distances"][0][i]
                # Chroma reports squared-Euclidean distance (d = 2*(1-cos) for
                # normalised embeddings), so true cosine similarity is
                # cos = 1 - d/2. Clamped to [0, 100] for display.
                cos_sim = max(0.0, 1.0 - dist / 2.0)
                out.append({
                    "id": r["ids"][0][i],
                    "text": r["documents"][0][i],
                    "filename": r["metadatas"][0][i]["filename"],
                    "doc_id": r["metadatas"][0][i]["doc_id"],
                    "page": r["metadatas"][0][i]["page"],
                    "chunk_index": r["metadatas"][0][i]["chunk_index"],
                    "department": r["metadatas"][0][i].get("department", department or "General"),
                    "similarity": round(cos_sim * 100, 1),  # True cosine similarity %
                })
        return out

    dense_results = []
    if admin_all:
        # Admin querying all departments - merge results from all dept collections
        seen = set()
        for dept in DEPARTMENTS:
            try:
                for c in _query_single(get_department_collection(dept), dense_n):
                    if c["id"] not in seen:
                        seen.add(c["id"])
                        dense_results.append(c)
            except Exception:
                continue
        # Also check default collection for backward compat
        try:
            for c in _query_single(collection, dense_n):
                if c["id"] not in seen:
                    seen.add(c["id"])
                    dense_results.append(c)
        except Exception:
            pass
    elif department:
        # Query specific department collection
        dense_results = _query_single(get_department_collection(department), dense_n)
    else:
        # Fallback to default collection
        dense_results = _query_single(collection, dense_n)

    if not dense_results:
        return []

    if use_hybrid and len(dense_results) > 1:
        from app.retrieval.bm25 import bm25_search
        from app.retrieval.hybrid import reciprocal_rank_fusion
        bm25_results = bm25_search(dense_results, query_text, top_k=len(dense_results))
        fused = reciprocal_rank_fusion(dense_results, bm25_results)
        result = fused[:n_results]
    else:
        dense_results.sort(key=lambda x: x["similarity"], reverse=True)
        result = dense_results[:n_results]

    if _cache_enabled and result:
        doc_ids_for_cache = list(set(c["doc_id"] for c in result))
        rc = _vector_cache["retrieval"]
        rc.set_results(query_text, cache_filters, result, doc_ids=doc_ids_for_cache)

    return result


def delete_document_from_index(doc_id, department=None):
    """Delete document chunks from the vector store.
    If department is specified, delete from that department's collection.
    Otherwise, try all collections including the legacy default.
    """
    if department:
        try:
            target_collection = get_department_collection(department)
            target_collection.delete(where={"doc_id": doc_id})
        except Exception as e:
            print(f"Error deleting from department {department}: {str(e)}")
    else:
        # Try all department collections and the legacy default
        for dept in DEPARTMENTS:
            try:
                dept_collection = get_department_collection(dept)
                dept_collection.delete(where={"doc_id": doc_id})
            except Exception:
                pass
        try:
            collection.delete(where={"doc_id": doc_id})
        except Exception:
            pass


def delete_from_vector_store(doc_id, department=None):
    """Alias for delete_document_from_index for consistency."""
    return delete_document_from_index(doc_id, department)
