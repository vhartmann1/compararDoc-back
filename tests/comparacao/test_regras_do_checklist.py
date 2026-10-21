"""Regras que vêm do checklist da operação (porto de descarga/entrega, shipper = fabricante)."""

from tests.comparacao.apoio import campo, doc, rodar


def _bl(**kw):
    return doc("conhecimento", 100, 110, subtipo="BL", numero="BL1", **kw)


def test_destino_da_invoice_confere_com_o_local_de_entrega_do_bl():
    r = rodar(
        [doc("invoice", 100, 110, numero="A1", destino="Azulmar"), doc("packing_list", 100, 110, refs=["A1"], destino="Azulmar")],
        [_bl(destino="Verdemar", entrega="Azulmar")],
    )
    destino = campo(r.comparacoes[0], "porto_destino")
    assert destino.status == "OK"
    assert destino.valores["conhecimento"].exibicao == "VERDEMAR (entrega: AZULMAR)"


def test_destino_diferente_da_descarga_e_da_entrega_diverge():
    r = rodar(
        [doc("invoice", 100, 110, numero="A1", destino="Azulmar"), doc("packing_list", 100, 110, refs=["A1"])],
        [_bl(destino="Verdemar", entrega="Verdemar")],
    )
    assert campo(r.comparacoes[0], "porto_destino").status == "DIVERGENTE"


def test_shipper_do_bl_pode_ser_o_fabricante_citado_na_invoice():
    fabricante = ("Fabrica Norte Ltd", "12 Industrial Rd, Northtown", "CANADA")
    r = rodar(
        [doc("invoice", 100, 110, numero="A1", exportador="Comercial Sul GmbH", endereco_exportador="Ringstrasse 5, Sudstadt",
             pais_exportador="AUSTRIA", fabricante=fabricante),
         doc("packing_list", 100, 110, refs=["A1"], exportador="Comercial Sul GmbH", pais_exportador="AUSTRIA")],
        [_bl(exportador="FABRICA NORTE LTD", endereco_exportador="12 INDUSTRIAL RD, NORTHTOWN", pais_exportador="CANADA")],
    )
    comp = r.comparacoes[0]
    assert [campo(comp, c).status for c in ("exportador", "endereco_exportador", "pais_exportador")] == ["OK"] * 3


def test_shipper_que_nao_e_exportador_nem_fabricante_e_triangular():
    r = rodar(
        [doc("invoice", 100, 110, numero="A1", exportador="Comercial Sul GmbH", fabricante=("Fabrica Norte Ltd", None, "CANADA")),
         doc("packing_list", 100, 110, refs=["A1"], exportador="Comercial Sul GmbH")],
        [_bl(exportador="Outra Empresa SA", endereco_exportador="Rua Larga 7, Vilamar")],
    )
    assert not [d for d in r.divergencias if d.campo == "exportador"]
    assert any("Shipper do BL (Outra Empresa SA)" in a and "triangular" in a for a in r.avisos)


def test_moeda_do_conhecimento_e_a_do_frete_e_nao_entra_na_comparacao():
    r = rodar(
        [doc("invoice", 100, 110, numero="A1", moeda="USD"), doc("packing_list", 100, 110, refs=["A1"])],
        [_bl(moeda="EUR")],
    )
    assert campo(r.comparacoes[0], "moeda").status != "DIVERGENTE"


def test_fob_com_local_diferente_do_porto_de_embarque_aponta():
    r = rodar(
        [doc("invoice", 100, 110, numero="A1", incoterm=("FOB", "Portomar"), origem="Baiamar"),
         doc("packing_list", 100, 110, refs=["A1"], origem="Baiamar")],
        [_bl(origem="Baiamar")],
    )
    assert any("FOB PORTOMAR" in d.mensagem and "embarque BAIAMAR" in d.mensagem for d in r.divergencias)


def test_cif_com_local_igual_a_entrega_do_bl_nao_aponta():
    r = rodar(
        [doc("invoice", 100, 110, numero="A1", incoterm=("CIF", "Azulmar")), doc("packing_list", 100, 110, refs=["A1"])],
        [_bl(destino="Verdemar", entrega="Azulmar", frete="PREPAID")],
    )
    assert not [d for d in r.divergencias if d.categoria == "coerencia"]


def test_fob_com_pais_no_lugar_do_porto_nao_aponta():
    r = rodar(
        [doc("invoice", 100, 110, numero="A1", incoterm=("FOB", "Indonesia"), origem="Baiamar"),
         doc("packing_list", 100, 110, refs=["A1"])],
    )
    assert not [d for d in r.divergencias if d.categoria == "coerencia"]


def test_destino_que_e_so_o_pais_nao_entra_na_comparacao_de_porto():
    r = rodar(
        [doc("invoice", 100, 110, numero="A1", destino="Brazil"), doc("packing_list", 100, 110, refs=["A1"], destino="Brazil")],
        [_bl(destino="Verdemar")],
    )
    assert campo(r.comparacoes[0], "porto_destino").status != "DIVERGENTE"
