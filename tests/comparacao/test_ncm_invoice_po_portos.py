from tests.comparacao.apoio import campo, doc, mensagens, rodar, tres_ok


def test_ncm_hs_compara_6_digitos():
    r = tres_ok(ncms=["HS 390110"])
    assert campo(r.comparacoes[0], "ncm").status == "OK"
    assert any("6 primeiros dígitos" in a for a in r.avisos)


def test_ncm_divergente():
    r = tres_ok(ncms=["3901.20.10"])
    assert r.divergencias[0].mensagem == "NCM: BL 3901.20.10 × Invoice/Packing List 3901.10.10"


def test_ncm_posicao_redundante_no_mesmo_documento_e_ignorada():
    r = tres_ok(ncms=["3901", "3901.10.10"])
    ncm = campo(r.comparacoes[0], "ncm")
    assert ncm.status == "OK"
    assert ncm.valores["conhecimento"].exibicao == "3901.10.10"
    assert not any("primeiros dígitos" in a for a in r.avisos)


def test_po_com_e_sem_o_rotulo_confere():
    r = rodar([doc("invoice", numero="1", po="PO 15 March"), doc("packing_list", numero="1", po="15 March")])
    assert campo(r.comparacoes[0], "po").status == "OK"


def test_porto_e_terminal_com_outro_nome_conferem():
    r = rodar([
        doc("invoice", numero="1", origem="Tianjin, China"),
        doc("packing_list", numero="1", origem="TIANJIN XINGANG"),
    ], [doc("conhecimento", subtipo="BL", origem="XINGANG")])
    assert campo(r.comparacoes[0], "porto_origem").status == "OK"
    valores = campo(r.comparacoes[0], "porto_origem").valores
    assert [valores[k].exibicao for k in ("invoice", "packing_list", "conhecimento")] == ["TIANJIN", "TIANJIN XINGANG", "XINGANG"]


def test_po_com_nome_do_cliente_na_frente_confere():
    r = rodar([doc("invoice", numero="1", po="114/26"), doc("packing_list", numero="1", po="ACME 114/26")])
    assert campo(r.comparacoes[0], "po").status == "OK"


def test_po_com_numero_diferente_continua_divergindo():
    r = rodar([doc("invoice", numero="1", po="HBPX41357"), doc("packing_list", numero="1", po="HBPX41458")])
    assert campo(r.comparacoes[0], "po").status == "DIVERGENTE"


def test_destino_da_invoice_com_alternativa_confere_com_qualquer_uma():
    r = rodar([doc("invoice", numero="1", destino="ITAJAI OR NAVEGANTES"), doc("packing_list", refs=["1"]),
               doc("conhecimento", subtipo="BL", numero="B1", refs=["1"], destino="NAVEGANTES")])
    porto = campo(r.comparacoes[0], "porto_destino")
    assert porto.status == "OK"
    assert porto.valores["invoice"].exibicao == "ITAJAI ou NAVEGANTES"


def test_destino_da_invoice_em_rota_confere_com_o_fim_dela():
    r = rodar([doc("invoice", numero="1", destino="Itajai, Brazil to Navegantes, Brazil"), doc("packing_list", refs=["1"]),
               doc("conhecimento", subtipo="BL", numero="B1", refs=["1"], destino="NAVEGANTES")])
    assert campo(r.comparacoes[0], "porto_destino").status == "OK"


def test_origem_confere_com_o_local_de_recebimento_do_bl_no_transbordo():
    r = rodar([doc("invoice", numero="1", origem="KEELUNG", incoterm=("FOB", "KEELUNG")), doc("packing_list", refs=["1"]),
               doc("conhecimento", subtipo="BL", numero="B1", refs=["1"], origem="BUSAN", recebimento="KEELUNG")])
    porto = campo(r.comparacoes[0], "porto_origem")
    assert porto.status == "OK"
    assert porto.valores["conhecimento"].exibicao == "BUSAN (recebimento: KEELUNG)"
    assert not mensagens(r, "coerencia")


def test_duas_invoices_de_origens_diferentes_contra_bl_de_uma_so_continua_divergindo():
    r = rodar(
        [doc("invoice", 10, 11, numero="1", origem="SANTOS"), doc("packing_list", 10, 11, refs=["1"])],
        [doc("invoice", 20, 22, numero="2", origem="RIO GRANDE"), doc("packing_list", 20, 22, refs=["2"])],
        [doc("conhecimento", None, 33, subtipo="BL", numero="B1", refs=["1", "2"], origem="SANTOS")],
    )
    consolidado = r.comparacoes[-1]
    assert campo(consolidado, "porto_origem").status == "DIVERGENTE"


def test_origem_escrita_como_rota_vale_so_pelo_comeco():
    r = rodar([doc("invoice", numero="1", origem="SANTOS to RIO GRANDE"), doc("packing_list", refs=["1"]),
               doc("conhecimento", subtipo="BL", numero="B1", refs=["1"], origem="RIO GRANDE")])
    assert campo(r.comparacoes[0], "porto_origem").status == "DIVERGENTE"


def test_terminal_de_itajai_no_incoterm_confere_com_a_descarga_em_itajai():
    r = rodar([doc("invoice", numero="1", incoterm=("CPT", "BARRA DO RIO")), doc("packing_list", refs=["1"]),
               doc("conhecimento", subtipo="CRT", numero="C1", refs=["1"], destino="ITAJAI")])
    assert not mensagens(r, "coerencia")
