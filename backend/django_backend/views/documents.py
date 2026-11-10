import os
import uuid
import threading
from django.utils import timezone

# DRF Imports
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

# Custom imports
from django_backend.models import Document
from django_backend.permissions import IsViewerOrAbove, IsEditorOrAbove
from django_backend.serializers import DocumentSerializer
from app.vector_store import index_document, delete_document_from_index

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOADS_DIR = os.getenv("INTRADOC_UPLOADS_DIR", os.path.join(BASE_DIR, "uploads"))
os.makedirs(UPLOADS_DIR, exist_ok=True)

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
        
        # 1. Run AI classification and risk screening
        classification, risk_status, risk_details = analyze_document_classification_and_risks(filepath)
        
        # 2. Ingest document text chunks into department-scoped vector store
        chunk_count = index_document(doc_id, filename, filepath, department=department)
        
        # 3. Save completed indices and AI metrics
        doc = Document.objects.get(id=doc_id)
        doc.status = "indexed"
        doc.chunk_count = chunk_count
        doc.classification = classification
        doc.risk_status = risk_status
        doc.risk_details = risk_details
        doc.save()
        print(f"Indexing background thread completed successfully for: {filename} ({chunk_count} chunks, Class: {classification}, Risk: {risk_status}, Dept: {department})")
    except Exception as e:
        print(f"Indexing error in background thread for {filename}: {str(e)}")
        try:
            doc = Document.objects.get(id=doc_id)
            doc.status = "error"
            doc.error_message = str(e)
            doc.save()
        except Exception:
            pass

@api_view(['POST'])
@permission_classes([IsEditorOrAbove])
def upload_document(request):
    if 'file' not in request.FILES:
        return Response({"detail": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

    file = request.FILES['file']
    doc_id = str(uuid.uuid4())
    filename = file.name
    filepath = os.path.join(UPLOADS_DIR, f"{doc_id}_{filename}")

    # Get the user's department for scoping
    try:
        user_department = request.user.profile.department
        user_role = request.user.profile.role
    except Exception:
        user_department = 'General'
        user_role = 'Viewer'

    # If admin provides a specific department, override user_department
    if user_role == 'Admin':
        requested_dept = request.data.get("department")
        if requested_dept and requested_dept != "All Departments":
            user_department = requested_dept

    try:
        with open(filepath, "wb") as destination:
            for chunk in file.chunks():
                destination.write(chunk)
    except Exception as e:
        return Response({"detail": f"Failed to save file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    file_size = os.path.getsize(filepath)

    # Save initial metadata to DB with department scoping
    doc = Document.objects.create(
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

    # Spawn thread for background vector store indexing with department
    thread = threading.Thread(
        target=process_document_indexing,
        args=(doc_id, filename, filepath, user_department)
    )
    thread.start()

    return Response({
        "id": doc_id,
        "filename": filename,
        "status": "ingesting",
        "department": user_department,
        "message": f"File upload complete. Background parsing and vector indexing started for {user_department} department."
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
