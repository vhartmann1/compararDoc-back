"""PL com uma linha por bobina × invoice com uma linha por medida."""

from tests.comparacao.apoio import doc, item, mensagens, rodar

BASE_PL = "STAINLESS STEEL COILS - GRADE 410 - Polished - {} MM x 980.000 MM - COIL"
BASE_INV = "STAINLESS STEEL COILS {}x980.000xCOIL-410/PL"


def _pl(*espessuras):
    return doc("packing_list", numero="7", itens=[item(None, BASE_PL.format(e), 1, "PIECES", lotes=[f"LT{n}"])
                                                  for n, e in enumerate(espessuras)])


def _invoice(*linhas):
    return doc("invoice", numero="7", itens=[item(None, BASE_INV.format(e), q, "MT") for e, q in linhas])


def _avisos_de_escrita(r):
    return [a for a in r.avisos if "de forma diferente" in a]


def test_linhas_do_pl_casam_com_a_linha_da_invoice_de_mesma_medida():
    r = rodar([_invoice(("0.600", 12.5), ("1.500", 8.25)), _pl(".600", "1.500", ".600", ".600", "1.500")])
    assert mensagens(r, "item") == []  # 'PL' × 'Polished' é só escrita diferente: um aviso para as duas linhas
    [aviso] = _avisos_de_escrita(r)
    assert aviso.startswith("Itens: 2 descrições escritas de forma diferente")


def test_medida_diferente_nao_junta():
    r = rodar([_invoice(("0.600", 12.5), ("1.500", 8.25)), _pl(".600", ".600", "1.800")])
    assert any("1.500" in m or "1.800" in m for m in mensagens(r, "item"))


def _par(invoice, pl):
    return rodar([doc("invoice", numero="8", itens=[item(None, invoice, 3, "MT")]),
                  doc("packing_list", numero="8", itens=[item(None, pl, 1, "PIECES"), item(None, pl, 1, "PIECES")])])


def test_mesma_medida_com_grau_ou_negacao_diferente_e_erro():
    for invoice, pl in (("STAINLESS STEEL COILS GRADE 430 0.600x900.000",
                         "STAINLESS STEEL COILS GRADE 304 .600 MM x 900.000 MM"),
                        ("ALUMINIUM PLATE ANODIZED 3x1500", "ALUMINIUM PLATE 3 MM x 1500 MM NOT ANODIZED")):
        [mensagem] = mensagens(_par(invoice, pl), "item")
        assert "descrição" in mensagem, mensagem


def test_mesma_medida_com_palavra_diferente_e_so_aviso():
    """Acabamento, abreviação ou palavra a mais de cada lado: o código não sabe se é outro produto."""
    pares = (("STEEL COILS GALVANIZED 0.500x1000.000", "STEEL COILS PREPAINTED .500 MM x 1000.000 MM"),
             ("HOT ROLLED CARBON STEEL COILS 0.450x1100.000xCOIL-220/PO/SE",
              "HOT ROLLED CARBON STEEL COILS - GRADE 220 - PICKLED OILED - Slit Edge - .450 MM x 1100.000 MM - COIL"),
             ("PLASTIC FILM PE 0.05x1000", "PLASTIC FILM 0.05 MM x 1000 MM POLYESTER EMBOSSED"),
             ("STEEL SHEET CR 2x1000", "STEEL SHEET 2.0 MM x 1000 MM COATED RED"))
    for invoice, pl in pares:
        r = _par(invoice, pl)
        assert mensagens(r, "item") == [], (invoice, mensagens(r, "item"))
        assert len(_avisos_de_escrita(r)) == 1, invoice


def test_palavra_a_mais_de_um_lado_so_nao_acusa_nem_avisa():
    r = _par("COPPER TUBE 10x1", "COPPER TUBE TINNED 10 MM x 1 MM")
    assert mensagens(r, "item") == [] and _avisos_de_escrita(r) == []


def test_so_a_notacao_da_medida_muda_nao_acusa():
    r = rodar([doc("invoice", numero="8", itens=[item(None, "STEEL SHEET CR 2x1000 COIL", 3, "MT")]),
               doc("packing_list", numero="8", itens=[item(None, "STEEL SHEET CR 2 MM x 1000 MM COIL", 1, "PIECES")])])
    assert mensagens(r, "item") == []
