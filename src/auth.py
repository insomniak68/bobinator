"""Simple session-based auth using signed cookies."""

import bcrypt
from itsdangerous import URLSafeSerializer
import os

SECRET_KEY = os.environ.get("BOBINATOR_SECRET", "bobinator-dev-secret-change-me")
serializer = URLSafeSerializer(SECRET_KEY)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_session_token(provider_id: int) -> str:
    return serializer.dumps({"pid": provider_id})


def get_provider_id_from_token(token: str) -> int | None:
    try:
        data = serializer.loads(token)
        return data.get("pid")
    except Exception:
        return None
