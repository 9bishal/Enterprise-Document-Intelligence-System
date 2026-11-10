import logging
import secrets
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from datetime import timedelta

# DRF Imports
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

# Custom imports
from django_backend.emails import send_invitation_email
from django_backend.models import UserProfile, UserInvitation
from django_backend.permissions import IsAdminUser

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

    try:
        validate_email(email)
    except ValidationError:
        return Response({"detail": "Enter a valid email address."}, status=status.HTTP_400_BAD_REQUEST)

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
    otp = "".join(secrets.choice("0123456789") for _ in range(6))
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

    try:
        send_invitation_email(email, otp, role, department)
        return Response({
            "detail": f"Invitation sent successfully to {email}.",
            "role": role,
            "department": department
        })
    except Exception as e:
        logging.getLogger(__name__).error("Email delivery failed for invitation %s: %s", email, e)
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

@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAdminUser])
def admin_update_user(request, user_id):
    """Update a user's role and/or department (PATCH), or delete the user
    with all their documents, vectors, files and sessions (DELETE)."""
    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        return _delete_user(request, target_user)

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


def _delete_user(request, target_user):
    """Delete a user and clean up everything they own: vector chunks, files,
    documents, sessions (DB cascades profile/sessions). Guards self-delete
    and deleting the last admin."""
    import os as _os

    if target_user.id == request.user.id:
        return Response({"detail": "You cannot delete your own account."},
                        status=status.HTTP_400_BAD_REQUEST)

    from django.contrib.auth.models import User as _User
    from django_backend.models import Document as _Document, UserProfile as _UserProfile
    admin_ids = set(_UserProfile.objects.filter(role='Admin').values_list('user_id', flat=True))
    if target_user.id in admin_ids and len(admin_ids) <= 1:
        return Response({"detail": "You cannot delete the last admin account."},
                        status=status.HTTP_400_BAD_REQUEST)

    username = target_user.username
    deleted_id = target_user.id
    removed_docs = 0
    for doc in _Document.objects.filter(user=target_user):
        try:
            from app.vector_store import delete_document_from_index
            delete_document_from_index(str(doc.id), department=doc.department)
        except Exception as e:
            print(f"[admin] vector cleanup failed for doc {doc.id}: {e}")
        try:
            if doc.path and _os.path.exists(doc.path):
                _os.remove(doc.path)
        except Exception as e:
            print(f"[admin] file cleanup failed for doc {doc.id}: {e}")
        removed_docs += 1

    try:
        from django_backend.cache.semantic_cache import SemanticResponseCache
        SemanticResponseCache().flush_type(reason="user_deleted")
    except Exception as e:
        print(f"[admin] semantic cache flush failed: {e}")

    target_user.delete()
    return Response({
        "detail": f"User '{username}' and {removed_docs} document(s) deleted successfully.",
        "id": deleted_id,
    })
