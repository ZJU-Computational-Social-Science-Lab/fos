from __future__ import annotations

import asyncio

from sqlalchemy import text

from fos.backend.core.database import engine


async def migrate() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info('users')"))
        columns = {row[1] for row in result.fetchall()}
        if "config" not in columns:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN config JSON DEFAULT '{}'")
            )
            print("Added 'config' column to users table")
        else:
            print("'config' column already exists in users table")


async def _main() -> None:
    await migrate()


if __name__ == "__main__":
    asyncio.run(_main())
