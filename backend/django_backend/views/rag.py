import uuid
import json
import time

# DRF Imports
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.http import StreamingHttpResponse

# Custom imports
from django_backend.models import Document, ChatSession, ChatMessage, LLMConfig
from django_backend.permissions import IsViewerOrAbove
from django_backend.serializers import ChatSessionSerializer, ChatMessageSerializer
from app.rag_graph import run_rag_pipeline, run_rag_stream


def _resolve_rag_scope(request, config_payload):
    """Shared auth + department scoping + model config for query endpoints."""
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

    if admin_all:
        user_docs = Document.objects.filter(status="indexed")
    elif is_admin:
        user_docs = Document.objects.filter(department=target_dept, status="indexed")
    else:
        user_docs = Document.objects.filter(department=user_department, status="indexed")
    user_doc_ids = [str(d.id) for d in user_docs]

    llm_config = LLMConfig.objects.first()
    if llm_config:
        api_keys = {
            "gemini": llm_config.get_gemini_key(),
            "openai": llm_config.get_openai_key(),
            "groq": llm_config.get_groq_key()
        }
        if llm_config.enforce_globally:
            model_config = {
                "provider": llm_config.provider,
                "model": llm_config.model,
                "temperature": llm_config.temperature,
                "k": llm_config.k
            }
        else:
            model_config = {
                "provider": config_payload.get("provider", llm_config.provider),
                "model": config_payload.get("model", llm_config.model),
                "temperature": config_payload.get("temperature", llm_config.temperature),
                "k": config_payload.get("k", llm_config.k)
            }
    else:
        api_keys = {}
        model_config = {
            "provider": config_payload.get("provider", "groq"),
            "model": config_payload.get("model", "groq/compound-mini"),
            "temperature": config_payload.get("temperature", 0.3),
            "k": config_payload.get("k", 4)
        }
    return api_keys, model_config, user_doc_ids, target_dept, admin_all

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

    # Always load admin-saved API keys from the database as the
    # authoritative source.  Users never supply their own keys.
    llm_config = LLMConfig.objects.first()
    if llm_config:
        api_keys = {
            "gemini": llm_config.get_gemini_key(),
            "openai": llm_config.get_openai_key(),
            "groq": llm_config.get_groq_key()
        }
        if llm_config.enforce_globally:
            # Admin enforced: use DB config entirely, ignore frontend payload
            model_config = {
                "provider": llm_config.provider,
                "model": llm_config.model,
                "temperature": llm_config.temperature,
                "k": llm_config.k
            }
        else:
            # Not enforced: use admin DB config as defaults, allow user
            # overrides for provider/model/temperature/k only
            model_config = {
                "provider": config_payload.get("provider", llm_config.provider),
                "model": config_payload.get("model", llm_config.model),
                "temperature": config_payload.get("temperature", llm_config.temperature),
                "k": config_payload.get("k", llm_config.k)
            }
    else:
        # No LLMConfig exists at all — use frontend payload with safe defaults
        model_config = {
            "provider": config_payload.get("provider", "groq"),
            "model": config_payload.get("model", "groq/compound-mini"),
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
        steps=json.dumps(result["steps"]),
        model_used=result.get("model_used", ""),
        input_tokens=result.get("input_tokens", 0),
        output_tokens=result.get("output_tokens", 0),
        estimated_cost_usd=result.get("estimated_cost_usd", 0.0),
        latency_ms=result.get("latency_ms", 0),
        cache_hit=result.get("cache_hit", False),
    )

    return Response({
        "id": assistant_msg_id,
        "role": "assistant",
        "content": result["generation"],
        "sources": result["documents"],
        "steps": result["steps"],
        "success": result["success"],
        "cache_hit": result.get("cache_hit", False),
        "model_used": result.get("model_used", ""),
        "estimated_cost_usd": result.get("estimated_cost_usd", 0.0),
        "latency_ms": result.get("latency_ms", 0),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "evaluation": result.get("evaluation"),
    })


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@api_view(['POST'])
@permission_classes([IsViewerOrAbove])
def query_rag_stream(request):
    """Streaming twin of query_rag (SSE: token/citations/done events).

    Same auth, scoping and persistence as query_rag — only generation streams,
    so the UI renders the first point while the rest is still generating.
    """
    session_id = request.data.get("session_id")
    question = request.data.get("question")
    config_payload = request.data.get("config", {})

    if not session_id or not question:
        return Response({"detail": "session_id and question are required."},
                        status=status.HTTP_400_BAD_REQUEST)

    session = ChatSession.objects.filter(user=request.user, id=session_id).first()
    if not session:
        return Response({"detail": "Session not found or unauthorized."},
                        status=status.HTTP_404_NOT_FOUND)

    user_msg_id = str(uuid.uuid4())
    ChatMessage.objects.create(
        id=user_msg_id, session=session, role="user", content=question
    )

    api_keys, model_config, user_doc_ids, target_dept, admin_all = _resolve_rag_scope(
        request, config_payload
    )
    start = time.time()

    def event_stream():
        full_answer = ""
        documents = []
        model_used = ""
        in_tok, out_tok, cost = 0, 0, 0.0
        first_token_ms = None
        try:
            for evt in run_rag_stream(
                question, api_keys, model_config,
                user_doc_ids=user_doc_ids, department=target_dept,
                admin_all=admin_all,
            ):
                etype = evt.get("type")
                if etype == "token" and evt.get("delta"):
                    if first_token_ms is None:
                        first_token_ms = int((time.time() - start) * 1000)
                    full_answer += evt["delta"]
                    yield _sse("token", {"delta": evt["delta"]})
                elif etype == "citations":
                    documents = evt.get("citations", []) or evt.get("documents", [])
                    yield _sse("citations", {"citations": documents})
                elif etype == "done":
                    model_used = evt.get("model_used", "")
                    documents = evt.get("documents", documents)
                    latency_ms = evt.get("latency_ms",
                                         int((time.time() - start) * 1000))
                    in_tok = evt.get("input_tokens", 0)
                    out_tok = evt.get("output_tokens", 0)
                    cost = evt.get("estimated_cost_usd", 0.0)
                    cache_hit = evt.get("cache_hit", False)
                    assistant_msg_id = str(uuid.uuid4())
                    try:
                        ChatMessage.objects.create(
                            id=assistant_msg_id, session=session, role="assistant",
                            content=evt.get("full_answer", full_answer),
                            sources=json.dumps(documents),
                            steps=json.dumps(["retrieve", "generate"]),
                            model_used=model_used, latency_ms=latency_ms,
                            input_tokens=in_tok, output_tokens=out_tok,
                            estimated_cost_usd=cost, cache_hit=cache_hit,
                        )
                    except Exception as e:
                        print(f"[stream] persist failed: {e}")
                    yield _sse("done", {
                        "id": assistant_msg_id, "model_used": model_used,
                        "latency_ms": latency_ms, "ttft_ms": first_token_ms,
                        "sources": documents,
                        "steps": ["retrieve", "generate"], "success": True,
                        "cache_hit": cache_hit,
                        "input_tokens": in_tok, "output_tokens": out_tok,
                        "estimated_cost_usd": cost,
                    })
        except Exception as e:
            yield _sse("token", {"delta": f"An error occurred: {str(e)}"})
            yield _sse("done", {"model_used": "error", "success": False,
                                "sources": [], "steps": ["retrieve", "error"]})

    response = StreamingHttpResponse(event_stream(),
                                     content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
