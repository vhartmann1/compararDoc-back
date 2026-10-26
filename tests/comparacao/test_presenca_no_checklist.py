"""Checklist da fatura: a invoice tem de trazer o CNPJ do consignatário."""

from tests.comparacao.apoio import doc, mensagens, rodar

CNPJ = "11.222.333/0001-44"
ENDERECO = "Rua Alfa 10, Vila Serena - SC"


def _invoice(cnpj=CNPJ):
    return doc("invoice", 90, 100, numero="F1", consignatario=("Mar Azul Comercio Ltda", cnpj, ENDERECO))


def _checklist(*docs):
    return [m for m in mensagens(rodar(list(docs)), "interna") if "checklist" in m]


def test_invoice_sem_cnpj_do_consignatario_e_apontada():
    pl = doc("packing_list", 90, 100, numero="F1", consignatario=("Mar Azul Comercio Ltda", CNPJ, ENDERECO))
    assert _checklist(_invoice(cnpj=None), pl) == [
        "Invoice F1: consignatário sem CNPJ (o checklist da fatura pede o importador com CNPJ)"]


def test_invoice_com_cnpj_do_consignatario_passa():
    assert _checklist(_invoice()) == []


def test_packing_list_sem_cnpj_nao_e_cobrado():
    assert _checklist(doc("packing_list", 90, 100, numero="F1", consignatario=("Mar Azul", None, ENDERECO))) == []
