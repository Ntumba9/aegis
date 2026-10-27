"""Synthetic internal-only metadata service. Reachable exclusively from
`lab-net` (an `internal: true` Docker network with no route out), which is
what makes the SSRF challenge reproducible without touching anything real.
"""
import os
import secrets

from fastapi import FastAPI

app = FastAPI(title="internal-metadata (lab-net only)")

# Generated at container start so each lab run has a fresh synthetic value;
# the FastAPI backend's verification path reads the *same* fixed value from
# lab-db (see lab/scripts/seed.py) rather than this process's memory.
SECRET = os.environ.get("SSRF_CHALLENGE_SECRET", "lab-ssrf-secret-change-me")


@app.get("/latest/internal-secret")
async def internal_secret():
    return {"secret": SECRET, "note": "synthetic data — this is a local training lab, not a real cloud metadata endpoint"}


@app.get("/latest/pricing")
async def pricing(discount_percent: float = 0):
    """Stands in for a third-party pricing API (API10 - Unsafe Consumption
    of APIs). It happily echoes back whatever `discount_percent` it was
    asked for, with NO validation — exactly like a real third-party
    service an attacker has found a way to influence. The bug under test
    lives in the *consumer* (lab-api's vulnerable pricing endpoint), which
    trusts this value without checking it belongs in [0, 100]."""
    return {"discount_percent": discount_percent}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
