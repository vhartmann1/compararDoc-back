"""Engine Postgres (SQLModel) e sessão."""

from collections.abc import Iterator

from sqlalchemy import Engine, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)


def criar_tabelas(em: Engine = engine) -> None:
    """Cria as tabelas que ainda não existem. Roda na subida do servidor.

    Só cria o que falta: tabela que já existe não é alterada.
    """
    from app import models  # noqa: F401  (registra as tabelas no metadata)

    if em.dialect.name == "postgresql":
        with em.begin() as con:
            # O índice de busca por nº do processo (models.py) depende desta extensão.
            con.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    SQLModel.metadata.create_all(em)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
