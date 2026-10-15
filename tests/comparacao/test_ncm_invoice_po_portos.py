from tests.comparacao.apoio import campo, doc, rodar, tres_ok


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
