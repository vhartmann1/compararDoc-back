"""Cabeçalho × assinatura × vendedor × fabricante da invoice/PL: triangular é aviso, terceira empresa é interna."""

from tests.comparacao.apoio import doc, mensagens, rodar

FABRICA = "DELTA RUBBER WORKS CO.,LTD"
TRADING = "ORION PACIFIC TRADING LIMITED"
TERCEIRA = "NORTE ALFA COMERCIAL LTDA"


def _invoice(cabecalho=FABRICA, assinatura="ORION PACIFIC TRADING LTD", vendedor=TRADING, fabricante=FABRICA,
             tipo="invoice"):
    return doc(tipo, numero="TX-1", exportador=vendedor, fabricante=(fabricante,) if fabricante else None,
               assinatura=assinatura, cabecalho=cabecalho)


def _sobre_cabecalho(r):
    return [a for a in r.avisos if "cabeçalho" in a]


def test_cabecalho_do_fabricante_e_vendedor_assinando_e_so_aviso():
    r = rodar([_invoice(cabecalho="DELTA RUBBER WORKS CO., LTD.")])
    assert not mensagens(r, "interna")
    assert any("triangular" in a and "DELTA RUBBER WORKS" in a for a in _sobre_cabecalho(r))


def test_packing_list_com_o_mesmo_arranjo_tambem_e_so_aviso():
    r = rodar([_invoice(tipo="packing_list")])
    assert not mensagens(r, "interna")
    assert _sobre_cabecalho(r)


def test_cabecalho_de_uma_terceira_empresa_e_interna():
    r = rodar([_invoice(cabecalho=TERCEIRA)])
    assert [m for m in mensagens(r, "interna") if TERCEIRA in m and "cabeçalho" in m]
    assert not _sobre_cabecalho(r)


def test_terceira_empresa_assinando_e_interna():
    r = rodar([_invoice(assinatura=TERCEIRA)])
    assert [m for m in mensagens(r, "interna") if TERCEIRA in m and "assinad" in m]


def test_vendedor_igual_ao_fabricante_com_uma_trading_assinando_e_interna():
    r = rodar([_invoice(vendedor=FABRICA, assinatura=TRADING)])
    assert len(mensagens(r, "interna")) == 1
    assert not _sobre_cabecalho(r)


def test_tudo_da_mesma_empresa_nao_diz_nada():
    r = rodar([_invoice(cabecalho=TRADING, fabricante=TRADING)])
    assert not mensagens(r, "interna") and not _sobre_cabecalho(r)


def test_sem_cabecalho_nao_conclui_nada():
    r = rodar([_invoice(cabecalho=None, assinatura=TERCEIRA)])
    assert not mensagens(r, "interna") and not _sobre_cabecalho(r)


def test_sem_fabricante_declarado_nao_julga_o_cabecalho():
    r = rodar([_invoice(fabricante=None)])
    assert not mensagens(r, "interna") and not _sobre_cabecalho(r)


def test_sem_assinatura_nao_conclui_nada():
    r = rodar([_invoice(cabecalho=TERCEIRA, assinatura=None)])
    assert not mensagens(r, "interna") and not _sobre_cabecalho(r)


def test_nome_com_erro_de_digitacao_nao_vira_terceira_empresa():
    r = rodar([_invoice(assinatura="ORION PACIFC TRADING LTD", cabecalho=TRADING, fabricante=TRADING)])
    assert not mensagens(r, "interna")


def test_no_conhecimento_o_cabecalho_do_transportador_e_ignorado():
    linha = "MARE AZUL LINES"
    bl = doc("conhecimento", subtipo="BL", exportador=TRADING, fabricante=(FABRICA,), assinatura=linha, cabecalho=linha)
    r = rodar([bl])
    assert not mensagens(r, "interna") and not _sobre_cabecalho(r)


def test_fabricante_so_da_invoice_nao_serve_para_julgar_o_packing_list():
    pl = doc("packing_list", numero="TX-1", exportador=TRADING, assinatura=TRADING, cabecalho=TERCEIRA)
    r = rodar([_invoice(), pl])
    assert not [m for m in mensagens(r, "interna") if TERCEIRA in m]
