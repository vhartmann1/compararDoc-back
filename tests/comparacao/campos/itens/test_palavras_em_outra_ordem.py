"""Linha do PL sem código com as palavras da invoice em outra ordem: casa pela medida, palavras e quantidade."""

from tests.comparacao.apoio import doc, item, mensagens, rodar

INVOICE = [
    item("ZQ-NB-TM06", "Tambourine 06\" K-30 - Nimbo Series", 10),
    item("ZQ-NB-GG14", "Gong 14\" K-30 - Nimbo Series", 8),
    item("ZQ-NB-GG15", "Gong 15\" K-30 - Nimbo Series", 6),
    item("ZQ-NB-HH13", "Hi hat 13\" K-30 - Nimbo Series", 5),
]
PL = [
    item(None, "Nimbo series - 15'' Gong", 6, "PCS"),
    item(None, "Nimbo series - 13'' Hihat", 5, "PRS"),
    item(None, "Nimbo series - 6'' Tambourine", 10, "PCS"),
    item(None, "Nimbo series - 14'' Gong", 8, "PCS"),
]


def _itens(invoice, pl):
    return sorted(mensagens(rodar([doc("invoice", numero="1", itens=invoice),
                                   doc("packing_list", refs=["1"], itens=pl)]), "item"))


def _par(invoice, pl):
    return _itens([item("ZQ-1", invoice, 4)], [item(None, pl, 4, "PCS")])


def test_mesmas_palavras_em_outra_ordem_casam():
    assert _itens(INVOICE, PL) == []


def test_ordem_das_linhas_nao_muda_o_resultado():
    assert _itens(INVOICE[::-1], PL) == _itens(INVOICE, PL[::-1]) == []


def test_tamanho_diferente_nao_casa():
    assert _par("Gong 14\" K-30 - Nimbo Series", "Nimbo series - 15'' Gong")


def test_quantidade_diferente_nao_casa_pela_palavra():
    pl = [*PL[:3], item(None, "Nimbo series - 14'' Gong", 7, "PCS")]
    assert any("ZQ-NB-GG14" in m for m in _itens(INVOICE, pl))


def test_palavra_so_de_um_lado_nao_casa():
    assert _par("Plate 12\" Anodized Velo", "Velo - 12'' Plate NOT ANODIZED")
    assert _par("Plate 12\" with Grip Velo", "Velo - 12'' Plate without Grip")
    assert _par("Sheet 12\" PE Velo", "Velo - 12'' Sheet POLYESTER EMBOSSED")
    assert _par("Sheet 12\" Grade 430 Velo", "Velo - 12'' Sheet Grade 304")
    assert _par("Plate 12\" Velo Red", "Velo - 12'' Plate")


def test_codigos_diferentes_dos_dois_lados_nao_casam():
    assert _par("Gong 14\" K-30 Nimbo", "Nimbo - 14'' Gong K31")


def test_criterio_das_palavras():
    from app.services.comparacao.campos.itens.palavras_em_outra_ordem import mesmas_palavras
    assert mesmas_palavras("Hi hat 13\" K-30 - Nimbo Series", "Nimbo series - 13'' Hihat")
    assert not mesmas_palavras("Plate Anodized Velo", "Velo Plate NOT ANODIZED")
    assert not mesmas_palavras("Plate with Grip", "Plate without Grip")
    assert not mesmas_palavras("Sheet PE Velo", "Velo Sheet POLYESTER EMBOSSED")
    assert not mesmas_palavras("Sheet Grade 430", "Sheet Grade 304")
    assert not mesmas_palavras("Plate Velo Red", "Velo Plate")
    assert not mesmas_palavras("Gong K-30 Nimbo", "Nimbo Gong K31")
    assert not mesmas_palavras("Gong drilled K-30 Nimbo", "Nimbo Gong")
