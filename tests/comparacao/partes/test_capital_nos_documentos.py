"""Packing list sem a Capital quando a invoice a traz; conta e ordem sem a Capital em nenhum documento."""

from tests.comparacao.apoio import doc, mensagens_de, rodar
from tests.comparacao.cenarios import CAPITAL

CLIENTE = ("Lume Bicicletas Comercio Ltda", "12.345.678/0001-90")


def test_pl_so_com_o_cliente_e_invoice_com_a_capital_e_apontado():
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL, adquirente=CLIENTE),
               doc("packing_list", numero="1", adquirente=CLIENTE)])
    assert mensagens_de(r, "consignatario") == [
        "Consignatário: falta a Capital Trade em Packing List 1, que traz só Lume Bicicletas Comercio Ltda; "
        "ela consta em Invoice 1; pedir inclusão."
    ]


def test_pl_com_o_cliente_consignatario_e_invoice_com_a_capital_pede_a_inclusao():
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL),
               doc("packing_list", numero="1", consignatario=CLIENTE)])
    assert mensagens_de(r, "consignatario") == [
        "Consignatário: falta a Capital Trade em Packing List, que traz Lume Bicicletas Comercio Ltda "
        "(12.345.678/0001-90); ela consta em Invoice; pedir inclusão."
    ]


def test_dois_clientes_diferentes_seguem_com_os_dois_nomes():
    outro = ("Serra Verde Comercio Ltda", "98.765.432/0001-10")
    r = rodar([doc("invoice", numero="1", consignatario=outro), doc("packing_list", numero="1", consignatario=CLIENTE)])
    assert [m.split(":")[0] for m in mensagens_de(r, "consignatario")] == ["Consignatário"]
    assert not any("falta a Capital" in m for m in mensagens_de(r, "consignatario"))


def test_pl_com_a_capital_passa():
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL, adquirente=CLIENTE),
               doc("packing_list", numero="1", consignatario=CAPITAL, adquirente=CLIENTE)])
    assert not mensagens_de(r, "consignatario")


def test_pl_sem_nenhuma_parte_nao_e_apontado():
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL, adquirente=CLIENTE), doc("packing_list", numero="1")])
    assert not mensagens_de(r, "consignatario")


def test_invoice_sem_a_capital_nao_cobra_a_capital_no_pl():
    r = rodar([doc("invoice", numero="1", consignatario=CLIENTE), doc("packing_list", numero="1", adquirente=CLIENTE)])
    assert not any("falta a Capital" in m for m in mensagens_de(r, "consignatario"))


def _todos_do_cliente(modalidade):
    return rodar([doc("invoice", numero="1", consignatario=CLIENTE),
                  doc("packing_list", numero="1", consignatario=CLIENTE)],
                 [doc("conhecimento", subtipo="BL", consignatario=CLIENTE, notify=CLIENTE)], modalidade=modalidade)


def test_conta_e_ordem_sem_a_capital_em_nenhum_documento_e_apontado():
    r = _todos_do_cliente("conta_e_ordem")
    assert any("Conta e ordem sem a Capital" in m for m in mensagens_de(r, "consignatario"))


def test_conta_propria_sem_a_capital_passa():
    for modalidade in ("propria", None):
        assert not mensagens_de(_todos_do_cliente(modalidade), "consignatario")


def test_conta_e_ordem_com_a_capital_no_bl_passa():
    r = rodar([doc("invoice", numero="1", consignatario=CLIENTE)],
              [doc("conhecimento", subtipo="BL", consignatario=CAPITAL)], modalidade="conta_e_ordem")
    assert not any("Conta e ordem sem a Capital" in m for m in mensagens_de(r, "consignatario"))


def test_capital_com_cnpj_lido_errado_nao_vira_falta_da_capital():
    torto = ("CAPITAL TRADE IMPORTACAO E EXPORTACAO LTDA", "07.872.399/0001-58")
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL),
               doc("packing_list", numero="1", consignatario=CAPITAL)],
              [doc("conhecimento", subtipo="BL", consignatario=torto)])
    assert not any("falta a Capital" in m for m in mensagens_de(r, "consignatario"))
