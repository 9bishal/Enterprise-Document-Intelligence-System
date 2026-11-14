# Creates loadtest users and pre-mints JWT tokens (bypasses the per-IP auth
# rate throttle, which would otherwise 429 all logins from one machine).
#
# Run once via:
#   cd backend && ../loadtests/.venv/bin/python manage.py shell < ../loadtests/create_test_users.py
#   (adjust the python path to wherever your backend env lives)
#
# Output: loadtests/tokens.json with {"loaduser0": {"access": ..., "refresh": ...}, ...}
import json
import os

from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from django_backend.models import UserProfile

NUM_USERS = int(os.getenv("LOADTEST_USERS", "70"))
PREFIX = os.getenv("LOADTEST_USER_PREFIX", "loaduser")
PASSWORD = os.getenv("LOADTEST_PASSWORD", "loadtest-Pass1")

OUT_FILE = os.getenv(
    "LOADTEST_TOKENS_FILE",
    os.path.join(os.getcwd(), "..", "loadtests", "tokens.json"),
)
OUT_FILE = os.path.normpath(OUT_FILE)

created = 0
tokens = {}
for i in range(NUM_USERS):
    username = f"{PREFIX}{i}"
    user, was_created = User.objects.get_or_create(username=username)
    if was_created:
        user.set_password(PASSWORD)
        user.save()
        created += 1
    UserProfile.objects.get_or_create(
        user=user, defaults={"role": "Viewer", "department": "General"}
    )
    refresh = RefreshToken.for_user(user)
    tokens[username] = {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "password": PASSWORD,
    }

with open(OUT_FILE, "w") as f:
    json.dump(tokens, f)

print(f"Created {created} new users ({NUM_USERS - created} already existed).")
print(f"Login credentials: {PREFIX}<0-{NUM_USERS - 1}> / {PASSWORD}")
print(f"Wrote {NUM_USERS} pre-minted JWT tokens to {OUT_FILE}")
