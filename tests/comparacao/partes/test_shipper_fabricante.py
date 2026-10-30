"""Shipper do BL que é o fabricante declarado: endereço e país conferem com os do fabricante."""

from tests.comparacao.apoio import campo, doc, rodar

VENDEDOR = "Corredor Metals Trading LLC"
FABRICA = "Forja do Vale Limited"
SEDE = {"endereco_exportador": "300 Lake Avenue, Suite 12, Springdale", "pais_exportador": "USA",
        "cidade_exportador": "SPRINGDALE"}
# a invoice cola as palavras do endereço da fábrica; o PL traz o endereço por extenso
FAB_INVOICE = (FABRICA, "Distrito Industrial NorteCampo Alto Vila Serra", "OUTRALANDIA", "VILA SERRA")
FAB_PL = (FABRICA, "Distrito Industrial Norte, Vila Serra Campo Alto, 700123, OUTRALANDIA", "OUTRALANDIA", "VILA SERRA")


def _rodar(endereco_bl, ordem=1):
    inv = doc("invoice", numero="5", exportador=VENDEDOR, fabricante=FAB_INVOICE, **SEDE)
    pl = doc("packing_list", numero="5", exportador=VENDEDOR, fabricante=FAB_PL, **SEDE)
    bl = doc("conhecimento", subtipo="BL", exportador="FORJA DO VALE LTD", endereco_exportador=endereco_bl,
             pais_exportador="OUTRALANDIA", cidade_exportador="VILA SERRA", refs=["5"])
    return rodar([inv, pl][::ordem], [bl])


def test_endereco_e_pais_do_bl_conferem_com_o_fabricante_declarado():
    for ordem in (1, -1):
        r = _rodar("Distrito Industrial Norte, Vila Serra, Campo Alto, 700123, OUTRALANDIA", ordem)
        assert campo(r.comparacoes[0], "endereco_exportador").status == "OK"
        assert campo(r.comparacoes[0], "pais_exportador").status == "OK"


def test_endereco_do_bl_diferente_do_fabricante_continua_erro():
    r = _rodar("Rua Doze 88, Bairro Porto, Vila Serra")
    assert campo(r.comparacoes[0], "endereco_exportador").status == "DIVERGENTE"


def test_fabricantes_diferentes_na_invoice_e_no_pl_nao_somam():
    outra = ("Laminadora Pinheiro Ltd", "Rua Sete 77, Polo Leste, Vila Serra", "OUTRALANDIA", "VILA SERRA")
    inv = doc("invoice", numero="5", exportador=VENDEDOR, fabricante=FAB_PL, **SEDE)
    pl = doc("packing_list", numero="5", exportador=VENDEDOR, fabricante=outra, **SEDE)
    # shipper com o nome do fabricante da invoice e o endereço do fabricante do PL
    bl = doc("conhecimento", subtipo="BL", exportador="FORJA DO VALE LTD", endereco_exportador=outra[1],
             pais_exportador="OUTRALANDIA", cidade_exportador="VILA SERRA", refs=["5"])
    for ordem in (1, -1):
        r = rodar([inv, pl][::ordem], [bl])
        assert campo(r.comparacoes[0], "endereco_exportador").status == "DIVERGENTE"
