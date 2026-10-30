"""Consignatário pela modalidade (Capital × cliente) e conferência do notify do conhecimento."""

from tests.comparacao.apoio import campo, doc, rodar
from tests.comparacao.cenarios import CAPITAL

CLIENTE = ("Lume Bicicletas Comercio Ltda", "12.345.678/0001-90")


def _com_cliente_na_invoice(modalidade):
    return rodar(
        [doc("invoice", numero="1", consignatario=CLIENTE), doc("packing_list", numero="1", consignatario=CLIENTE)],
        [doc("conhecimento", subtipo="BL", consignatario=CAPITAL)],
        modalidade=modalidade,
    )


def test_capital_no_bl_e_cliente_na_invoice_e_aviso_em_qualquer_modalidade():
    for modalidade in ("conta_e_ordem", "encomenda", "propria", None):
        r = _com_cliente_na_invoice(modalidade)
        assert campo(r.comparacoes[0], "consignatario").status == "OK"
        assert not [d for d in r.divergencias if d.campo == "consignatario"]
        assert any(a.startswith("Consignatário: BL em nome da Capital Trade") and "Lume Bicicletas" in a
                   for a in r.avisos)


def test_aviso_do_consignatario_diz_o_que_a_modalidade_espera():
    avisos = {m: " ".join(_com_cliente_na_invoice(m).avisos) for m in ("conta_e_ordem", "propria", None)}
    assert "aceito pela modalidade conta e ordem" in avisos["conta_e_ordem"]
    assert "em conta própria o consignatário esperado é o cliente" in avisos["propria"]
    assert "modalidade não informada" in avisos[None]


def test_tudo_em_nome_da_capital_nao_gera_aviso():
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL),
               doc("packing_list", numero="1", consignatario=CAPITAL)],
              [doc("conhecimento", subtipo="BL", consignatario=CAPITAL)])
    assert campo(r.comparacoes[0], "consignatario").status == "OK"
    assert not any(a.startswith("Consignatário") for a in r.avisos)


def test_capital_com_cnpj_lido_errado_nao_vira_cliente():
    lido_errado = ("Capital Trade Importacao e Exportacao Ltda", "07.872.328/0001-58")
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL),
               doc("packing_list", numero="1", consignatario=lido_errado)],
              [doc("conhecimento", subtipo="BL", consignatario=CAPITAL)])
    assert not any(a.startswith("Consignatário") for a in r.avisos)
    assert campo(r.comparacoes[0], "consignatario").status == "DIVERGENTE"


def test_bl_de_outra_empresa_que_nao_a_capital_continua_divergindo():
    r = rodar([doc("invoice", numero="1", consignatario=CLIENTE),
               doc("packing_list", numero="1", consignatario=CLIENTE)],
              [doc("conhecimento", subtipo="BL", consignatario=("Terceira Logistica Ltda", "98.765.432/0001-10"))])
    assert campo(r.comparacoes[0], "consignatario").status == "DIVERGENTE"


def _notify(notify, adquirente=CLIENTE[0]):
    return rodar([doc("invoice", numero="1", consignatario=CAPITAL, adquirente=adquirente),
                  doc("packing_list", numero="1", consignatario=CAPITAL)],
                 [doc("conhecimento", subtipo="BL", numero="BL1", consignatario=CAPITAL, notify=notify)])


def _avisos_do_notify(r):
    return [a for a in r.avisos if a.startswith("Notify")]


def test_notify_capital_ou_adquirente_nao_gera_aviso():
    assert not _avisos_do_notify(_notify(CAPITAL))
    assert not _avisos_do_notify(_notify("LUME BICICLETAS COMERCIO LTDA."))


def test_notify_de_outra_empresa_gera_aviso_e_nao_divergencia():
    r = _notify("Terceira Logistica Ltda")
    assert _avisos_do_notify(r) == [
        "Notify do BL BL1 (Terceira Logistica Ltda) não é a Capital Trade nem o adquirente da invoice "
        "(Lume Bicicletas Comercio Ltda); confira."
    ]
    assert not r.divergencias


def test_notify_sem_adquirente_para_conferir_nao_gera_aviso():
    assert not _avisos_do_notify(_notify("Terceira Logistica Ltda", adquirente=None))


def test_notify_repetido_no_pl_do_fornecedor_nao_vira_cliente_quando_ha_adquirente():
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL, adquirente=CLIENTE[0]),
               doc("packing_list", numero="1", consignatario=CAPITAL, notify="Terceira Logistica Ltda")],
              [doc("conhecimento", subtipo="BL", numero="BL1", consignatario=CAPITAL, notify="Terceira Logistica Ltda")])
    assert _avisos_do_notify(r) == [
        "Notify do BL BL1 (Terceira Logistica Ltda) não é a Capital Trade nem o adquirente da invoice "
        "(Lume Bicicletas Comercio Ltda); confira."
    ]


def test_sem_adquirente_o_notify_da_invoice_ainda_conta_como_cliente():
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL, notify=CLIENTE[0]),
               doc("packing_list", numero="1", consignatario=CAPITAL)],
              [doc("conhecimento", subtipo="BL", numero="BL1", consignatario=CAPITAL, notify=CLIENTE[0])])
    assert not _avisos_do_notify(r)
