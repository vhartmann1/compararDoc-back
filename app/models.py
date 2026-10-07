"""Tabelas (Postgres), criadas na subida do servidor (app/db.py).

Sem JSON aqui: extração e resultado de cada análise ficam no MongoDB (app/mongo.py), com o mesmo id.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Text
from sqlmodel import Field, SQLModel


def _novo_id() -> str:
    return str(uuid.uuid4())


def agora_utc() -> datetime:
    return datetime.now(UTC)


class AnaliseDB(SQLModel, table=True):
    __tablename__ = "analises"

    id: str = Field(default_factory=_novo_id, primary_key=True)
    processo: str | None = None
    modalidade: str | None = None  # propria | conta_e_ordem | encomenda
    usuario_id: str | None = Field(default=None, index=True)
    status_processamento: str = "PROCESSANDO"
    etapa: str = "RECEBIDO"
    erro: str | None = Field(default=None, sa_type=Text)
    criado_em: datetime = Field(default_factory=agora_utc, index=True, sa_type=DateTime(timezone=True))
    concluido_em: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    # preenchidas no fim, quando a análise conclui
    status_resultado: str | None = None  # OK | DIVERGENTE | INCOMPLETO
    total_divergencias: int | None = None
    modelo: str | None = None
    tokens_entrada: int | None = None
    tokens_saida: int | None = None
    custo_usd: float | None = None


class ArquivoDB(SQLModel, table=True):
    __tablename__ = "arquivos"

    id: str = Field(default_factory=_novo_id, primary_key=True)
    analise_id: str = Field(foreign_key="analises.id", index=True)
    ordem: int = 0  # posição no envio (a ordem dos arquivos importa na comparação)
    nome: str
    media_type: str
    tamanho_bytes: int
    paginas: int | None = None
    caminho: str
