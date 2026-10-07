"""Engine Postgres (SQLModel) e sessão."""

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)


def criar_tabelas() -> None:
    """Cria as tabelas que ainda não existem. Roda na subida do servidor."""
    from app import models  # noqa: F401  (registra as tabelas no metadata)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
