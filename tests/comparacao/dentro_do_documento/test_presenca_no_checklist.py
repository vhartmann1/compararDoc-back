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


def _avisos(*docs):
    return [a for a in rodar(list(docs)).avisos if "pedir inclusão" in a]


def test_fabricante_sem_nome_vira_aviso():
    for nome in ("UNKNOWN", "desconhecido", "N/A"):
        inv = doc("invoice", numero="F1", fabricante=(nome,), volumes=(5, "CTNS"))
        assert _avisos(inv) == [f"Invoice F1: fabricante sem nome ('{nome}'); pedir inclusão."]


def test_fabricante_com_nome_passa():
    assert _avisos(doc("invoice", numero="F1", fabricante=("Fabrica Unida Ltd",), volumes=(5, "CTNS"))) == []


def test_invoice_sem_volumes_que_o_pl_traz_vira_aviso():
    inv, pl = doc("invoice", numero="F1"), doc("packing_list", numero="F1", volumes=(12, "CTNS"))
    assert _avisos(inv, pl) == ["Invoice F1: sem quantidade e espécie de volumes (Packing List F1 traz 12 CTNS); "
                                "pedir inclusão."]


def test_invoice_sem_volumes_quando_ninguem_traz_nao_avisa():
    assert _avisos(doc("invoice", numero="F1"), doc("packing_list", numero="F1")) == []
