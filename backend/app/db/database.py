from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from ..config import settings


def _async_database_url(database_url: str) -> URL:
    try:
        url = make_url(database_url.strip())
    except ArgumentError as error:
        raise ValueError(
            "DATABASE_URL must contain only a valid PostgreSQL connection URL. "
            "In Render, copy the database's Internal Database URL into the "
            "environment variable value without adding 'DATABASE_URL=' or quotes."
        ) from error

    if url.drivername not in {
        "postgres",
        "postgresql",
        "postgresql+asyncpg",
        "postgresql+psycopg",
        "postgresql+psycopg2",
    }:
        raise ValueError("DATABASE_URL must use PostgreSQL.")

    return url.set(drivername="postgresql+asyncpg")


engine = create_async_engine(
    _async_database_url(settings.DATABASE_URL),
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session