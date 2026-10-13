"""O que o Postgres garante sozinho: valores aceitos, exclusão em cascata e índice da busca.

Precisa de um Postgres de verdade (o do docker-compose.yaml); sem ele, os testes são pulados.
Usa um banco temporário, criado e apagado aqui. Dados inventados.
"""

import uuid

import pytest
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import settings
from app.db import criar_tabelas

DADOS = """
INSERT INTO analises (id, processo, status_processamento, etapa, criado_em, status_resultado)
VALUES ('a1', 'PROC-001', 'CONCLUIDA', 'FINALIZADO', now(), 'OK');
INSERT INTO arquivos (id, analise_id, ordem, nome, media_type, tamanho_bytes, caminho)
VALUES ('f1', 'a1', 0, 'x.pdf', 'application/pdf', 1, 'a1/f1.pdf'),
       ('f2', 'a1', 1, 'y.pdf', 'application/pdf', 1, 'a1/f2.pdf');
"""


@pytest.fixture
def banco():
    url = make_url(settings.database_url)
    try:
        administracao = create_engine(url, isolation_level="AUTOCOMMIT")
        administracao.connect().close()
    except OperationalError:
        pytest.skip("Postgres local indisponível")

    nome = f"teste_esquema_{uuid.uuid4().hex[:12]}"
    with administracao.connect() as con:
        con.execute(text(f"CREATE DATABASE {nome}"))
    engine = create_engine(url.set(database=nome))
    criar_tabelas(engine)
    with engine.begin() as con:
        con.execute(text(DADOS))

    yield engine

    engine.dispose()
    with administracao.connect() as con:
        con.execute(text(f"DROP DATABASE {nome} WITH (FORCE)"))
    administracao.dispose()


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE analises SET status_processamento = 'TERMINOU' WHERE id = 'a1'",
        "UPDATE analises SET etapa = 'OUTRA' WHERE id = 'a1'",
        "UPDATE analises SET status_resultado = 'MAIS_OU_MENOS' WHERE id = 'a1'",
        "UPDATE analises SET modalidade = 'qualquer' WHERE id = 'a1'",
        "UPDATE arquivos SET ordem = 0 WHERE id = 'f2'",  # posição repetida na mesma análise
    ],
)
def test_banco_recusa_dado_invalido(banco, sql):
    with pytest.raises(IntegrityError), banco.begin() as con:
        con.execute(text(sql))


def test_apagar_a_analise_apaga_os_arquivos_dela(banco):
    with banco.begin() as con:
        con.execute(text("DELETE FROM analises WHERE id = 'a1'"))
        assert con.execute(text("SELECT count(*) FROM arquivos")).scalar() == 0


def test_busca_por_processo_usa_o_indice_de_trigramas(banco):
    with banco.begin() as con:
        # Com uma linha o Postgres prefere varrer a tabela; aqui só interessa se o índice serve à consulta.
        con.execute(text("SET LOCAL enable_seqscan = off"))
        plano = "\n".join(
            linha[0] for linha in con.execute(text("EXPLAIN SELECT id FROM analises WHERE processo ILIKE '%roc-00%' ESCAPE '\\'"))
        )
    assert "ix_analises_processo_trgm" in plano
