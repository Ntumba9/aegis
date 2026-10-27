"""Seeds the lab database with synthetic users' projects and the flags/
secrets the backend's verify() functions check submissions against.
Safe to re-run — it is idempotent (used by reset.sh)."""
import asyncio
import os
import secrets

import asyncpg

LAB_DATABASE_URL = os.environ.get(
    "LAB_DATABASE_URL", "postgresql://lab:lab_dev_only@localhost:5433/aegis_lab"
)
SSRF_SECRET = os.environ.get("SSRF_CHALLENGE_SECRET", "lab-ssrf-secret-change-me")
API8_DEBUG_SECRET = "AEGIS{internal-debug-secret-leaked}"  # must match lab/app/routers/misconfiguration.py


def _flag() -> str:
    return f"AEGIS{{{secrets.token_hex(8)}}}"


async def main():
    with open(os.path.join(os.path.dirname(__file__), "init_schema.sql")) as f:
        schema_sql = f.read()

    conn = await asyncpg.connect(LAB_DATABASE_URL)
    try:
        await conn.execute(schema_sql)
        await conn.execute(
            "truncate bola_victim_projects, bola_projects, ssrf_internal_secrets, "
            "challenge_flags, lab_sessions, lab_users, sensitive_records, "
            "wallets, coupon_redemptions restart identity"
        )
        await conn.execute("alter sequence lab_sessions_vuln_seq restart with 1")

        # --- API1 BOLA ---
        alice_flag = _flag()
        alice_project = await conn.fetchrow(
            "insert into bola_projects (owner_id, name, description) values (1, $1, $2) returning id",
            "Alice's Confidential Roadmap",
            alice_flag,
        )
        await conn.execute(
            "insert into bola_projects (owner_id, name, description) values (2, 'Bob''s Public Notes', 'nothing sensitive here')"
        )
        await conn.execute(
            "insert into bola_victim_projects (challenge_id, project_id, flag) values ($1, $2, $3)",
            "api1-bola-project-files",
            alice_project["id"],
            alice_flag,
        )

        # --- API7 SSRF ---
        await conn.execute(
            "insert into ssrf_internal_secrets (challenge_id, secret) values ($1, $2)",
            "api7-ssrf-url-preview",
            SSRF_SECRET,
        )

        # --- lab_users (roles for API3 / API5 / API9) ---
        await conn.execute(
            "insert into lab_users (id, username, display_name, role) values "
            "(1, 'alice', 'Alice', 'user'), "
            "(2, 'bob', 'Bob', 'user'), "
            "(4, 'dave', 'Dave', 'user'), "
            "(5, 'erin', 'Erin', 'admin')"
        )

        # --- API2 Broken Authentication: erin's pre-existing predictable session ---
        api2_flag = _flag()
        await conn.execute(
            "insert into challenge_flags (challenge_id, flag) values ($1, $2)",
            "api2-broken-auth-predictable-session",
            api2_flag,
        )
        await conn.execute("select nextval('lab_sessions_vuln_seq')")  # consumes id=1
        await conn.execute(
            "insert into lab_sessions (token, username, mode) values ('sess-000001', 'erin', 'vulnerable')"
        )

        # --- API3 BOPLA ---
        await conn.execute(
            "insert into challenge_flags (challenge_id, flag) values ($1, $2)",
            "api3-bopla-role-escalation",
            _flag(),
        )

        # --- API4 Resource Consumption: 500 harmless rows + 1 sensitive row ---
        api4_flag = _flag()
        await conn.executemany(
            "insert into sensitive_records (payload) values ($1)",
            [(f"routine record #{i}",) for i in range(1, 501)],
        )
        await conn.execute("insert into sensitive_records (payload) values ($1)", api4_flag)
        await conn.execute(
            "insert into challenge_flags (challenge_id, flag) values ($1, $2)",
            "api4-resource-consumption-pagination",
            api4_flag,
        )

        # --- API5 BFLA ---
        await conn.execute(
            "insert into challenge_flags (challenge_id, flag) values ($1, $2)",
            "api5-bfla-admin-broadcast",
            _flag(),
        )

        # --- API6 Sensitive Business Flows ---
        await conn.execute(
            "insert into challenge_flags (challenge_id, flag) values ($1, $2)",
            "api6-sensitive-flows-coupon-replay",
            _flag(),
        )

        # --- API8 Security Misconfiguration ---
        await conn.execute(
            "insert into challenge_flags (challenge_id, flag) values ($1, $2)",
            "api8-misconfiguration-verbose-errors",
            API8_DEBUG_SECRET,
        )

        # --- API9 Improper Inventory Management ---
        await conn.execute(
            "insert into challenge_flags (challenge_id, flag) values ($1, $2)",
            "api9-inventory-shadow-v1-endpoint",
            _flag(),
        )

        # --- API10 Unsafe Consumption of APIs ---
        await conn.execute(
            "insert into challenge_flags (challenge_id, flag) values ($1, $2)",
            "api10-unsafe-consumption-pricing",
            _flag(),
        )
    finally:
        await conn.close()

    print("Lab seeded. 10 challenges ready — recover each flag to complete it.")


if __name__ == "__main__":
    asyncio.run(main())
