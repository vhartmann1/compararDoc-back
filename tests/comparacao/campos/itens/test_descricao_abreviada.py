"""Descrição abreviada: só o modelo, começo da outra ou só medidas a mais no fim; o resto continua divergindo."""

from tests.comparacao.apoio import doc, item, mensagens, rodar


def _divergencias(invoice, pl, ref_invoice=None, ref_pl=None, codigo_invoice=None):
    r = rodar(
        [doc("invoice", numero="1", itens=[item(codigo_invoice, invoice, 4, "PCS", referencia=ref_invoice)]),
         doc("packing_list", refs=["1"], itens=[item(None, pl, 4, "PCS", referencia=ref_pl)])],
    )
    return mensagens(r, "item")


def test_pl_so_com_o_modelo_que_comeca_a_descricao_da_invoice_confere():
    assert not _divergencias("QX-77 - medidor de bancada", "QX-77", "QX-77", "QX-77", codigo_invoice="QX-77")
    assert not _divergencias("QX-77 - medidor de bancada", "QX-77", ref_pl="QX-77")


def test_marca_lida_como_referencia_no_documento_mais_curto_nao_impede_o_comeco():
    assert not _divergencias("Talmex Sensor de carga, Modelo TS100-01, faixa de 9 MN e completo",
                             "Talmex Sensor de carga Modelo", "TS100-01", "Talmex")


def test_pl_com_medidas_no_fim_confere():
    assert not _divergencias("ANTI GLARE CLIP", "Anti glare clip 30*12.5*40CM")


def test_modelo_diferente_ou_so_parecido_diverge():
    assert _divergencias("QX-770 - medidor de bancada", "QX-77", ref_pl="QX-77")
    assert _divergencias("QX-78 - medidor de bancada", "QX-77", ref_pl="QX-77")


def test_abreviacao_nao_junta_produtos_diferentes():
    assert _divergencias("ALUMINIUM PLATE ANODIZED 3x1500", "ALUMINIUM PLATE 3 MM x 1500 MM NOT ANODIZED")
    assert _divergencias("PLASTIC FILM PE 0.05x1000", "PLASTIC FILM 0.05 MM x 1000 MM POLYESTER EMBOSSED")
    assert _divergencias("STAINLESS STEEL COIL GRADE 430", "STAINLESS STEEL COIL GRADE 304 2x1000")
    assert _divergencias("Talmex Sensor de carga, Modelo TS100-01", "Talmex Sensor de carga, Modelo TS200-01",
                         "TS100-01", "TS200-01")


def test_medidas_no_fim_com_palavra_a_mais_do_outro_lado_diverge():
    for com_medida, outra in (("STEEL PIPE SEAMLESS 50*3*6000MM", "STEEL PIPE SEAMLESS GALVANIZED"),
                              ("RUBBER SEAL RING 20X30", "RUBBER SEAL RING KIT"),
                              ("LED PANEL LIGHT 60*60", "LED PANEL LIGHT DRIVER")):
        assert _divergencias(outra, com_medida), (com_medida, outra)


def test_referencia_da_curta_tem_de_ser_palavra_inteira_da_longa():
    assert _divergencias("Talmex Sensor de carga Modelo BX10 de 9 MN", "Talmex Sensor de carga Modelo", "BX10", "X1")
    assert _divergencias("Talmex Sensor de carga Modelo TS100-01 de 9 MN", "Talmex Sensor de carga Modelo",
                         "TS100-01", "TS1")


def test_numero_sem_referencia_nao_e_modelo():
    assert _divergencias("2024 KIT FERRAMENTAS", "2024")
