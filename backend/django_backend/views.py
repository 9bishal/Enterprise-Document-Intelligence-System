import os
import uuid
import json
import logging
import random
import string
import threading
from django.db import models
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from datetime import timedelta

# DRF Imports
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

# Custom imports
from django_backend.models import Document, ChatSession, ChatMessage, UserProfile, UserInvitation, PasswordResetOTP, LLMConfig, DEPT_CHOICES
from django_backend.permissions import IsViewerOrAbove, IsEditorOrAbove, IsAdminUser
from django_backend.serializers import (
    UserSerializer, DocumentSerializer, ChatSessionSerializer, ChatMessageSerializer
)
from app.vector_store import index_document, delete_document_from_index
from app.rag_graph import run_rag_pipeline

UPLOADS_DIR = os.getenv(
    "INTRADOC_UPLOADS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads"),
)
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

# --- Authentication Endpoints ---

@api_view(['POST'])
@permission_classes([AllowAny])
def auth_signup(request):
    username = request.data.get("username")
    password = request.data.get("password")
    email = request.data.get("email", "")
    otp = request.data.get("otp", "")

    if not username or not password:
        return Response({"detail": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({"detail": "Username already exists."}, status=status.HTTP_400_BAD_REQUEST)

    # First-user bootstrap: allow the first user to self-register as Admin
    if User.objects.count() == 0:
        user = User.objects.create_user(username=username, password=password, email=email)
        profile = UserProfile.objects.create(user=user, role='Admin', department='General')
        refresh = RefreshToken.for_user(user)
        return Response({
            "username": user.username,
            "role": "Admin",
            "department": "General",
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "detail": "First user registered as Admin successfully."
        }, status=status.HTTP_201_CREATED)

    # All subsequent users must have a valid OTP invitation
    if not email or not otp:
        return Response({"detail": "Email and OTP code are required for registration. Contact your administrator for an invitation."}, status=status.HTTP_400_BAD_REQUEST)

    # Validate invitation
    invitation = UserInvitation.objects.filter(
        email=email, otp=otp, is_verified=False
    ).first()

    if not invitation:
        return Response({"detail": "Invalid email or OTP code. Please check and try again."}, status=status.HTTP_400_BAD_REQUEST)

    if invitation.expires_at < timezone.now():
        return Response({"detail": "OTP has expired. Please request a new invitation from your administrator."}, status=status.HTTP_400_BAD_REQUEST)

    # Create user with pre-assigned role and department from invitation
    user = User.objects.create_user(username=username, password=password, email=email)
    profile = UserProfile.objects.create(
        user=user,
        role=invitation.role,
        department=invitation.department
    )

    # Mark invitation as verified
    invitation.is_verified = True
    invitation.save()

    refresh = RefreshToken.for_user(user)
    return Response({
        "username": user.username,
        "role": invitation.role,
        "department": invitation.department,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "detail": "Signup successful."
    }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([AllowAny])
def auth_login(request):
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response({"detail": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=username, password=password)
    if user is not None:
        profile, created = UserProfile.objects.get_or_create(user=user, defaults={'role': 'Viewer', 'department': 'General'})
        refresh = RefreshToken.for_user(user)
        return Response({
            "username": user.username,
            "role": profile.role,
            "department": profile.department,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "detail": "Login successful."
        })
    else:
        return Response({"detail": "Invalid username or password."}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auth_logout(request):
    return Response({"detail": "Logout successful."})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def auth_me(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user, defaults={'role': 'Viewer', 'department': 'General'})
    return Response({
        "username": request.user.username,
        "role": profile.role,
        "department": profile.department,
        "authenticated": True
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def auth_forgot_password(request):
    email = request.data.get("email")
    if not email:
        return Response({"detail": "Email is required."}, status=400)
        
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"detail": "No registered user found with this email."}, status=404)
        
    otp = ''.join(random.choices(string.digits, k=6))
    
    PasswordResetOTP.objects.filter(email=email).delete()
    PasswordResetOTP.objects.create(email=email, otp=otp)
    
    # Send OTP via email (no console print)
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        send_mail(
            subject="Intradoc AI — Password Reset OTP",
            message=(
                f"Hello,\n\n"
                f"You requested a password reset for your Intradoc AI account.\n\n"
                f"Your OTP is:\n\n"
                f"    {otp}\n\n"
                f"This code expires in 15 minutes.\n\n"
                f"If you did not request this, please ignore this email.\n\n"
                f"— Intradoc AI"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"SMTP failed for password reset {email}: {e}")
        return Response({"detail": "Failed to send OTP email. Please contact administrator."}, status=500)
    
    return Response({"message": "Password reset OTP sent to email."})

@api_view(['POST'])
@permission_classes([AllowAny])
def auth_reset_password(request):
    email = request.data.get("email")
    otp = request.data.get("otp")
    new_password = request.data.get("new_password")
    
    if not email or not otp or not new_password:
        return Response({"detail": "Email, OTP, and new password are required."}, status=400)
        
    try:
        reset_entry = PasswordResetOTP.objects.get(email=email, otp=otp)
    except PasswordResetOTP.DoesNotExist:
        return Response({"detail": "Invalid or expired OTP."}, status=400)
        
    try:
        user = User.objects.get(email=email)
        user.set_password(new_password)
        user.save()
        reset_entry.delete()
        return Response({"message": "Password reset successfully."})
    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=404)

@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def admin_update_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        
        # Superuser protection
        if user.is_superuser:
            return Response({"detail": "Cannot modify root superuser."}, status=403)
            
        data = request.data
        if 'role' in data:
            user.profile.role = data['role']
        if 'department' in data:
            user.profile.department = data['department']
            
        user.profile.save()
        return Response({"detail": f"User {user.username} updated."})
    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=404)

# ---------------------------------------------------------------------
# Global System Settings
# ---------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_public_llm_config(request):
    config = LLMConfig.objects.first()
    if not config:
        config = LLMConfig.objects.create()
    
    return Response({
        "enforce_globally": config.enforce_globally,
        "config": {
            "provider": config.provider,
            "model": config.model,
            "temperature": config.temperature,
            "k": config.k
        }
    })

@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_admin_llm_config(request):
    config = LLMConfig.objects.first()
    if not config:
        config = LLMConfig.objects.create()
        
    return Response({
        "enforce_globally": config.enforce_globally,
        "config": {
            "provider": config.provider,
            "model": config.model,
            "temperature": config.temperature,
            "k": config.k
        },
        "api_keys": config.masked_keys()
    })

@api_view(['PUT'])
@permission_classes([IsAdminUser])
def update_admin_llm_config(request):
    config = LLMConfig.objects.first()
    if not config:
        config = LLMConfig.objects.create()
        
    data = request.data
    config.enforce_globally = data.get("enforce_globally", config.enforce_globally)
    
    cfg = data.get("config", {})
    if 'provider' in cfg: config.provider = cfg['provider']
    if 'model' in cfg: config.model = cfg['model']
    if 'temperature' in cfg: config.temperature = cfg['temperature']
    if 'k' in cfg: config.k = cfg['k']
    
    keys = data.get("api_keys", {})
    if "groq" in keys and keys["groq"] and "*" not in keys["groq"]:
        config.set_groq_key(keys["groq"])
    if "gemini" in keys and keys["gemini"] and "*" not in keys["gemini"]:
        config.set_gemini_key(keys["gemini"])
    if "openai" in keys and keys["openai"] and "*" not in keys["openai"]:
        config.set_openai_key(keys["openai"])
        
    config.save()
    
    return Response({"message": "System LLM configuration updated."})

# --- Document Management Endpoints ---

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

    limit = int(request.GET.get('limit', 100))
    offset = int(request.GET.get('offset', 0))
    total = docs.count()
    docs = docs[offset:offset + limit]

    serializer = DocumentSerializer(docs, many=True)
    return Response({
        "results": serializer.data,
        "total": total,
        "limit": limit,
        "offset": offset
    })

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

# --- Session & Chat Endpoints ---

@api_view(['GET', 'POST'])
@permission_classes([IsViewerOrAbove])
def chat_sessions_api(request):
    if request.method == "POST":
        name = request.data.get("name")
        if not name:
            return Response({"detail": "Session name is required"}, status=status.HTTP_400_BAD_REQUEST)

        session_id = str(uuid.uuid4())
        session = ChatSession.objects.create(
            id=session_id,
            user=request.user,
            name=name
        )
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    else:
        sessions = ChatSession.objects.filter(user=request.user).order_by("-created_at")
        serializer = ChatSessionSerializer(sessions, many=True)
        return Response(serializer.data)

@api_view(['DELETE'])
@permission_classes([IsViewerOrAbove])
def delete_chat_session(request, session_id):
    session = ChatSession.objects.filter(user=request.user, id=session_id).first()
    if not session:
        return Response({"detail": "Session not found or unauthorized."}, status=status.HTTP_404_NOT_FOUND)

    session.delete()
    return Response({"status": "success", "message": "Session deleted successfully."})

@api_view(['GET'])
@permission_classes([IsViewerOrAbove])
def get_messages(request, session_id):
    session = ChatSession.objects.filter(user=request.user, id=session_id).first()
    if not session:
        return Response({"detail": "Session not found or unauthorized."}, status=status.HTTP_404_NOT_FOUND)

    messages = ChatMessage.objects.filter(session=session).order_by("created_at")
    serializer = ChatMessageSerializer(messages, many=True)
    return Response(serializer.data)

# --- Core RAG Execution Endpoint ---

@api_view(['POST'])
@permission_classes([IsViewerOrAbove])
def query_rag(request):
    session_id = request.data.get("session_id")
    question = request.data.get("question")
    api_keys = request.data.get("api_keys", {})
    config_payload = request.data.get("config", {})

    if not session_id or not question:
        return Response({"detail": "session_id and question are required."}, status=status.HTTP_400_BAD_REQUEST)

    session = ChatSession.objects.filter(user=request.user, id=session_id).first()
    if not session:
        return Response({"detail": "Session not found or unauthorized."}, status=status.HTTP_404_NOT_FOUND)

    # 1. Save User Message in database
    user_msg_id = str(uuid.uuid4())
    ChatMessage.objects.create(
        id=user_msg_id,
        session=session,
        role="user",
        content=question
    )

    # 2. Get user's department and role for scoping
    try:
        profile = request.user.profile
        user_role = profile.role
        user_department = profile.department
    except Exception:
        user_role = 'Viewer'
        user_department = 'General'

    is_admin = user_role == 'Admin'

    requested_dept = request.data.get("department")
    
    admin_all = is_admin
    target_dept = user_department
    
    if is_admin:
        if requested_dept and requested_dept != "All Departments":
            admin_all = False
            target_dept = requested_dept
        else:
            target_dept = None

    # 3. Collect user's indexed document IDs for vector query isolation
    if admin_all:
        user_docs = Document.objects.filter(status="indexed")
    elif is_admin:
        user_docs = Document.objects.filter(department=target_dept, status="indexed")
    else:
        user_docs = Document.objects.filter(department=user_department, status="indexed")
    user_doc_ids = [str(d.id) for d in user_docs]

    # Convert config format
    
    # Check Global Settings Enforcements
    llm_config = LLMConfig.objects.first()
    if llm_config and llm_config.enforce_globally:
        api_keys = {
            "gemini": llm_config.get_gemini_key(),
            "openai": llm_config.get_openai_key(),
            "groq": llm_config.get_groq_key()
        }
        model_config = {
            "provider": llm_config.provider,
            "model": llm_config.model,
            "temperature": llm_config.temperature,
            "k": llm_config.k
        }
    else:
        model_config = {
            "provider": config_payload.get("provider", "gemini"),
            "model": config_payload.get("model", "gemini-1.5-flash"),
            "temperature": config_payload.get("temperature", 0.3),
            "k": config_payload.get("k", 4)
        }

    # 4. Execute the stateful LangGraph pipeline with department scoping
    result = run_rag_pipeline(
        question, api_keys, model_config,
        user_doc_ids=user_doc_ids,
        department=target_dept,
        admin_all=admin_all
    )

    # 5. Save Assistant Response in database
    assistant_msg_id = str(uuid.uuid4())
    ChatMessage.objects.create(
        id=assistant_msg_id,
        session=session,
        role="assistant",
        content=result["generation"],
        sources=json.dumps(result["documents"]),
        steps=json.dumps(result["steps"])
    )

    return Response({
        "id": assistant_msg_id,
        "role": "assistant",
        "content": result["generation"],
        "sources": result["documents"],
        "steps": result["steps"],
        "success": result["success"]
    })

# --- Admin Monitoring Endpoint ---

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_metrics(request):
    # Counts
    total_users = User.objects.count()
    total_documents = Document.objects.count()
    total_chunks = Document.objects.aggregate(models.Sum('chunk_count'))['chunk_count__sum'] or 0
    total_file_size = Document.objects.aggregate(models.Sum('file_size'))['file_size__sum'] or 0
    total_sessions = ChatSession.objects.count()
    
    # User lists with role and department
    users_list = []
    for u in User.objects.all():
        profile, _ = UserProfile.objects.get_or_create(user=u, defaults={'role': 'Viewer', 'department': 'General'})
        users_list.append({
            "username": u.username,
            "role": profile.role,
            "department": profile.department,
            "date_joined": u.date_joined.isoformat()
        })
        
    # Classification distributions
    class_dist = list(Document.objects.values('classification').annotate(count=models.Count('id')))
    class_dist_map = {c['classification']: c['count'] for c in class_dist}
    for cat in ["Legal", "Financial", "Technical", "Human Resources", "General"]:
        if cat not in class_dist_map:
            class_dist_map[cat] = 0
            
    # Risk flagged documents
    flagged_docs = Document.objects.filter(risk_status="Risk Detected").order_by("-created_at")
    flagged_docs_list = [{
        "id": d.id,
        "filename": d.filename,
        "owner": d.user.username,
        "classification": d.classification,
        "risk_status": d.risk_status,
        "risk_details": d.risk_details,
        "department": d.department,
        "created_at": d.created_at.isoformat()
    } for d in flagged_docs]
    
    # Estimated tokens based on character counts / 4
    total_chars_agg = ChatMessage.objects.aggregate(total=models.Sum(models.functions.Length('content')))
    total_chars = total_chars_agg['total'] or 0
    estimated_tokens = int(total_chars / 4)
    
    # Recent activities
    recent_activity_list = []
    
    recent_docs = Document.objects.order_by("-created_at")[:5]
    for d in recent_docs:
        recent_activity_list.append({
            "type": "upload",
            "username": d.user.username,
            "filename": d.filename,
            "department": d.department,
            "timestamp": d.created_at.isoformat()
        })
        
    recent_msgs = ChatMessage.objects.filter(role="user").order_by("-created_at")[:5]
    for m in recent_msgs:
        recent_activity_list.append({
            "type": "chat",
            "username": m.session.user.username,
            "content": m.content[:40] + ("..." if len(m.content) > 40 else ""),
            "timestamp": m.created_at.isoformat()
        })
        
    # Sort recent activity by timestamp descending
    recent_activity_list = sorted(recent_activity_list, key=lambda x: x['timestamp'], reverse=True)[:8]
    
    return Response({
        "metrics": {
            "total_users": total_users,
            "total_documents": total_documents,
            "total_chunks": total_chunks,
            "total_file_size": total_file_size,
            "total_sessions": total_sessions,
            "estimated_tokens": estimated_tokens
        },
        "users": users_list,
        "classification_distribution": class_dist_map,
        "flagged_documents": flagged_docs_list,
        "recent_activities": recent_activity_list
    })

# --- Admin Invite Endpoint ---

@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_invite(request):
    """Send an OTP invitation email to a new employee."""
    email = request.data.get("email", "").strip()
    role = request.data.get("role", "Viewer")
    department = request.data.get("department", "General")

    if not email:
        return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

    # Validate role and department
    valid_roles = ['Viewer', 'Editor', 'Admin']
    valid_departments = ['HR', 'Legal', 'Finance', 'Technical', 'General']

    if role not in valid_roles:
        return Response({"detail": f"Invalid role. Must be one of: {', '.join(valid_roles)}"}, status=status.HTTP_400_BAD_REQUEST)
    if department not in valid_departments:
        return Response({"detail": f"Invalid department. Must be one of: {', '.join(valid_departments)}"}, status=status.HTTP_400_BAD_REQUEST)

    # Check if user with this email already exists
    if User.objects.filter(email=email).exists():
        return Response({"detail": "A user with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)

    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    expires_at = timezone.now() + timedelta(minutes=15)

    # Create or update invitation (re-invite invalidates previous OTP)
    invitation, created = UserInvitation.objects.update_or_create(
        email=email,
        defaults={
            "otp": otp,
            "role": role,
            "department": department,
            "expires_at": expires_at,
            "is_verified": False,
        }
    )

    # Send email via Django SMTP
    try:
        from django.core.mail import send_mail
        subject = "Intradoc AI — Your Corporate Workspace Invitation"
        message = (
            f"Hello,\n\n"
            f"You have been invited to join Intradoc AI as a {role} in the {department} department.\n\n"
            f"Your one-time registration code is:\n\n"
            f"    {otp}\n\n"
            f"This code expires in 15 minutes.\n\n"
            f"To complete your registration:\n"
            f"1. Go to http://localhost:5173\n"
            f"2. Click 'Register now'\n"
            f"3. Enter your username, password, this email, and the code above\n\n"
            f"— Intradoc AI Administration"
        )
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return Response({
            "detail": f"Invitation sent successfully to {email}.",
            "role": role,
            "department": department
        })
    except Exception as e:
        print(f"SMTP email send error for {email}: {str(e)}")
        return Response({
            "detail": f"Invitation created but email delivery failed. Contact the new employee manually with their OTP.",
            "role": role,
            "department": department
        }, status=status.HTTP_207_MULTI_STATUS)


# --- Admin User Management Endpoints ---

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_users_list(request):
    """Get all users with their profiles for the corporate roster."""
    users_data = []
    for u in User.objects.all().order_by('-date_joined'):
        profile, _ = UserProfile.objects.get_or_create(user=u, defaults={'role': 'Viewer', 'department': 'General'})
        users_data.append({
            "id": u.id,
            "username": u.username,
            "email": u.email or "",
            "role": profile.role,
            "department": profile.department,
            "date_joined": u.date_joined.isoformat()
        })
    return Response(users_data)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def admin_update_user(request, user_id):
    """Update a user's role and/or department."""
    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    profile, _ = UserProfile.objects.get_or_create(user=target_user, defaults={'role': 'Viewer', 'department': 'General'})

    # Prevent admin from demoting themselves
    if target_user.id == request.user.id:
        new_role = request.data.get("role", profile.role)
        if new_role != 'Admin':
            return Response({"detail": "You cannot demote yourself. Ask another admin to change your role."}, status=status.HTTP_400_BAD_REQUEST)

    new_role = request.data.get("role", None)
    new_department = request.data.get("department", None)

    if new_role:
        valid_roles = ['Viewer', 'Editor', 'Admin']
        if new_role not in valid_roles:
            return Response({"detail": f"Invalid role. Must be one of: {', '.join(valid_roles)}"}, status=status.HTTP_400_BAD_REQUEST)
        profile.role = new_role

    if new_department:
        valid_departments = ['HR', 'Legal', 'Finance', 'Technical', 'General']
        if new_department not in valid_departments:
            return Response({"detail": f"Invalid department. Must be one of: {', '.join(valid_departments)}"}, status=status.HTTP_400_BAD_REQUEST)
        profile.department = new_department

    profile.save()

    return Response({
        "detail": f"User '{target_user.username}' updated successfully.",
        "id": target_user.id,
        "username": target_user.username,
        "role": profile.role,
        "department": profile.department
    })


# --- Admin Knowledge Graph Data Endpoint ---

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_knowledge_graph_data(request):
    """Return department and document graph data for the Enterprise Knowledge Graph visualization."""
    departments_data = []
    documents_data = []
    connections = []

    valid_departments = ['HR', 'Legal', 'Finance', 'Technical', 'General']

    for dept in valid_departments:
        dept_docs = Document.objects.filter(department=dept)
        doc_count = dept_docs.count()
        chunk_sum = dept_docs.aggregate(models.Sum('chunk_count'))['chunk_count__sum'] or 0

        departments_data.append({
            "name": dept,
            "document_count": doc_count,
            "chunk_count": chunk_sum
        })

        for d in dept_docs:
            documents_data.append({
                "id": d.id,
                "filename": d.filename,
                "department": d.department,
                "status": d.status,
                "chunk_count": d.chunk_count,
                "classification": d.classification,
                "risk_status": d.risk_status,
                "file_size": d.file_size,
                "owner": d.user.username
            })
            connections.append({
                "from_department": dept,
                "to_document": d.id
            })

    return Response({
        "departments": departments_data,
        "documents": documents_data,
        "connections": connections
    })
