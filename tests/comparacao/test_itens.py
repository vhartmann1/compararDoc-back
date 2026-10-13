from tests.comparacao.apoio import campo, doc, item, mensagens, rodar
from tests.comparacao.cenarios import caso_1, caso_6_v3


def test_caso_1_itens():
    r = caso_1()
    assert len(r.itens) == 1
    linhas = {l.chave: l for l in r.itens[0].linhas}
    assert list(linhas) == ["QB-SR-102", "QB-TN-505", "OA-UV-088", "QB-MS-312"]
    assert linhas["QB-SR-102"].status == "OK"
    assert linhas["QB-TN-505"].diferencas == ["lote"]
    # invoice 500 + 100 agrupados = 600 do PL; os lotes batem, a validade não
    assert linhas["QB-MS-312"].diferencas == ["validade"]
    assert linhas["QB-MS-312"].valores["invoice"].quantidade == "600 PCS"
    assert mensagens(r, "item") == [
        "Item QB-TN-505: lote Invoice #LT2031C14-E × Packing List #LT2031C20-E",
        "Item QB-MS-312: validade Invoice 11/2025, 11/2028 × Packing List 11/2025",
    ]
    assert [d.item_chave for d in r.divergencias if d.categoria == "item"] == ["QB-TN-505", "QB-MS-312"]
    assert all(d.item_chave is None for d in r.divergencias if d.categoria != "item")


def test_caso_6_itens_e_quantidade():
    r = caso_6_v3()
    unica = r.comparacoes[0]
    assert campo(unica, "quantidade").status == "DIVERGENTE"  # 24 TO × 24.000 TONS
    [linha] = r.itens[0].linhas
    assert linha.chave == "52871046"
    assert linha.diferencas == ["descricao", "quantidade", "lote"]
    [msg] = mensagens(r, "item")
    assert msg.startswith("Item 52871046: descrição Invoice POLIRMX HD 475")
    assert ("quantidade Invoice 24 TO × Packing List 24.000 TONS — provável unidade errada: "
            "24.000 TONS equivale a 24 t se for kg") in msg
    assert "lote Invoice 7713904 × Packing List 4K0518206" in msg
    assert any("provável unidade errada" in m for m in mensagens(r, "comparacao") if m.startswith("Quantidade"))
    assert mensagens(r, "interna") == ["Packing List 48273916: Quantidade em toneladas incompatível com as bolsas"]


def test_item_so_de_um_lado_e_casamento_por_descricao():
    r = rodar([
        doc("invoice", numero="1", itens=[item(None, "Synthetic Trail Running Shoes Model: Ridge-Path 2.", 150, "PAIRS"),
                                          item(None, "Synthetic Indoor Soccer Shoes Model: Indoor-Ace X.", 50, "PAIRS"),
                                          item(None, "Cycling socks", 10, "PCS")]),
        doc("packing_list", numero="1", itens=[item(None, "Synthetic Indoor Soccer Shoes Model: Indoor-Ace X", 50, "pair"),
                                               item(None, "Synthetic Trail Running Shoes Model: Ridge-Path 2", 150, "PRS")]),
    ])
    linhas = r.itens[0].linhas
    assert [l.status for l in linhas] == ["OK", "OK", "DIVERGENTE"]
    assert linhas[2].diferencas == ["ausente"]
    assert mensagens(r, "item") == ["Item Cycling socks: só na Invoice"]


def test_chave_do_item_nao_repete_quando_a_descricao_so_difere_no_fim():
    parafuso = "PARAFUSO SEXTAVADO (HEX BOLT) MARCA:ACME ACABAMENTO: ZINCADO CLASSE: 8.8 MEDIDA:{} PASSO: {}"
    itens = [item(None, parafuso.format("M8X40", 1), 500, "BOXES"), item(None, parafuso.format("M10X60", 2), 500, "BOXES")]
    r = rodar([doc("invoice", numero="1", itens=itens), doc("packing_list", numero="1", itens=itens)])
    chaves = [l.chave for l in r.itens[0].linhas]
    assert chaves == [
        "PARAFUSO SEXTAVADO (HEX… MEDIDA:M8X40 PASSO: 1",
        "PARAFUSO SEXTAVADO (HEX… MEDIDA:M10X60 PASSO: 2",
    ]


def test_chave_do_item_ganha_numero_de_ordem_quando_a_descricao_e_identica():
    itens = [item(None, "Parafuso", 10, "PCS", lotes=["L1"]), item(None, "Parafuso", 20, "PCS", lotes=["L2"]),
             item(None, "Porca", 5, "PCS")]
    r = rodar([doc("invoice", numero="1", itens=itens), doc("packing_list", numero="1", itens=itens)])
    assert [l.chave for l in r.itens[0].linhas] == ["Parafuso (1)", "Parafuso (2)", "Porca"]


def test_referencia_diferente_por_uma_letra_diverge():
    # Invoice = BL (XC); só o PL diz WC — similaridade das descrições é alta, mas a referência difere
    desc = "POLYVINYL CHLORIDE RESIN POLIREX {} 455 / 25 kg SA"
    r = rodar(
        [doc("invoice", numero="1", itens=[item("52871046", desc.format("ZK"), 24, "TON", referencia="POLIREX ZK 455")]),
         doc("packing_list", numero="1", itens=[item("52871046", desc.format("YK"), 24, "TON", referencia="POLIREX YK 455")])],
        [doc("conhecimento", subtipo="BL", itens=[item(None, "POLIREX ZK 455 - PVC RESIN", referencia="POLIREX ZK 455")])],
    )
    [linha] = r.itens[0].linhas
    assert linha.valores["conhecimento"] is not None
    assert linha.diferencas == ["descricao"]
    [msg] = mensagens(r, "item")
    assert "Packing List" in msg and "YK 455" in msg and "ZK 455" in msg


def test_referencia_igual_ou_sem_marca_nao_diverge_e_sem_referencia_usa_similaridade():
    r = rodar(
        [doc("invoice", numero="1", itens=[item("A", "PVC resin Polirex ZK-455", 1, "TON", referencia="Polirex ZK-455"),
                                           item("B", "Synthetic Shoes Model: Trail-Max 10", 5, "PAIRS")]),
         doc("packing_list", numero="1", itens=[item("A", "PVC RESIN ZK 455", 1, "TON", referencia="ZK 455"),
                                                item("B", "Synthetic Shoes Model Trail-Max 10", 5, "PAIRS",
                                                     referencia="Trail-Max 10")])],
    )
    assert [l.status for l in r.itens[0].linhas] == ["OK", "OK"]


def test_referencias_com_numero_diferente_divergem():
    r = rodar(
        [doc("invoice", numero="1", itens=[item("B", "Shoes Trail-Max 10", 5, "PAIRS", referencia="Trail-Max 10")]),
         doc("packing_list", numero="1", itens=[item("B", "Shoes Trail-Max 100", 5, "PAIRS", referencia="Trail-Max 100")])],
    )
    assert r.itens[0].linhas[0].diferencas == ["descricao"]
