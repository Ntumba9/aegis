import os

import asyncpg

LAB_DATABASE_URL = os.environ.get(
    "LAB_DATABASE_URL", "postgresql://lab:lab_dev_only@lab-db:5432/aegis_lab"
)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(LAB_DATABASE_URL, min_size=1, max_size=5)
    return _pool
