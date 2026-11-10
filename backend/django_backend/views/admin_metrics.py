from django.db import models
from django.contrib.auth.models import User

# DRF Imports
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

# Custom imports
from django_backend.models import Document, ChatSession, ChatMessage, UserProfile
from django_backend.permissions import IsAdminUser

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_metrics(request):
    # Counts (documents scoped to actually-indexed for retrieval truthfulness)
    total_users = User.objects.count()
    indexed_docs = Document.objects.filter(status="indexed")
    total_documents = indexed_docs.count()
    total_chunks = indexed_docs.aggregate(models.Sum('chunk_count'))['chunk_count__sum'] or 0
    total_file_size = indexed_docs.aggregate(models.Sum('file_size'))['file_size__sum'] or 0
    total_sessions = ChatSession.objects.count()

    # Real request metrics from the assistant-message ledger (classic + streamed
    # queries both persist input/output tokens, cost, latency and cache hits).
    assistant_msgs = ChatMessage.objects.filter(role="assistant")
    token_agg = assistant_msgs.aggregate(
        total_in=models.Sum('input_tokens'), total_out=models.Sum('output_tokens'),
    )
    total_input_tokens = token_agg['total_in'] or 0
    total_output_tokens = token_agg['total_out'] or 0
    total_cost = assistant_msgs.aggregate(total=models.Sum('estimated_cost_usd'))['total'] or 0.0
    total_responses = assistant_msgs.count()
    cache_hits = assistant_msgs.filter(cache_hit=True).count()
    avg_latency_agg = assistant_msgs.aggregate(avg=models.Avg('latency_ms'))['avg'] or 0
    error_responses = assistant_msgs.filter(models.Q(model_used="error") | models.Q(content__icontains="an error occurred")).count()

    latency_values = sorted(
        v for v in assistant_msgs.exclude(latency_ms=0).values_list('latency_ms', flat=True)
        if v is not None
    )

    def _percentile(values, fraction):
        if not values:
            return 0
        position = (len(values) - 1) * fraction
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        if lower == upper:
            return values[lower]
        return values[lower] + (values[upper] - values[lower]) * (position - lower)

    p50_latency = round(_percentile(latency_values, 0.50))
    p95_latency = round(_percentile(latency_values, 0.95))
    p99_latency = round(_percentile(latency_values, 0.99))
    cache_hit_rate = round(cache_hits / total_responses, 4) if total_responses else 0.0
    
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

    # Indexed documents list for the vector-database panel
    indexed_documents_list = [{
        "id": d.id,
        "filename": d.filename,
        "owner": d.user.username if d.user_id else "Unknown",
        "department": d.department,
        "status": d.status,
        "chunk_count": d.chunk_count,
        "file_size": d.file_size,
    } for d in indexed_docs.order_by("-created_at")]

    return Response({
        "metrics": {
            "total_users": total_users,
            "total_documents": total_documents,
            "total_chunks": total_chunks,
            "total_file_size": total_file_size,
            "total_sessions": total_sessions,
            "estimated_tokens": total_input_tokens + total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "total_cost": round(float(total_cost), 6),
            "cache_hits": cache_hits,
            "cache_hit_rate": cache_hit_rate,
            "total_responses": total_responses,
            "avg_latency": round(float(avg_latency_agg)),
            "p50_latency": p50_latency,
            "p95_latency": p95_latency,
            "p99_latency": p99_latency,
            "error_responses": error_responses,
        },
        "users": users_list,
        "classification_distribution": class_dist_map,
        "flagged_documents": flagged_docs_list,
        "indexed_documents": indexed_documents_list,
        "recent_activities": recent_activity_list
    })
