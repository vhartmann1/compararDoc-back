"""Listagem de análises: filtro, busca, contagem e paginação (SQLite em memória, dados inventados)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models import AnaliseDB, ArquivoDB
from app.routes.analises import listar_analises

INICIO = datetime(2026, 1, 1, tzinfo=UTC)


def analise(n: int, processo: str | None, processamento: str, resultado: str | None = None, **campos) -> AnaliseDB:
    return AnaliseDB(
        id=f"a{n}",
        processo=processo,
        status_processamento=processamento,
        status_resultado=resultado,
        criado_em=INICIO + timedelta(minutes=n),
        **campos,
    )


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all(
            [
                analise(1, "PROC-001", "CONCLUIDA", "OK", total_divergencias=0, modalidade="propria"),
                analise(2, "PROC-002", "CONCLUIDA", "DIVERGENTE", total_divergencias=3),
                analise(3, "PROC-003", "CONCLUIDA", "DIVERGENTE", total_divergencias=1),
                analise(4, "OUTRO_100%", "CONCLUIDA", "INCOMPLETO", total_divergencias=0),
                analise(5, None, "ERRO", erro="Falhou."),
                analise(6, "proc-006", "PROCESSANDO"),
                analise(7, "PROC-007", "CONCLUIDA", None),  # versão anterior, sem resultado
                ArquivoDB(id="f1", analise_id="a2", nome="x.pdf", caminho="x.pdf", media_type="application/pdf", tamanho_bytes=1),
                ArquivoDB(id="f2", analise_id="a2", ordem=1, nome="y.pdf", caminho="y.pdf", media_type="application/pdf", tamanho_bytes=1),
            ]
        )
        s.commit()
        yield s


def ids(lista) -> list[str]:
    return [a.id for a in lista.itens]


def test_sem_filtro_devolve_tudo_da_mais_recente_para_a_mais_antiga(session):
    lista = listar_analises(session)
    assert ids(lista) == ["a7", "a6", "a5", "a4", "a3", "a2", "a1"]
    assert lista.contagem == {"TODAS": 7, "OK": 1, "DIVERGENTE": 2, "INCOMPLETO": 1, "PROCESSANDO": 1, "ERRO": 1}


def test_resumo_traz_modalidade_divergencias_erro_e_arquivos(session):
    por_id = {a.id: a for a in listar_analises(session).itens}
    assert por_id["a1"].modalidade == "propria"
    assert por_id["a2"].total_divergencias == 3
    assert por_id["a2"].qtd_arquivos == 2
    assert por_id["a5"].erro == "Falhou."
    assert por_id["a5"].qtd_arquivos == 0


@pytest.mark.parametrize(
    ("status", "esperado"),
    [
        ("OK", ["a1"]),
        ("DIVERGENTE", ["a3", "a2"]),
        ("INCOMPLETO", ["a4"]),
        ("PROCESSANDO", ["a6"]),
        ("ERRO", ["a5"]),
    ],
)
def test_filtro_por_status(session, status, esperado):
    lista = listar_analises(session, status=status)
    assert ids(lista) == esperado
    # a contagem não muda com o filtro escolhido
    assert lista.contagem["TODAS"] == 7


def test_busca_ignora_maiusculas_e_ajusta_a_contagem(session):
    lista = listar_analises(session, q=" proc-00 ")
    assert ids(lista) == ["a7", "a6", "a3", "a2", "a1"]
    assert lista.contagem == {"TODAS": 5, "OK": 1, "DIVERGENTE": 2, "INCOMPLETO": 0, "PROCESSANDO": 1, "ERRO": 0}


def test_busca_trata_curinga_como_texto(session):
    assert ids(listar_analises(session, q="100%")) == ["a4"]
    assert ids(listar_analises(session, q="_")) == ["a4"]
    assert ids(listar_analises(session, q="%")) == ["a4"]


def test_busca_combinada_com_filtro(session):
    assert ids(listar_analises(session, status="DIVERGENTE", q="003")) == ["a3"]


def test_paginacao(session):
    assert ids(listar_analises(session, limit=3, offset=0)) == ["a7", "a6", "a5"]
    assert ids(listar_analises(session, limit=3, offset=3)) == ["a4", "a3", "a2"]
    assert ids(listar_analises(session, limit=3, offset=6)) == ["a1"]
    assert ids(listar_analises(session, limit=3, offset=9)) == []


def test_filtra_por_usuario(session):
    session.add(analise(8, "PROC-008", "CONCLUIDA", "OK", usuario_id="u1"))
    session.commit()
    lista = listar_analises(session, usuario_id="u1")
    assert ids(lista) == ["a8"]
    assert lista.contagem["TODAS"] == 1
