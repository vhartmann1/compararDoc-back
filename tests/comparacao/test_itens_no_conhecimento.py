from tests.comparacao.apoio import doc, item, mensagens, rodar
from tests.comparacao.cenarios import caso_1, caso_4_v3, caso_6_v3


def test_caso_1_bl_generico_so_aviso():
    r = caso_1(itens_bl=[item(None, "SKINCARE ESSENTIALS")])
    [comparacao] = r.itens
    assert [c.chave for c in comparacao.colunas] == ["invoice", "packing_list", "conhecimento"]
    assert all(l.valores["conhecimento"] is None for l in comparacao.linhas)
    assert comparacao.linhas[0].status == "OK"  # célula vazia do BL não é divergência
    assert all("ausente" not in l.diferencas for l in comparacao.linhas)
    assert mensagens(r, "item") == [  # as mesmas de antes, sem nada do BL
        "Item QB-TN-505: lote Invoice #LT2031C14-E × Packing List #LT2031C20-E",
        "Item QB-MS-312: validade Invoice 11/2025, 11/2028 × Packing List 11/2025",
    ]
    assert "BL descreve 'SKINCARE ESSENTIALS'; não foi possível relacionar aos itens." in r.avisos


def test_caso_4_awb_generico_no_consolidado_so_aviso():
    itens_par = (
        [item(None, "Synthetic Trail Running Shoes Model: Ridge-Path 2", 150, "PAIRS"),
         item(None, "Synthetic Indoor Soccer Shoes Model: Indoor-Ace X", 170, "PAIRS")],
        [item(None, "Synthetic Basketball Shoes Model: Jump-Shot 5", 120, "PAIRS"),
         item(None, "Synthetic Running Sandals Model: Summer-Lite", 80, "PAIRS")],
    )
    r = caso_4_v3(itens_par=itens_par, itens_awb=[item(None, "SYNTHETIC SHOES")])
    assert [c.comparacao_id for c in r.itens] == ["par-1", "par-2", "consolidado"]
    consolidado = r.itens[2]
    assert [c.chave for c in consolidado.colunas] == ["soma_invoices", "soma_packing_lists", "conhecimento"]
    assert len(consolidado.linhas) == 4
    assert all(l.status == "OK" and l.valores["conhecimento"] is None for l in consolidado.linhas)
    assert mensagens(r, "item") == []
    assert "Consolidado — AWB descreve 'SYNTHETIC SHOES'; não foi possível relacionar aos itens." in r.avisos


def test_caso_4_sem_itens_no_awb_nao_gera_consolidado_de_itens():
    itens_par = ([item("A", "Shoe A", 1, "PAIRS")], [item("B", "Shoe B", 1, "PAIRS")])
    r = caso_4_v3(itens_par=itens_par)
    assert [c.comparacao_id for c in r.itens] == ["par-1", "par-2"]


def test_caso_6_descricao_do_bl_diverge():
    r = caso_6_v3(itens_bl=[item(None, "POLIREX ZK 455")])
    [linha] = r.itens[0].linhas
    assert linha.valores["conhecimento"].descricao == "POLIREX ZK 455"
    assert linha.diferencas == ["descricao", "quantidade", "lote"]
    [divergencia] = [d for d in r.divergencias if d.categoria == "item"]
    assert divergencia.item_chave == "52871046"
    assert divergencia.mensagem.startswith(
        "Item 52871046: descrição Invoice POLIRMX HD 475 / 25 kg SA RESINA DE PVC × "
        "Packing List POLIREX YK 455 × BL POLIREX ZK 455;"
    )
    assert not any("descreve" in a for a in r.avisos)


def test_conhecimento_casa_por_codigo_e_compara_so_o_que_informa():
    r = rodar(
        [doc("invoice", numero="1", itens=[item("A1", "Widget", 10, "PCS", ["L1"]), item("B2", "Gadget", 5, "PCS")]),
         doc("packing_list", numero="1", itens=[item("A1", "Widget", 10, "PCS", ["L1"]), item("B2", "Gadget", 5, "PCS")])],
        [doc("conhecimento", subtipo="BL", itens=[item("A1", "Widget", 12, "PCS")])],
    )
    linhas = {l.chave: l for l in r.itens[0].linhas}
    assert linhas["A1"].diferencas == ["quantidade"]  # lote não informado no BL: não compara
    assert linhas["B2"].status == "OK" and linhas["B2"].valores["conhecimento"] is None
    assert mensagens(r, "item") == ["Item A1: quantidade BL 12 PCS × Invoice/Packing List 10 PCS"]


def test_conhecimento_com_descricao_que_serve_para_varios_itens_so_aviso():
    r = rodar(
        [doc("invoice", numero="1", itens=[item(None, "Synthetic Shoes Model: Trail-Max 10", 200, "PAIRS"),
                                           item(None, "Synthetic Shoes Model: Wind-Ride 500", 120, "PAIRS")]),
         doc("packing_list", numero="1", itens=[item(None, "Synthetic Shoes Model: Trail-Max 10", 200, "PAIRS"),
                                                item(None, "Synthetic Shoes Model: Wind-Ride 500", 120, "PAIRS")])],
        [doc("conhecimento", subtipo="AWB", itens=[item(None, "SYNTHETIC SHOES")])],
    )
    assert all(l.valores["conhecimento"] is None and l.status == "OK" for l in r.itens[0].linhas)
    assert not any("descreve" in a for a in r.avisos)  # 'Synthetic Shoes' começa a descrição dos dois itens


def test_descricao_generica_do_conhecimento_casado_pelo_codigo_nao_diverge():
    r = rodar(
        [doc("invoice", numero="1", itens=[item("A1", "Fio de polietileno 8000 dtex azul", 10, "KG")]),
         doc("packing_list", numero="1", itens=[item("A1", "Fio de polietileno 8000 dtex azul", 10, "KG")])],
        [doc("conhecimento", subtipo="BL", itens=[item("A1", "Synthetic yarn")])],
    )
    assert all(l.status == "OK" for i in r.itens for l in i.linhas)


def test_conhecimento_por_categoria_contida_nos_itens_nao_avisa():
    itens = [item("K1", "CABO USB TIPO-C 1M REF:K1", 10, "PCS"), item("K2", "CABO USB MICRO 2M REF:K2", 5, "PCS"),
             item("K3", "2 EM 1 SUPORTE DOBRAVEL REF:K3", 4, "PCS")]
    r = rodar(
        [doc("invoice", numero="1", itens=itens), doc("packing_list", numero="1", itens=itens)],
        [doc("conhecimento", subtipo="BL", itens=[item(None, "CABO USB (DATA CABLE)"),
                                                  item(None, "SUPORTE DOBRAVEL (HOLDER)"),
                                                  item(None, "CABO HDMI (VIDEO CABLE)"), item(None, "CABOS")])],
    )
    assert mensagens(r, "item") == []
    assert [a for a in r.avisos if "descreve" in a] == [
        "BL descreve 'CABO HDMI (VIDEO CABLE)'; não foi possível relacionar aos itens.",
        "BL descreve 'CABOS'; não foi possível relacionar aos itens.",
    ]
