"""Engine SQLite (SQLModel) e sessão."""

from collections.abc import Iterator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings


def _garantir_pasta_sqlite(url: str) -> None:
    if url.startswith("sqlite:///"):
        caminho = url.removeprefix("sqlite:///")
        if caminho and caminho != ":memory:":
            Path(caminho).parent.mkdir(parents=True, exist_ok=True)


_garantir_pasta_sqlite(settings.database_url)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)


def criar_tabelas() -> None:
    from app import models  # noqa: F401  (registra as tabelas no metadata)

    SQLModel.metadata.create_all(engine)
    _adicionar_colunas_novas()


def _adicionar_colunas_novas() -> None:
    """create_all não altera tabelas existentes; adiciona colunas que surgiram depois."""
    with engine.begin() as conn:
        colunas = {linha[1] for linha in conn.exec_driver_sql("PRAGMA table_info(analises)")}
        if "modalidade" not in colunas:
            conn.exec_driver_sql("ALTER TABLE analises ADD COLUMN modalidade VARCHAR")


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
