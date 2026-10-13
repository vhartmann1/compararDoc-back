"""Tabelas (Postgres), criadas na subida do servidor (app/db.py).

Sem JSON aqui: extração e resultado de cada análise ficam no MongoDB (app/mongo.py), com o mesmo id.

Tabela que já existe não muda sozinha: mudou coluna, restrição ou índice, o banco é recriado.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import get_args

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, Text, text
from sqlmodel import Field, SQLModel

from app.schemas import Etapa, Modalidade, StatusProcessamento, StatusResultado


def _novo_id() -> str:
    return str(uuid.uuid4())


def agora_utc() -> datetime:
    return datetime.now(UTC)


def _um_de(coluna: str, valores: object) -> str:
    """Condição SQL: a coluna só aceita os valores do tipo (nulo continua valendo onde a coluna permite)."""
    return f"{coluna} IN ({', '.join(repr(valor) for valor in get_args(valores))})"


class AnaliseDB(SQLModel, table=True):
    __tablename__ = "analises"
    __table_args__ = (
        # O banco recusa valor fora da lista, venha de onde vier (código, script ou correção manual).
        CheckConstraint(_um_de("status_processamento", StatusProcessamento), name="ck_analises_status_processamento"),
        CheckConstraint(_um_de("etapa", Etapa), name="ck_analises_etapa"),
        CheckConstraint(_um_de("status_resultado", StatusResultado), name="ck_analises_status_resultado"),
        CheckConstraint(_um_de("modalidade", Modalidade), name="ck_analises_modalidade"),
        # A listagem ordena por (criado_em, id) decrescente, com ou sem filtro de usuário.
        Index("ix_analises_criado_id", text("criado_em DESC"), text("id DESC")),
        Index("ix_analises_usuario_criado_id", "usuario_id", text("criado_em DESC"), text("id DESC")),
        # Busca "contém" no nº do processo: índice comum não serve, trigramas sim.
        Index(
            "ix_analises_processo_trgm",
            "processo",
            postgresql_using="gin",
            postgresql_ops={"processo": "gin_trgm_ops"},
        ),
    )

    id: str = Field(default_factory=_novo_id, primary_key=True)
    processo: str | None = None
    modalidade: str | None = None
    usuario_id: str | None = None
    status_processamento: str = "PROCESSANDO"
    etapa: str = "RECEBIDO"
    erro: str | None = Field(default=None, sa_type=Text)
    criado_em: datetime = Field(default_factory=agora_utc, sa_type=DateTime(timezone=True))
    concluido_em: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    # preenchidas no fim, quando a análise conclui
    status_resultado: str | None = None
    total_divergencias: int | None = None
    modelo: str | None = None
    tokens_entrada: int | None = None
    tokens_saida: int | None = None
    # dinheiro é decimal exato, não ponto flutuante
    custo_usd: Decimal | None = Field(default=None, sa_type=Numeric(12, 6))


class ArquivoDB(SQLModel, table=True):
    __tablename__ = "arquivos"
    __table_args__ = (
        # Um arquivo por posição em cada análise; também serve de índice para buscar os arquivos da análise.
        Index("uq_arquivos_analise_ordem", "analise_id", "ordem", unique=True),
    )

    id: str = Field(default_factory=_novo_id, primary_key=True)
    # Apagar a análise apaga as linhas dos arquivos dela.
    analise_id: str = Field(foreign_key="analises.id", ondelete="CASCADE")
    ordem: int = 0  # posição no envio (a ordem dos arquivos importa na comparação)
    nome: str
    media_type: str
    tamanho_bytes: int
    paginas: int | None = None
    caminho: str
