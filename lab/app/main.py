from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel

from app.auth import SYNTHETIC_USERS, issue_token
from app.routers import (
    bfla,
    bola,
    bopla,
    broken_auth,
    business_flows,
    inventory,
    misconfiguration,
    resource_consumption,
    ssrf,
    unsafe_consumption,
)

app = FastAPI(
    title="AEGIS Labs - OWASP API Top 10 Target",
    description=(
        "Intentionally vulnerable lab API. Bind to localhost only. "
        "Authorized testing scope: this instance, on your own machine, only."
    ),
)

auth_router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@auth_router.post("/auth/login")
async def login(body: LoginRequest):
    user = SYNTHETIC_USERS.get(body.username)
    if user is None or user["password"] != body.password:
        raise HTTPException(status_code=401, detail="Invalid synthetic credentials")
    return {"access_token": issue_token(body.username), "token_type": "bearer"}


app.include_router(auth_router)
app.include_router(bola.router)
app.include_router(ssrf.router)
app.include_router(broken_auth.router)
app.include_router(bopla.router)
app.include_router(resource_consumption.router)
app.include_router(bfla.router)
app.include_router(business_flows.router)
app.include_router(misconfiguration.router)
app.include_router(inventory.router)
app.include_router(unsafe_consumption.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "mode": "lab"}
