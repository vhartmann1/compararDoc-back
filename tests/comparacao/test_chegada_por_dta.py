"""AWB que chega em Guarulhos/Viracopos com a invoice indicando SC: vem por DTA, aviso em vez de divergência."""

from tests.comparacao.apoio import campo, doc, rodar


def _aereo(destino_invoice, destino_awb, entrega=None, subtipo="AWB"):
    return rodar([doc("invoice", numero="1", destino=destino_invoice),
                  doc("packing_list", numero="1", destino=destino_invoice)],
                 [doc("conhecimento", subtipo=subtipo, destino=destino_awb, entrega=entrega)])


def _divergencias_de_destino(r):
    return [d for d in r.divergencias if d.campo == "porto_destino"]


def test_awb_em_guarulhos_e_invoice_em_itajai_vira_aviso_de_dta():
    r = _aereo("ITAJAI", "GUARULHOS")
    assert not _divergencias_de_destino(r)
    assert campo(r.comparacoes[0], "porto_destino").status == "OK"
    assert any("confirmar DTA" in a and "GUARULHOS" in a for a in r.avisos)


def test_awb_em_viracopos_pela_sigla_e_invoice_em_navegantes_vira_aviso():
    r = _aereo("Navegantes - SC, Brazil", "VCP")
    assert not _divergencias_de_destino(r)
    assert any("confirmar DTA" in a for a in r.avisos)


def test_invoice_em_joinville_tambem_e_santa_catarina():
    assert not _divergencias_de_destino(_aereo("JOINVILLE", "GRU"))


def test_awb_em_outro_aeroporto_continua_divergindo():
    r = _aereo("ITAJAI", "CONFINS")
    assert _divergencias_de_destino(r)
    assert not any("DTA" in a for a in r.avisos)


def test_invoice_fora_de_santa_catarina_continua_divergindo():
    assert _divergencias_de_destino(_aereo("CURITIBA", "GUARULHOS"))


def test_awb_com_entrega_em_outro_porto_de_sc_confere_pela_entrega_e_nao_pela_dta():
    r = _aereo("ITAJAI", "GUARULHOS", entrega="NAVEGANTES")
    assert _divergencias_de_destino(r)


def test_bl_maritimo_nao_entra_na_regra():
    assert _divergencias_de_destino(_aereo("ITAJAI", "SAO PAULO", subtipo="BL"))
