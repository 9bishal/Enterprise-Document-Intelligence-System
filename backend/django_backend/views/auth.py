import secrets
import string
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta

# DRF Imports
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

# Custom imports
from django_backend.activity import notify_activity
from django_backend.emails import send_password_reset_email
from django_backend.models import UserProfile, UserInvitation, PasswordResetOTP
from django_backend.throttles import AuthRateThrottle


def _password_error(password: str) -> str | None:
    try:
        validate_password(password)
    except ValidationError as exc:
        return " ".join(exc.messages)
    return None


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def auth_signup(request):
    """
    User registration endpoint.
    First user to sign up becomes Admin automatically (bootstrap).
    Subsequent users require a valid email+OTP invitation from admin.
    """
    username = request.data.get("username")
    password = request.data.get("password")
    email = request.data.get("email", "")
    otp = request.data.get("otp", "")

    if not username or not password:
        return Response({"detail": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    password_error = _password_error(password)
    if password_error:
        return Response({"detail": password_error}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({"detail": "Username already exists."}, status=status.HTTP_400_BAD_REQUEST)

    # First-user bootstrap: allow the first user to self-register as Admin
    if User.objects.count() == 0:
        if not getattr(settings, "ALLOW_FIRST_USER_BOOTSTRAP", True):
            return Response(
                {"detail": "Registration is closed. Ask an administrator for an invitation."},
                status=status.HTTP_403_FORBIDDEN,
            )
        user = User.objects.create_user(username=username, password=password, email=email)
        profile = UserProfile.objects.create(user=user, role='Admin', department='General')
        notify_activity("user.registered", username, "Role: `Admin` · Dept: `General`")
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
@throttle_classes([AuthRateThrottle])
def auth_login(request):
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response({"detail": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=username, password=password)
    if user is not None:
        profile, created = UserProfile.objects.get_or_create(user=user, defaults={'role': 'Viewer', 'department': 'General'})
        notify_activity("user.login", user.username, f"Role: `{profile.role}` · Dept: `{profile.department}`")
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

from rest_framework_simplejwt.exceptions import TokenError

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auth_logout(request):
    refresh_token = request.data.get("refresh")
    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            pass
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
@throttle_classes([AuthRateThrottle])
def auth_forgot_password(request):
    email = request.data.get("email")
    if not email:
        return Response({"detail": "Email is required."}, status=400)

    # Always return the same message so attackers cannot enumerate accounts.
    generic_message = "If an account exists for that email, a reset code has been sent."

    user = User.objects.filter(email=email).first()
    if not user:
        return Response({"message": generic_message})

    otp = "".join(secrets.choice(string.digits) for _ in range(6))

    PasswordResetOTP.objects.filter(email=email).delete()
    PasswordResetOTP.objects.create(email=email, otp=otp)
    notify_activity("password.reset_requested", user.username, "OTP email requested")
    
    try:
        send_password_reset_email(email, otp)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Email delivery failed for password reset %s: %s", email, e)
        return Response({"message": generic_message})
    
    return Response({"message": generic_message})

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def auth_reset_password(request):
    email = request.data.get("email")
    otp = request.data.get("otp")
    new_password = request.data.get("new_password")
    
    if not email or not otp or not new_password:
        return Response({"detail": "Email, OTP, and new password are required."}, status=400)

    password_error = _password_error(new_password)
    if password_error:
        return Response({"detail": password_error}, status=400)
        
    try:
        reset_entry = PasswordResetOTP.objects.get(email=email, otp=otp)
    except PasswordResetOTP.DoesNotExist:
        return Response({"detail": "Invalid or expired OTP."}, status=400)

    if reset_entry.created_at < timezone.now() - timedelta(minutes=15):
        reset_entry.delete()
        return Response({"detail": "OTP has expired. Request a new reset code."}, status=400)
        
    try:
        user = User.objects.get(email=email)
        user.set_password(new_password)
        user.save()
        reset_entry.delete()
        reset_user = User.objects.filter(email=email).first()
        notify_activity("password.reset_completed", reset_user.username if reset_user else "", "Password changed")
        return Response({"message": "Password reset successfully."})
    except User.DoesNotExist:
        return Response({"detail": "Invalid or expired OTP."}, status=400)
