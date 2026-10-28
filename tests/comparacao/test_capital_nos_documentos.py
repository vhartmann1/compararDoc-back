"""Packing list sem a Capital quando a invoice a traz; conta e ordem sem a Capital em nenhum documento."""

from tests.comparacao.apoio import doc, rodar
from tests.comparacao.cenarios import CAPITAL

CLIENTE = ("Lume Bicicletas Comercio Ltda", "12.345.678/0001-90")


def _do_consignatario(r):
    return [d.mensagem for d in r.divergencias if d.campo == "consignatario"]


def test_pl_so_com_o_cliente_e_invoice_com_a_capital_e_apontado():
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL, adquirente=CLIENTE),
               doc("packing_list", numero="1", adquirente=CLIENTE)])
    assert any("sem a Capital Trade" in m and "pedir a inclusão" in m for m in _do_consignatario(r))


def test_pl_com_a_capital_passa():
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL, adquirente=CLIENTE),
               doc("packing_list", numero="1", consignatario=CAPITAL, adquirente=CLIENTE)])
    assert not _do_consignatario(r)


def test_pl_sem_nenhuma_parte_nao_e_apontado():
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL, adquirente=CLIENTE), doc("packing_list", numero="1")])
    assert not _do_consignatario(r)


def test_invoice_sem_a_capital_nao_cobra_a_capital_no_pl():
    r = rodar([doc("invoice", numero="1", consignatario=CLIENTE), doc("packing_list", numero="1", adquirente=CLIENTE)])
    assert not any("sem a Capital" in m for m in _do_consignatario(r))


def _todos_do_cliente(modalidade):
    return rodar([doc("invoice", numero="1", consignatario=CLIENTE),
                  doc("packing_list", numero="1", consignatario=CLIENTE)],
                 [doc("conhecimento", subtipo="BL", consignatario=CLIENTE, notify=CLIENTE)], modalidade=modalidade)


def test_conta_e_ordem_sem_a_capital_em_nenhum_documento_e_apontado():
    assert any("Conta e ordem sem a Capital" in m for m in _do_consignatario(_todos_do_cliente("conta_e_ordem")))


def test_conta_propria_sem_a_capital_passa():
    for modalidade in ("propria", None):
        assert not _do_consignatario(_todos_do_cliente(modalidade))


def test_conta_e_ordem_com_a_capital_no_bl_passa():
    r = rodar([doc("invoice", numero="1", consignatario=CLIENTE)],
              [doc("conhecimento", subtipo="BL", consignatario=CAPITAL)], modalidade="conta_e_ordem")
    assert not any("Conta e ordem sem a Capital" in m for m in _do_consignatario(r))
