"""Syncs app/challenges/*.py METADATA into the public `challenges` table.
Run after every new migration or new challenge module:
    python backend/scripts/seed_challenges.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncpg

from app.challenges.registry import all_metadata
from app.core.config import settings


async def main():
    conn = await asyncpg.connect(settings.database_url)
    try:
        for m in all_metadata():
            await conn.execute(
                """
                insert into challenges (
                    id, owasp_category, title, difficulty, summary,
                    learning_objectives, prerequisites, authorized_scope,
                    required_services, hints, remediation_markdown, points
                ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                on conflict (id) do update set
                    owasp_category = excluded.owasp_category,
                    title = excluded.title,
                    difficulty = excluded.difficulty,
                    summary = excluded.summary,
                    learning_objectives = excluded.learning_objectives,
                    prerequisites = excluded.prerequisites,
                    authorized_scope = excluded.authorized_scope,
                    required_services = excluded.required_services,
                    hints = excluded.hints,
                    remediation_markdown = excluded.remediation_markdown,
                    points = excluded.points
                """,
                m.id, m.owasp_category, m.title, m.difficulty, m.summary,
                m.learning_objectives, m.prerequisites, m.authorized_scope,
                m.required_services, m.hints, m.remediation_markdown, m.points,
            )
        print(f"Synced {len(all_metadata())} challenges.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
