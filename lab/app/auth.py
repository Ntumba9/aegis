"""Minimal auth for the lab. Synthetic users/passwords only — this issuer
and secret are never shared with the production AEGIS platform."""
import os
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

LAB_JWT_SECRET = os.environ.get("LAB_JWT_SECRET", "lab-dev-secret-not-for-reuse")
bearer_scheme = HTTPBearer(auto_error=True)

# Synthetic, documented-as-insecure lab credentials. Never reused anywhere else.
SYNTHETIC_USERS = {
    "alice": {"user_id": 1, "password": "lab-password-alice"},
    "bob": {"user_id": 2, "password": "lab-password-bob"},
    "dave": {"user_id": 4, "password": "lab-password-dave"},
    "erin": {"user_id": 5, "password": "lab-password-erin"},   # seeded as the admin in lab_users
}


def issue_token(username: str) -> str:
    user = SYNTHETIC_USERS[username]
    payload = {"sub": username, "user_id": user["user_id"], "iat": int(time.time())}
    return jwt.encode(payload, LAB_JWT_SECRET, algorithm="HS256")


def get_current_lab_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, LAB_JWT_SECRET, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid lab token") from exc
    return payload
