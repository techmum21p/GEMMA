from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
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
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
