"""Nº da invoice e PO quase iguais com um lado escaneado: aviso de leitura incerta, não divergência."""

from tests.comparacao.apoio import campo, doc, mensagens, rodar


def _po(bl_po, escaneados):
    return rodar(
        [doc("invoice", numero="INV1", po="PO 77104523"), doc("packing_list", numero="INV1", po="77104523")],
        [doc("conhecimento", subtipo="BL", po=bl_po)],
        escaneados=escaneados,
    )


def test_po_com_um_digito_trocado_no_bl_escaneado_e_aviso():
    r = _po("77184523", [False, True])
    assert not [m for m in mensagens(r, "comparacao") if m.startswith("PO")]
    assert campo(r.comparacoes[0], "po").status == "INSUFICIENTE"
    assert ("PO: BL 77184523 × Invoice/Packing List PO 77104523; BL escaneado, "
            "pode ser leitura — conferir na imagem.") in r.avisos


def test_po_com_digito_trocado_em_documentos_digitais_continua_divergente():
    r = _po("77184523", [False, False])
    assert "PO: BL 77184523 × Invoice/Packing List PO 77104523" in mensagens(r, "comparacao")


def test_sem_saber_se_e_scan_continua_divergente():
    r = _po("77184523", [None, None])
    assert "PO: BL 77184523 × Invoice/Packing List PO 77104523" in mensagens(r, "comparacao")


def test_tres_caracteres_diferentes_continua_divergente_mesmo_escaneado():
    r = _po("77189593", [False, True])
    assert "PO: BL 77189593 × Invoice/Packing List PO 77104523" in mensagens(r, "comparacao")


def test_numero_da_invoice_com_letra_trocada_na_pl_escaneada_e_aviso():
    r = rodar([doc("invoice", numero="KX-305512")], [doc("packing_list", numero="KX-305572")],
              escaneados=[False, True])
    assert not mensagens(r, "comparacao")
    assert any(a.startswith("Nº da invoice: ") and "Packing List escaneado" in a for a in r.avisos)


def test_numero_a_mais_de_um_lado_continua_divergente():
    r = rodar([doc("invoice", numero="1", po="551203")], [doc("packing_list", numero="1", po="551203 / 551204")],
              escaneados=[True, True])
    assert any(m.startswith("PO:") for m in mensagens(r, "comparacao"))
