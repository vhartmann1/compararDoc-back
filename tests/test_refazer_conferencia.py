"""Refazer a conferência com as leituras já gravadas (SQLite em memória, MongoDB simulado, dados inventados)."""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import mongo
from app.models import AnaliseDB, ArquivoDB
from app.routes.analises import refazer_conferencia

AGORA = datetime(2026, 1, 2, tzinfo=UTC)


def documento(tipo: str, bruto: float) -> dict:
    return {
        "tipo": tipo, "subtipo": None, "paginas": [1], "numero": "INV-1", "invoices_referenciadas": [], "po": None,
        "incoterm": None, "frete": None, "moeda": None, "pais_origem": None, "emitente_assinatura": None,
        "versao": "original", "exportador": None, "consignatario": None, "porto_origem": None, "porto_destino": None,
        "peso_liquido_total": None,
        "peso_bruto_total": {"valor": bruto, "unidade": "KG", "texto_original": f"{bruto} KG", "pagina": 1},
        "volumes_total": None, "quantidade_total": None, "ncms": [], "itens": [], "inconsistencias_internas": [],
    }


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all([
            AnaliseDB(id="a1", processo="PROC-1", status_processamento="CONCLUIDA", status_resultado="OK", total_divergencias=0),
            AnaliseDB(id="a2", processo="PROC-2", status_processamento="PROCESSANDO"),
            ArquivoDB(id="f1", analise_id="a1", nome="inv.pdf", caminho="inv.pdf", media_type="application/pdf", tamanho_bytes=1),
            ArquivoDB(id="f2", analise_id="a1", ordem=1, nome="pl.pdf", caminho="pl.pdf", media_type="application/pdf", tamanho_bytes=1),
        ])
        s.commit()
        yield s


@pytest.fixture
def gravados(monkeypatch):
    extracoes = {
        "f1": {"documentos": [documento("invoice", 110)]},
        "f2": {"documentos": [documento("packing_list", 120)]},
    }
    resultados: dict[str, dict] = {}
    monkeypatch.setattr(mongo, "ler_extracoes", lambda ids: {i: extracoes[i] for i in ids if i in extracoes})

    def salvar_resultado(analise_id, resultado):
        resultados[analise_id] = resultado
        return AGORA

    monkeypatch.setattr(mongo, "salvar_resultado", salvar_resultado)
    return extracoes, resultados


def test_refaz_a_conferencia_com_as_leituras_gravadas_e_atualiza_o_resumo(session, gravados):
    _, resultados = gravados
    analise = refazer_conferencia("a1", session)
    assert analise.resultado.status == "DIVERGENTE"
    assert analise.conferido_em == AGORA
    assert resultados["a1"]["status"] == "DIVERGENTE"
    gravada = session.get(AnaliseDB, "a1")
    assert gravada.status_resultado == "DIVERGENTE" and gravada.total_divergencias == 1


def test_so_refaz_a_conferencia_de_analise_concluida(session, gravados):
    with pytest.raises(HTTPException) as erro:
        refazer_conferencia("a2", session)
    assert erro.value.status_code == 409


def test_sem_a_leitura_gravada_pede_para_enviar_de_novo(session, gravados):
    extracoes, _ = gravados
    del extracoes["f2"]
    with pytest.raises(HTTPException) as erro:
        refazer_conferencia("a1", session)
    assert erro.value.status_code == 409 and "envie novamente" in erro.value.detail
