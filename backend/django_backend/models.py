import json
from django.db import models
from django.contrib.auth.models import User

DEPT_CHOICES = (
    ('HR', 'HR'),
    ('Legal', 'Legal'),
    ('Finance', 'Finance'),
    ('Technical', 'Technical'),
    ('General', 'General'),
)

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('Viewer', 'Viewer'),
        ('Editor', 'Editor'),
        ('Admin', 'Admin'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Viewer')
    department = models.CharField(max_length=20, choices=DEPT_CHOICES, default='General')

    def __str__(self):
        return f"{self.user.username} - {self.role} ({self.department})"

class Document(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documents")
    filename = models.CharField(max_length=255)
    path = models.CharField(max_length=512)
    file_size = models.IntegerField()
    chunk_count = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default="ingesting") # ingesting, indexed, error
    error_message = models.TextField(null=True, blank=True)
    classification = models.CharField(max_length=100, default="General")
    risk_status = models.CharField(max_length=50, default="Clean") # Clean, Risk Detected
    risk_details = models.TextField(null=True, blank=True)
    department = models.CharField(max_length=20, choices=DEPT_CHOICES, default='General')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.filename} ({self.status}) - {self.department}"

class UserInvitation(models.Model):
    ROLE_CHOICES = (
        ('Viewer', 'Viewer'),
        ('Editor', 'Editor'),
        ('Admin', 'Admin'),
    )
    email = models.EmailField(unique=True)
    otp = models.CharField(max_length=6)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Viewer')
    department = models.CharField(max_length=20, choices=DEPT_CHOICES, default='General')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.email} - OTP: {self.otp} ({self.role} in {self.department})"

class PasswordResetOTP(models.Model):
    email = models.EmailField(unique=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Reset OTP for {self.email}"

def _mask_key(key):
    if not key or len(key) < 8:
        return ""
    return key[:4] + "*" * (len(key) - 8) + key[-4:]

def _encryption_key() -> bytes:
    """Derive a stable Fernet key from the dedicated encryption secret.

    Falls back to SECRET_KEY for backwards compatibility with existing rows.
    """
    from django.conf import settings
    import base64
    import hashlib

    secret = getattr(settings, "INTRADOC_ENCRYPTION_KEY", None) or settings.SECRET_KEY
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())


def _encrypt_value(plaintext):
    if not plaintext:
        return ""
    from cryptography.fernet import Fernet

    f = Fernet(_encryption_key())
    return f.encrypt(plaintext.encode()).decode()

def _decrypt_value(ciphertext):
    if not ciphertext:
        return ""
    from cryptography.fernet import Fernet

    f = Fernet(_encryption_key())
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        return ciphertext

class LLMConfig(models.Model):
    enforce_globally = models.BooleanField(default=False)
    provider = models.CharField(max_length=50, default='gemini')
    model = models.CharField(max_length=100, default='gemini-1.5-flash')
    temperature = models.FloatField(default=0.3)
    k = models.IntegerField(default=4)
    groq_api_key = models.CharField(max_length=512, blank=True)
    gemini_api_key = models.CharField(max_length=512, blank=True)
    openai_api_key = models.CharField(max_length=512, blank=True)

    def get_groq_key(self):
        return _decrypt_value(self.groq_api_key)

    def get_gemini_key(self):
        return _decrypt_value(self.gemini_api_key)

    def get_openai_key(self):
        return _decrypt_value(self.openai_api_key)

    def set_groq_key(self, value):
        self.groq_api_key = _encrypt_value(value)

    def set_gemini_key(self, value):
        self.gemini_api_key = _encrypt_value(value)

    def set_openai_key(self, value):
        self.openai_api_key = _encrypt_value(value)

    def masked_keys(self):
        return {
            "groq": _mask_key(self.get_groq_key()),
            "gemini": _mask_key(self.get_gemini_key()),
            "openai": _mask_key(self.get_openai_key()),
        }

    def __str__(self):
        return f"Global LLM Config (Enforced: {self.enforce_globally})"


class ChatSession(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.user.username}"

class ChatMessage(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=50) # 'user' or 'assistant'
    content = models.TextField()
    sources = models.TextField(null=True, blank=True) # JSON array of sources
    steps = models.TextField(null=True, blank=True) # JSON array of steps
    model_used = models.CharField(max_length=100, null=True, blank=True)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    estimated_cost_usd = models.FloatField(default=0.0)
    latency_ms = models.IntegerField(default=0)
    cache_hit = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role} in {self.session.id}"

    def get_sources_list(self):
        if self.sources:
            try:
                return json.loads(self.sources)
            except Exception:
                return []
        return []

    def get_steps_list(self):
        if self.steps:
            try:
                return json.loads(self.steps)
            except Exception:
                return []
        return []
