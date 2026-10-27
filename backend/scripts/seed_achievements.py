"""Seeds the public `achievements` catalog. Run after migrations:
    python backend/scripts/seed_achievements.py
Achievement ids here must match the constants in app/services/achievements.py.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncpg

from app.core.config import settings

ACHIEVEMENTS = [
    ("first-blood", "First Blood", "Completed your first challenge.", "flag"),
    ("api-top-10-graduate", "API Top 10 Graduate", "Completed all ten OWASP API Security Top 10 challenges.", "trophy"),
    ("red-team-rookie", "Red Team Rookie", "Started your first team session in Attack mode.", "sword"),
]


async def main():
    conn = await asyncpg.connect(settings.database_url)
    try:
        for achievement_id, title, description, icon in ACHIEVEMENTS:
            await conn.execute(
                "insert into achievements (id, title, description, icon) values ($1, $2, $3, $4) "
                "on conflict (id) do update set title = excluded.title, "
                "description = excluded.description, icon = excluded.icon",
                achievement_id,
                title,
                description,
                icon,
            )
        print(f"Synced {len(ACHIEVEMENTS)} achievements.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
