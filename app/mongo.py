"""MongoDB: documentos de cada análise (extração e resultado), com o mesmo id do Postgres."""

from pymongo import MongoClient

from app.config import settings
from app.models import agora_utc

_cliente: MongoClient = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=3000, tz_aware=True)
_colecao = _cliente[settings.mongo_db]["analises"]


def verificar() -> None:
    """Levanta erro se o MongoDB não responder. Roda na subida do servidor."""
    _cliente.admin.command("ping")


def salvar(analise_id: str, resultado: dict, extracoes: dict) -> None:
    _colecao.replace_one(
        {"_id": analise_id},
        {"_id": analise_id, "resultado": resultado, "extracoes": extracoes, "gravado_em": agora_utc()},
        upsert=True,
    )


def ler(analise_id: str) -> dict | None:
    return _colecao.find_one({"_id": analise_id})


def apagar(analise_id: str) -> None:
    _colecao.delete_one({"_id": analise_id})
