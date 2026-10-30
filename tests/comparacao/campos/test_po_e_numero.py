from app.services.comparacao.normalizacao.numeros_de_documento import (
    mesmo_numero,
    numero_da_invoice_para_conferir,
    pos_do_texto,
)
from tests.comparacao.apoio import campo, doc, rodar


def _po(invoice, pl):
    r = rodar([doc("invoice", numero="1", po=invoice), doc("packing_list", numero="1", po=pl)])
    return campo(r.comparacoes[0], "po").status


def test_os_mesmos_pos_com_separadores_e_rotulos_diferentes_conferem():
    assert _po("PO# 5501&PO# 5502&5503", "PO#5501, PO#5502, PO#5503") == "OK"
    assert _po("5501&5502", "PO#5502，PO#5501") == "OK"
    assert _po("PO 5501 / PO 5502", "5502; 5501") == "OK"


def test_lista_de_pos_com_um_a_mais_continua_divergindo():
    assert _po("PO# 5501&PO# 5502", "PO#5501, PO#5502, PO#5503") == "DIVERGENTE"


def test_po_com_barra_no_numero_nao_vira_dois():
    assert pos_do_texto("114/26") == ["114/26"]
    assert _po("114/26", "114") == "DIVERGENTE"


def _numeros(a, b):
    return mesmo_numero(numero_da_invoice_para_conferir(a), numero_da_invoice_para_conferir(b))


def test_numero_com_serie_do_ano_na_frente_confere():
    assert _numeros("FT AB.2026/417203", "417203")
    r = rodar([doc("invoice", numero="FT AB.2026/417203"), doc("packing_list", refs=["417203"])])
    assert campo(r.comparacoes[0], "numero_invoice").status == "OK"


def test_serie_que_nao_e_ano_ou_numero_diferente_continua_divergindo():
    assert not _numeros("FT AB.2026/417203", "417204")
    assert not _numeros("AB1234/417203", "417203")
    assert not _numeros("AB2026417203", "6417203")
    assert not _numeros("AB2026417203", "417203")  # série com o ano só vale separada do número por barra
