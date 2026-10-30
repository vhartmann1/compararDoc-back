"""Documentos que não entram na soma: outro tipo, proforma, resumo e conhecimento de saída."""

from app.tipos_de_arquivo import MEDIA_PDF, MEDIA_XLSX
from tests.comparacao.apoio import campo, doc, enviar, rodar


def test_arquivo_que_nao_e_invoice_pl_nem_conhecimento_gera_aviso():
    r = enviar(
        ("INV.pdf", MEDIA_PDF, [doc("invoice", 100, 110, numero="A1")]),
        ("COMPROVANTE.pdf", MEDIA_PDF, [doc("outro", subtipo="COMPROVANTE DE IMPORTACAO")]),
    )
    assert "COMPROVANTE.pdf não entrou na comparação: não é invoice, packing list nem conhecimento (COMPROVANTE DE IMPORTACAO)." in r.avisos


def test_proforma_lida_dentro_do_excel_nao_soma_com_a_invoice_comercial():
    r = enviar(
        ("PEDIDO.xlsx", MEDIA_XLSX, [
            doc("invoice", numero="PI-9", subtipo="PROFORMA", quantidade=(5000, "PCS"), pagina=None),
            doc("invoice", 30, 33, quantidade=(200, "PCS"), pagina=None),
            doc("packing_list", 30, 33, quantidade=(200, "PCS"), pagina=None),
        ]),
    )
    assert len(r.comparacoes) == 1
    assert campo(r.comparacoes[0], "quantidade").status == "OK"
    assert "Proforma PI-9 (PEDIDO.xlsx) não entrou na comparação: há invoice comercial." in r.avisos


def test_so_proforma_continua_sendo_comparada():
    r = enviar(
        ("PI.pdf", MEDIA_PDF, [doc("invoice", 30, 33, numero="PI-9", subtipo="PROFORMA")]),
        ("PL.pdf", MEDIA_PDF, [doc("packing_list", 30, 33, refs=["PI-9"])]),
    )
    assert campo(r.comparacoes[0], "peso_bruto").status == "OK"


def test_planilha_resumo_de_duas_invoices_sai_da_soma():
    r = enviar(
        ("INV1.pdf", MEDIA_PDF, [doc("invoice", 10, 11, numero="7001")]),
        ("INV2.pdf", MEDIA_PDF, [doc("invoice", 20, 22, numero="7002")]),
        ("RESUMO.xlsx", MEDIA_XLSX, [doc("invoice", 30, 33, numero="7001, 7002", pagina=None,
                                   internas=[("Peso líquido e bruto trocados no cabeçalho", "NET 33 / GROSS 30")])]),
        ("BL.pdf", MEDIA_PDF, [doc("conhecimento", None, 33, subtipo="BL", numero="B1", refs=["7001", "7002"])]),
    )
    assert "Invoice 7001, 7002 (RESUMO.xlsx) não entrou na comparação: é o resumo das outras invoices." in r.avisos
    assert campo(r.comparacoes[-1], "peso_bruto").status == "OK"
    assert any("trocados no cabeçalho" in d.mensagem for d in r.divergencias if d.categoria == "interna")


def test_proforma_em_dois_arquivos_e_conferida_por_dentro_uma_vez_com_o_proprio_nome():
    interna = [("Moeda da coluna (USD) diferente da do total (EUR)", "USD × EUR")]
    proforma = dict(numero="PI-9", subtipo="PROFORMA", internas=interna, quantidade=(900, "PCS"))
    r = enviar(
        ("PI.pdf", MEDIA_PDF, [doc("invoice", **proforma)]),
        ("PEDIDO.xlsx", MEDIA_XLSX, [doc("invoice", **proforma, pagina=None)]),
        ("INV.pdf", MEDIA_PDF, [doc("invoice", 30, 33, numero="C-1")]),
    )
    internas = [d.mensagem for d in r.divergencias if d.categoria == "interna"]
    assert internas == ["Proforma PI-9: Moeda da coluna (USD) diferente da do total (EUR)"]
    assert "Proforma PI-9 (PI.pdf, pág. 1) não entrou na comparação: há invoice comercial." in r.avisos


def test_conhecimento_de_exportacao_fica_fora_com_aviso():
    r = rodar(
        [doc("invoice", 1, 2, numero="1", origem="NINGBO", destino="ITAJAI"), doc("packing_list", 1, 2, numero="1")],
        [doc("conhecimento", 1, 2, subtipo="BL", numero="A", origem="NINGBO", destino="ITAJAI")],
        [doc("conhecimento", 5, 9, subtipo="BL", numero="B", origem="Itapoa - SC, Brazil", destino="SHANGHAI")],
    )
    assert [c.chave for c in r.comparacoes[0].colunas] == ["invoice", "packing_list", "conhecimento"]
    assert campo(r.comparacoes[0], "peso_bruto").status == "OK"
    assert any("BL B" in a and "exportação" in a for a in r.avisos)


def test_conhecimento_de_importacao_continua_entrando():
    r = rodar(
        [doc("invoice", 1, 2, numero="1"), doc("packing_list", 1, 2, numero="1")],
        [doc("conhecimento", 1, 2, subtipo="BL", numero="A", origem="SHANGHAI", destino="Itapoa - SC, Brazil")],
    )
    assert [c.chave for c in r.comparacoes[0].colunas] == ["invoice", "packing_list", "conhecimento"]
    assert not any("exportação" in a for a in r.avisos)


def test_unico_conhecimento_nunca_sai_mesmo_com_rota_estranha():
    for origem, destino in (("GRU", "VCP"), ("Viracopos", "CNF"), ("GRU", "BRAZIL"), ("Santos, Brazil", "Vila do Conde - PA")):
        r = rodar(
            [doc("invoice", 1, 2, numero="1"), doc("packing_list", 1, 2, numero="1")],
            [doc("conhecimento", 1, 2, subtipo="AWB", numero="A", origem=origem, destino=destino)],
        )
        assert [c.chave for c in r.comparacoes[0].colunas] == ["invoice", "packing_list", "conhecimento"], origem
        assert not any("exportação" in a for a in r.avisos)
