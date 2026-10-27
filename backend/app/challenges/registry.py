"""Central registry mapping challenge id -> module. Adding a challenge is:
1. write `app/challenges/<id>.py` implementing METADATA + verify()
2. register it below
3. run scripts/seed_challenges.py to sync METADATA into the `challenges` table
"""
from app.challenges import (
    api1_bola,
    api2_broken_auth,
    api3_bopla,
    api4_resource_consumption,
    api5_bfla,
    api6_business_flows,
    api7_ssrf,
    api8_misconfiguration,
    api9_inventory,
    api10_unsafe_consumption,
)

_MODULES = [
    api1_bola,
    api2_broken_auth,
    api3_bopla,
    api4_resource_consumption,
    api5_bfla,
    api6_business_flows,
    api7_ssrf,
    api8_misconfiguration,
    api9_inventory,
    api10_unsafe_consumption,
]

REGISTRY = {mod.METADATA.id: mod for mod in _MODULES}


def get_challenge_module(challenge_id: str):
    return REGISTRY.get(challenge_id)


def all_metadata():
    return [mod.METADATA for mod in REGISTRY.values()]
