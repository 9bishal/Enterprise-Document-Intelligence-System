import os
import hashlib
import threading
from django_backend.models import Document
from app.vector_store import index_document

try:
    from django_backend.cache.domain_caches import DocumentFingerprintCache
    from django_backend.monitoring.metrics import DOCUMENTS_INDEXED
    _fingerprint_cache = DocumentFingerprintCache()
    _cache_enabled = True
except Exception:
    _cache_enabled = False

def _compute_file_hash(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

# Helper function to classify and scan document risks
def analyze_document_classification_and_risks(filepath):
    try:
        from app.vector_store import extract_text_from_file
        pages_data = extract_text_from_file(filepath)
        if not pages_data:
            return "General", "Clean", "No text found to analyze."
        
        sample_text = ""
        for p in pages_data[:3]: # grab first 3 pages
            sample_text += p["text"] + "\n"
        
        sample_text = sample_text[:1500]
        
        prompt = f"""
        You are a corporate document security classifier and compliance screener. Analyze the document snippet below.
        
        Document Name: {os.path.basename(filepath)}
        Document Preview:
        {sample_text}
        
        Identify:
        1. The primary Classification of this document. It must be exactly one of: "Legal", "Financial", "Technical", "Human Resources", "General".
        2. Risk screening. Screen for confidentiality or regulatory compliance risks. Focus on:
           - Exposed API keys, secrets, private keys, passwords.
           - PII (Social Security Numbers, private phone numbers, home addresses).
           - Financial details (confidential salary charts, trade secrets).
         3. State if it is "Clean" or if a "Risk Detected" occurred.
        
        Format your output EXACTLY as a JSON object matching this schema:
        {{
            "classification": "Legal" | "Financial" | "Technical" | "Human Resources" | "General",
            "risk_status": "Clean" | "Risk Detected",
            "risk_details": "Explain in 1 sentence what risk was found, or leave empty if Clean."
        }}
        """
        
        from app.llm_helper import call_llm_json, resolve_llm_config
        llm_cfg = resolve_llm_config()
        if not llm_cfg:
            return "General", "Clean", ""
        res = call_llm_json(
            prompt=prompt,
            system_prompt="You are a precise corporate security compliance assistant. Return valid JSON only.",
            provider=llm_cfg["provider"],
            api_key=llm_cfg["api_key"],
            model_name=llm_cfg["model"],
            temperature=0.0
        )
        
        classification = res.get("classification", "General")
        risk_status = res.get("risk_status", "Clean")
        risk_details = res.get("risk_details", "")
        return classification, risk_status, risk_details
    except Exception as e:
        print(f"Error in analyze_document_classification_and_risks: {str(e)}")
        return "General", "Clean", f"Analysis error: {str(e)}"

# Background thread indexing worker with classification & risk analysis
def process_document_indexing(doc_id, filename, filepath, department='General'):
    try:
        print(f"Indexing background thread started for file: {filename} (Department: {department})")

        if _cache_enabled:
            try:
                content_hash = _compute_file_hash(filepath)
                if _fingerprint_cache.is_duplicate(doc_id, content_hash):
                    print(f"Document '{filename}' content unchanged, skipping re-indexing")
                    doc = Document.objects.get(id=doc_id)
                    doc.status = "indexed"
                    doc.save()
                    return
                _fingerprint_cache.set_fingerprint(doc_id, content_hash)
            except Exception as cache_error:
                print(f"Fingerprint cache unavailable for '{filename}'; continuing without it: {cache_error}")

        # 1. Run AI classification and risk screening IN PARALLEL with indexing.
        #    Classification is network-bound (LLM call), indexing is compute-bound
        #    (embedding), so overlapping them makes total time ~max() not the sum.
        classify_result = {}
        def _classify():
            try:
                classify_result["value"] = analyze_document_classification_and_risks(filepath)
            except Exception as e:
                classify_result["value"] = ("General", "Clean", f"Analysis error: {str(e)}")
        classify_thread = threading.Thread(target=_classify, daemon=True)
        classify_thread.start()

        # 2. Ingest document text chunks into department-scoped vector store
        chunk_count = index_document(doc_id, filename, filepath, department=department)

        # 3. Wait for classification to finish (already overlapped with embedding)
        classify_thread.join(timeout=90)
        classification, risk_status, risk_details = classify_result.get(
            "value", ("General", "Clean", "")
        )

        # 4. Map department to classification if needed
        dept_to_classification = {
            'HR': 'Human Resources',
            'Legal': 'Legal',
            'Finance': 'Financial',
            'Technical': 'Technical',
            'General': 'General'
        }
        
        mapped_classification = dept_to_classification.get(department, classification)
        if mapped_classification == 'General' and classification != 'General':
            mapped_classification = classification
        
        # 5. Save completed indices and AI metrics (unless a newer version
        #    superseded this document while it was indexing — then leave it
        #    retired instead of resurrecting it as indexed).
        doc = Document.objects.get(id=doc_id)
        if doc.status == "superseded":
            print(f"Document '{filename}' was superseded by a newer version during indexing; leaving it retired.")
            try:
                from app.vector_store import delete_document_from_index
                delete_document_from_index(doc_id, department=department)
            except Exception:
                pass
            return
        doc.status = "indexed"
        doc.chunk_count = chunk_count
        doc.classification = mapped_classification
        doc.risk_status = risk_status
        doc.risk_details = risk_details
        doc.save()

        if _cache_enabled:
            DOCUMENTS_INDEXED.labels(department, "indexed").inc()

        print(f"Indexing background thread completed successfully for: {filename} ({chunk_count} chunks, Class: {mapped_classification}, Risk: {risk_status}, Dept: {department})")
    except Exception as e:
        print(f"Indexing error in background thread for {filename}: {str(e)}")
        if _cache_enabled:
            DOCUMENTS_INDEXED.labels(department, "error").inc()
        try:
            doc = Document.objects.get(id=doc_id)
            doc.status = "error"
            doc.error_message = str(e)
            doc.save()
        except Exception:
            pass
