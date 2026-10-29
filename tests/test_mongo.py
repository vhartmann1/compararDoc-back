"""Documentos no MongoDB: formato (sem banco) e gravação/leitura de verdade. Dados inventados."""

import uuid
from datetime import UTC, datetime

import pytest
from pymongo.errors import PyMongoError

from app import mongo

RESULTADO = {"status": "OK", "documentos": [], "comparacoes": [], "itens": [], "divergencias": [], "avisos": []}
POR_ARQUIVO = {
    "arquivo-b": {"documentos": [{"tipo": "invoice"}], "escaneado": True},
    "arquivo-a": {"documentos": [], "escaneado": False},
}
AGORA = datetime(2026, 1, 1, tzinfo=UTC)


def test_resultado_vira_um_documento_com_o_id_da_analise():
    assert mongo.montar_resultado("analise-1", RESULTADO, AGORA) == {"_id": "analise-1", **RESULTADO, "gravado_em": AGORA}


def test_cada_arquivo_vira_um_documento_de_extracao_com_o_id_dele():
    assert mongo.montar_extracoes("analise-1", POR_ARQUIVO, AGORA) == [
        {"_id": "arquivo-b", "analise_id": "analise-1", "documentos": [{"tipo": "invoice"}], "escaneado": True,
         "gravado_em": AGORA},
        {"_id": "arquivo-a", "analise_id": "analise-1", "documentos": [], "escaneado": False, "gravado_em": AGORA},
    ]


def test_analise_sem_extracao_nao_gera_documento():
    assert mongo.montar_extracoes("analise-1", {}, AGORA) == []


# ---------------------------------------------------------------------------
# Gravação e leitura de verdade. Precisa do MongoDB local; sem ele, os testes são pulados.
# Usa coleções temporárias no banco da aplicação, apagadas no fim.
# ---------------------------------------------------------------------------


@pytest.fixture
def colecoes_temporarias(monkeypatch):
    try:
        mongo.verificar()
    except PyMongoError:
        pytest.skip("MongoDB local indisponível")
    banco = mongo.resultados.database
    sufixo = uuid.uuid4().hex[:12]
    monkeypatch.setattr(mongo, "resultados", banco[f"teste_resultados_{sufixo}"])
    monkeypatch.setattr(mongo, "extracoes", banco[f"teste_extracoes_{sufixo}"])
    yield
    mongo.resultados.drop()
    mongo.extracoes.drop()


def test_grava_e_le_o_resultado_como_a_api_devolve(colecoes_temporarias):
    mongo.salvar("analise-1", RESULTADO, POR_ARQUIVO)
    gravado = mongo.ler_resultado("analise-1")
    assert {k: v for k, v in gravado.items() if k != "gravado_em"} == RESULTADO
    assert gravado["gravado_em"] is not None
    assert mongo.ler_resultado("nao-existe") is None


def test_grava_uma_extracao_por_arquivo(colecoes_temporarias):
    mongo.salvar("analise-1", RESULTADO, POR_ARQUIVO)
    gravadas = {e["_id"]: e for e in mongo.extracoes.find()}
    assert set(gravadas) == {"arquivo-a", "arquivo-b"}
    assert gravadas["arquivo-b"]["analise_id"] == "analise-1"
    assert gravadas["arquivo-b"]["documentos"] == [{"tipo": "invoice"}]


def test_regravar_substitui_em_vez_de_duplicar(colecoes_temporarias):
    mongo.salvar("analise-1", RESULTADO, POR_ARQUIVO)
    mongo.salvar("analise-1", {**RESULTADO, "status": "DIVERGENTE"}, POR_ARQUIVO)
    assert mongo.resultados.count_documents({}) == 1
    assert mongo.extracoes.count_documents({}) == 2
    assert mongo.ler_resultado("analise-1")["status"] == "DIVERGENTE"


def test_le_as_extracoes_gravadas_por_arquivo(colecoes_temporarias):
    mongo.salvar("analise-1", RESULTADO, POR_ARQUIVO)
    lidas = mongo.ler_extracoes(["arquivo-b", "nao-existe"])
    assert lidas == {"arquivo-b": {"documentos": [{"tipo": "invoice"}], "escaneado": True}}


def test_regravar_so_o_resultado_mantem_as_extracoes(colecoes_temporarias):
    mongo.salvar("analise-1", RESULTADO, POR_ARQUIVO)
    mongo.salvar_resultado("analise-1", {**RESULTADO, "status": "DIVERGENTE"})
    assert mongo.ler_resultado("analise-1")["status"] == "DIVERGENTE"
    assert mongo.extracoes.count_documents({}) == 2
