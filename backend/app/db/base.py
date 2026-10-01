from datetime import datetime

from sqlalchemy import BigInteger, DateTime, MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Classe declarativa comum a todos os modelos ORM."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class GoldDatabaseSync(Base):
    """Registra qual arquivo Gold foi aplicado ao banco operacional."""

    __tablename__ = "gold_database_sync"

    dataset_name: Mapped[str] = mapped_column(String(80), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )
    source_size_bytes: Mapped[int | None] = mapped_column(BigInteger(), nullable=True)
    source_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
