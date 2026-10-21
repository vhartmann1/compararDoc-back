from tests.comparacao.apoio import campo, doc, rodar
from tests.comparacao.cenarios import CAPITAL


def test_parte_por_cnpj_quando_os_dois_tem():
    r = rodar([
        doc("invoice", numero="1", consignatario=("AtlasFit Ltda", "12.345.678/0005-80")),
        doc("packing_list", numero="1", consignatario=("ATLASFIT BRASIL LTDA", "12345678000190")),
    ])
    c = campo(r.comparacoes[0], "consignatario")
    assert c.status == "DIVERGENTE"
    assert c.valores["invoice"].exibicao == "AtlasFit Ltda (12.345.678/0005-80)"


def consignado_a_capital(modalidade):
    return rodar(
        [doc("invoice", numero="1", consignatario=("AtlasFit Ltda", "12.345.678/0005-80")),
         doc("packing_list", numero="1", consignatario=("ATLASFIT LTDA", "12345678000580"))],
        [doc("conhecimento", subtipo="BL", consignatario=CAPITAL)],
        modalidade=modalidade,
    )


def test_capital_no_conhecimento_aceita_em_conta_e_ordem_e_encomenda():
    for modalidade in ("conta_e_ordem", "encomenda"):
        r = consignado_a_capital(modalidade)
        assert campo(r.comparacoes[0], "consignatario").status == "OK"
        assert not [d for d in r.divergencias if d.campo == "consignatario"]
        assert any("Capital Trade" in a and "aceito" in a for a in r.avisos)


def test_conta_e_ordem_nao_esconde_divergencia_entre_invoice_e_pl():
    r = rodar(
        [doc("invoice", numero="1", consignatario=("AtlasFit Ltda", "12.345.678/0005-80")),
         doc("packing_list", numero="1", consignatario=("Outra Empresa Ltda", "99.999.999/0001-99"))],
        [doc("conhecimento", subtipo="BL", consignatario=CAPITAL)],
        modalidade="conta_e_ordem",
    )
    assert campo(r.comparacoes[0], "consignatario").status == "DIVERGENTE"
