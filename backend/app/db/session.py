from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()


def enable_sqlite_foreign_keys(async_engine: AsyncEngine) -> None:
    """Habilita chaves estrangeiras em cada conexão SQLite."""

    @event.listens_for(async_engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: object, connection_record: object) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-65536")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


engine = create_async_engine(settings.database_url, echo=settings.environment == "local")
enable_sqlite_foreign_keys(engine)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Fornece uma sessão assíncrona por requisição."""

    async with AsyncSessionLocal() as session:
        yield session
