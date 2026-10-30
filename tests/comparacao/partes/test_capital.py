"""Os dois critérios de Capital: identificar (o CNPJ decide) e descartar (qualquer sinal basta)."""

from app.schemas import Parte
from app.services.comparacao.partes.capital import (
    CNPJ_RAIZ_CAPITAL,
    parte_da_capital,
    sem_sinal_da_capital,
    valor_da_capital,
)
from app.services.comparacao.tipos import Valor

CNPJ_DA_CAPITAL = f"{CNPJ_RAIZ_CAPITAL}000199"
CNPJ_DE_OUTRA = "11222333000144"


def _parte(nome, cnpj=None):
    return Parte(nome=nome, cnpj=cnpj, endereco=None, cidade=None, pais=None, pagina=1)


def _valor(*empresas):
    return Valor(tuple((nome, cnpj, False) for nome, cnpj in empresas), "", None, None, None)


def test_cnpj_decide_quando_ha():
    assert parte_da_capital(_parte("Lumen Comercial Ltda", CNPJ_DA_CAPITAL))
    assert not parte_da_capital(_parte("Capital Trade Ltda", CNPJ_DE_OUTRA))
    assert parte_da_capital(_parte("Capital Trade Importação e Exportação Ltda"))


def test_valor_da_capital_exige_todas_as_empresas():
    assert valor_da_capital(_valor(("Capital Trade", None), ("X", CNPJ_DA_CAPITAL)))
    assert not valor_da_capital(_valor(("Capital Trade", None), ("Lumen Comercial", None)))


def test_cnpj_lido_errado_com_o_nome_da_capital_nao_vira_cliente():
    valor = _valor(("Capital Trade Ltda", CNPJ_DE_OUTRA))
    assert not valor_da_capital(valor)
    assert not sem_sinal_da_capital(valor)


def test_sem_sinal_quando_nem_nome_nem_raiz_do_cnpj():
    assert sem_sinal_da_capital(_valor(("Lumen Comercial", CNPJ_DE_OUTRA)))
    assert not sem_sinal_da_capital(_valor(("Lumen Comercial", CNPJ_DA_CAPITAL)))
