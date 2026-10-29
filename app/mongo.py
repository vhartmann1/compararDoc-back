"""MongoDB: o que é aninhado demais para virar tabela. Duas coleções, no espelho das tabelas do Postgres.

    resultados   um documento por análise (_id = analises.id)
                 status, documentos, comparacoes, itens, divergencias, avisos — o que a API devolve
                 em `Analise.resultado` — e gravado_em

    extracoes    um documento por arquivo (_id = arquivos.id)
                 analise_id, documentos (o que foi lido do arquivo) e gravado_em

Ficam separadas porque são lidas em momentos diferentes: o resultado a cada abertura de análise;
a extração só para auditoria e para medir o acerto da leitura. Dentro de cada documento o conteúdo
fica junto, porque é sempre lido inteiro.
"""

from datetime import datetime
from typing import Any

from pymongo import MongoClient, ReplaceOne
from pymongo.collection import Collection

from app.config import settings
from app.models import agora_utc

# Tempo máximo de cada operação (conexão, envio e resposta), para nenhuma requisição ficar presa.
TEMPO_LIMITE_MS = 10_000

Documento = dict[str, Any]

# Um cliente por processo: ele mantém o conjunto de conexões e é seguro entre threads.
_cliente: MongoClient[Documento] = MongoClient(
    settings.mongo_url,
    appname="comparardocs-backend",
    serverSelectionTimeoutMS=3000,
    timeoutMS=TEMPO_LIMITE_MS,
    # Só confirma a escrita depois de gravada em disco pela maioria dos nós (em nó único, por ele).
    w="majority",
    journal=True,
    tz_aware=True,
)
resultados: Collection[Documento] = _cliente[settings.mongo_db]["resultados"]
extracoes: Collection[Documento] = _cliente[settings.mongo_db]["extracoes"]


def verificar() -> None:
    """Levanta erro se o MongoDB não responder. Roda na subida do servidor."""
    _cliente.admin.command("ping")


def fechar() -> None:
    """Devolve as conexões. Roda na descida do servidor."""
    _cliente.close()


def montar_resultado(analise_id: str, resultado: Documento, gravado_em: datetime) -> Documento:
    return {"_id": analise_id, **resultado, "gravado_em": gravado_em}


def montar_extracoes(analise_id: str, por_arquivo: dict[str, Documento], gravado_em: datetime) -> list[Documento]:
    """`por_arquivo` é arquivo_id -> extração; cada arquivo vira um documento, com o id dele."""
    return [
        {
            "_id": arquivo_id,
            "analise_id": analise_id,
            "documentos": extracao.get("documentos", []),
            "escaneado": extracao.get("escaneado"),
            "gravado_em": gravado_em,
        }
        for arquivo_id, extracao in por_arquivo.items()
    ]


def salvar(analise_id: str, resultado: Documento, por_arquivo: dict[str, Documento]) -> None:
    """Grava (ou regrava) o que a análise produziu. Repetir a chamada não duplica nada.

    As extrações vão primeiro e o resultado por último: resultado gravado significa análise completa.
    """
    agora = agora_utc()
    novas = montar_extracoes(analise_id, por_arquivo, agora)
    if novas:
        extracoes.bulk_write([ReplaceOne({"_id": e["_id"]}, e, upsert=True) for e in novas], ordered=False)
    resultados.replace_one({"_id": analise_id}, montar_resultado(analise_id, resultado, agora), upsert=True)


def salvar_resultado(analise_id: str, resultado: Documento) -> datetime:
    """Regrava só o resultado; devolve quando gravou."""
    agora = agora_utc()
    resultados.replace_one({"_id": analise_id}, montar_resultado(analise_id, resultado, agora), upsert=True)
    return agora


def ler_resultado(analise_id: str) -> Documento | None:
    """Resultado gravado para a análise, como a API devolve, mais `gravado_em`; None se não houver."""
    return resultados.find_one({"_id": analise_id}, {"_id": 0})


def ler_extracoes(arquivo_ids: list[str]) -> dict[str, Documento]:
    """arquivo_id -> extração gravada; arquivo sem extração fica de fora."""
    return {
        e["_id"]: {"documentos": e["documentos"], "escaneado": e.get("escaneado")}
        for e in extracoes.find({"_id": {"$in": arquivo_ids}})
    }
