"""PL com uma linha por bobina × invoice com uma linha por medida."""

from app.services.comparacao.itens.medidas_do_item import mesmas_medidas
from tests.comparacao.apoio import doc, item, rodar

BASE_PL = "STAINLESS STEEL COILS - GRADE 410 - Polished - {} MM x 980.000 MM - COIL"
BASE_INV = "STAINLESS STEEL COILS {}x980.000xCOIL-410/PL"


def _pl(*espessuras):
    return doc("packing_list", numero="7", itens=[item(None, BASE_PL.format(e), 1, "PIECES", lotes=[f"LT{n}"])
                                                  for n, e in enumerate(espessuras)])


def _invoice(*linhas):
    return doc("invoice", numero="7", itens=[item(None, BASE_INV.format(e), q, "MT") for e, q in linhas])


def _itens(r):
    return [d.mensagem for d in r.divergencias if d.categoria == "item"]


def test_linhas_do_pl_casam_com_a_linha_da_invoice_de_mesma_medida():
    r = rodar([_invoice(("0.600", 12.5), ("1.500", 8.25)), _pl(".600", "1.500", ".600", ".600", "1.500")])
    assert not any("só n" in m for m in _itens(r))  # a descrição diferente continua acusada


def test_medida_diferente_nao_junta():
    r = rodar([_invoice(("0.600", 12.5), ("1.500", 8.25)), _pl(".600", ".600", "1.800")])
    assert any("1.500" in m or "1.800" in m for m in _itens(r))


def test_mesmas_medidas_normaliza_zero_e_unidade():
    assert mesmas_medidas(BASE_PL.format(".600"), BASE_INV.format("0.600"))
    assert not mesmas_medidas(BASE_PL.format(".600"), BASE_INV.format("1.600"))
    assert not mesmas_medidas("ALUMINIUM SHEET 0.600x980.000", BASE_INV.format("0.600"))


def test_mesma_medida_com_descricao_diferente_continua_acusando():
    for invoice, pl in (("STEEL COILS GALVANIZED 0.500x1000.000", "STEEL COILS PREPAINTED .500 MM x 1000.000 MM"),
                        ("STAINLESS STEEL COILS GRADE 430 0.800x1250.000",
                         "STAINLESS STEEL COILS GRADE 304 .800 MM x 1250.000 MM")):
        r = rodar([doc("invoice", numero="8", itens=[item(None, invoice, 3, "MT")]),
                   doc("packing_list", numero="8", itens=[item(None, pl, 1, "PIECES"), item(None, pl, 1, "PIECES")])])
        assert any("descrição" in m.lower() for m in _itens(r)), _itens(r)


def test_par_no_formato_bobina_por_linha_casa_e_acusa_so_a_descricao():
    invoice = "HOT ROLLED CARBON STEEL COILS 0.450x1100.000xCOIL-220/PO/SE"
    pl = "HOT ROLLED CARBON STEEL COILS - GRADE 220 - PICKLED OILED - Slit Edge - .450 MM x 1100.000 MM - COIL"
    r = rodar([doc("invoice", numero="9", itens=[item(None, invoice, 4.2, "MT")]),
               doc("packing_list", numero="9", itens=[item(None, pl, 1, "PIECES"), item(None, pl, 1, "PIECES")])])
    [mensagem] = _itens(r)  # 'PO/SE' × 'PICKLED OILED - Slit Edge': abreviação não é aceita
    assert "descrição" in mensagem


def test_mesma_medida_com_palavra_a_mais_ou_diferente_acusa():
    pares = (("ALUMINIUM PLATE ANODIZED 3x1500", "ALUMINIUM PLATE 3 MM x 1500 MM NOT ANODIZED"),
             ("PLASTIC FILM PE 0.05x1000", "PLASTIC FILM 0.05 MM x 1000 MM POLYESTER EMBOSSED"),
             ("STEEL SHEET CR 2x1000", "STEEL SHEET 2.0 MM x 1000 MM COATED RED"),
             ("COPPER TUBE 10x1", "COPPER TUBE TINNED 10 MM x 1 MM"))
    for invoice, pl in pares:
        r = rodar([doc("invoice", numero="8", itens=[item(None, invoice, 3, "MT")]),
                   doc("packing_list", numero="8", itens=[item(None, pl, 1, "PIECES")])])
        assert any("descrição" in m.lower() for m in _itens(r)), (invoice, _itens(r))


def test_so_a_notacao_da_medida_muda_nao_acusa():
    r = rodar([doc("invoice", numero="8", itens=[item(None, "STEEL SHEET CR 2x1000 COIL", 3, "MT")]),
               doc("packing_list", numero="8", itens=[item(None, "STEEL SHEET CR 2 MM x 1000 MM COIL", 1, "PIECES")])])
    assert _itens(r) == []
