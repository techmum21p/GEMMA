"""
Async SQLite database engine, session factory, and initialisation helpers.

SQLite is chosen for GEMMA because the app is designed to run entirely on a
single laptop or health worker's device — no network database required.
aiosqlite provides a non-blocking async interface compatible with FastAPI's
async route handlers.

init_db() is called once at startup (via the FastAPI lifespan context) and
uses SQLAlchemy's create_all to create tables.  It also runs ALTER TABLE
statements to add columns introduced after the initial schema so existing
databases are migrated without data loss.

get_db() is a FastAPI dependency that yields a session per request and
ensures the session is closed afterwards regardless of success or failure.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """
    Create all ORM-defined tables and apply incremental column migrations.

    Safe to call on every startup — create_all is a no-op for existing tables,
    and ALTER TABLE statements are wrapped in try/except so already-present
    columns are silently skipped.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add new columns to existing tables without dropping data
        new_columns = [
            ("patients", "address",       "VARCHAR"),
            ("patients", "bp",            "VARCHAR(20)"),
            ("patients", "temperature",   "VARCHAR(10)"),
            ("patients", "triage_reason", "TEXT"),
            ("patients", "heart_rate",    "VARCHAR(10)"),
            ("patients", "spo2",          "VARCHAR(10)"),
        ]
        for table, col, col_type in new_columns:
            try:
                await conn.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
                )
            except Exception:
                pass  # column already exists


async def get_db():
    """FastAPI dependency: yield an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
