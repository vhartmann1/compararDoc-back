from pathlib import Path

import pytest

from app.schemas import ArquivoEntrada, ExtracaoArquivo
from app.services.comparacao import comparar
from app.services.comparacao.escolha_dos_documentos import revisao_pelo_nome
from tests.comparacao.apoio import campo, doc, item, rodar
from tests.comparacao.cenarios import caso_4


def test_documento_faltando_incompleto():
    r = rodar([doc("invoice", 1, 2, ["39011010"], numero="1"), doc("packing_list", 1, 2, ["39011010"], numero="1")])
    assert r.status == "INCOMPLETO"
    assert any("Conhecimento" in a for a in r.avisos)


def test_prioridade_de_versao_mesmo_numero():
    r = rodar(
        [doc("invoice", 1, 2, numero="1"), doc("packing_list", 1, 2, numero="1")],
        [doc("conhecimento", 1, 2, subtipo="BL", numero="BL9", versao="original")],
        [doc("conhecimento", 1, 3, subtipo="BL", numero="BL9", versao="draft")],
    )
    conhecimentos = [d for d in r.documentos if d.tipo == "conhecimento"]
    assert len(conhecimentos) == 1 and conhecimentos[0].versao == "original"
    assert campo(r.comparacoes[0], "peso_bruto").status == "OK"
    assert any("Mais de um documento BL BL9" in a for a in r.avisos)


def test_conhecimentos_com_numeros_diferentes_viram_colunas():
    r = rodar(
        [doc("invoice", 1, 2, numero="1"), doc("packing_list", 1, 2, numero="1")],
        [doc("conhecimento", 1, 2, subtipo="BL", numero="A"), doc("conhecimento", 1, 2, subtipo="BL", numero="B")],
    )
    assert [c.chave for c in r.comparacoes[0].colunas] == ["invoice", "packing_list", "conhecimento", "conhecimento_2"]


def test_pareamento_forcado_gera_aviso_e_pl_sem_referencia_usa_proprio_numero():
    r = rodar([doc("invoice", 1, 2, numero="KTR27393803"), doc("packing_list", 1, 2, numero="KTR27393806")])
    assert [c.chave for c in r.comparacoes[0].colunas] == ["invoice", "packing_list"]
    assert any("não cita o número da invoice" in a for a in r.avisos)
    # PL sem referência usa o próprio número (caso 1: KTR27393806 × KTR27393803)
    assert campo(r.comparacoes[0], "numero_invoice").status == "DIVERGENTE"
    assert "Nº da invoice: Invoice KTR27393803 × Packing List KTR27393806" in [d.mensagem for d in r.divergencias]


def test_caso_4_estrutura():
    r = caso_4()
    assert [c.id for c in r.comparacoes] == ["par-1", "par-2", "consolidado"]
    consolidado = r.comparacoes[2]
    assert [c.chave for c in consolidado.colunas] == ["soma_invoices", "soma_packing_lists", "conhecimento"]
    assert [c.rotulo for c in consolidado.colunas] == ["Soma das 2 invoices", "Soma dos 2 packing lists", "AWB 123-4567 8901"]
    assert consolidado.titulo == "Soma das 2 invoices × Soma dos 2 packing lists × AWB 123-4567 8901"
    assert r.status == "DIVERGENTE"


def test_documentos_sem_numero_e_com_totais_diferentes_sao_documentos_diferentes():
    r = rodar(
        [doc("invoice", 100, 110, numero="A1"), doc("packing_list", 100, 110, refs=["A1"])],
        [doc("invoice", 50, 60, numero="B2"), doc("packing_list", 50, 60, refs=["B2"])],
    )
    assert not any("Mais de um documento" in a for a in r.avisos)
    assert campo(r.comparacoes[0], "peso_bruto").status == "OK"


def test_o_mesmo_documento_sem_numero_enviado_duas_vezes_conta_uma():
    pl = doc("packing_list", 100, 110, refs=["A1"])
    r = rodar([doc("invoice", 100, 110, numero="A1"), pl], [pl])
    assert any("Mais de um documento Packing List" in a for a in r.avisos)


def test_invoice_e_packing_list_com_o_mesmo_numero_e_series_diferentes_formam_par():
    r = rodar([doc("invoice", 100, 110, numero="FT A26/000123"), doc("packing_list", 100, 110, numero="GR A26/000123")])
    assert not any("sem packing list" in a or "sem invoice" in a for a in r.avisos)
    assert campo(r.comparacoes[0], "numero_invoice").status != "DIVERGENTE"
    assert campo(r.comparacoes[0], "peso_bruto").status == "OK"


def test_numero_proprio_do_packing_list_nao_vira_divergencia_de_invoice():
    r = rodar([doc("invoice", 100, 110, numero="91234567"), doc("packing_list", 100, 110, numero="80765432")])
    assert campo(r.comparacoes[0], "numero_invoice").status != "DIVERGENTE"


def test_mesmo_documento_em_dois_formatos_um_sem_numero_conta_uma_vez():
    r = rodar(
        [doc("invoice", 100, 110, numero="A1", volumes=(20, "CTNS")), doc("packing_list", 100, 110, volumes=(20, "CTNS"))],
        [doc("invoice", 100, 110, volumes=(20, "CARTONS")), doc("packing_list", 100, 110, volumes=(20, "CARTONS"))],
    )
    assert campo(r.comparacoes[0], "peso_bruto").status == "OK"
    assert any("Mais de um documento Invoice" in a for a in r.avisos)


@pytest.mark.parametrize(
    ("antigo", "revisado"),
    [
        ("CI 001.pdf", "CI 001 REV-1.pdf"),
        ("PL 001 REV.1.pdf", "PL 001 REV.2.pdf"),
        ("HBL DRAFT.pdf", "HBL DRAFT (2 - ajustado).pdf"),
        ("INVOICE.pdf", "INVOICE REVISED.xlsx"),
        ("OHBL.pdf", "OHBL final.pdf"),
    ],
)
def test_revisao_pelo_nome_do_arquivo(antigo, revisado):
    assert revisao_pelo_nome(revisado) > revisao_pelo_nome(antigo)


def test_nome_com_rev_no_meio_de_palavra_nao_e_revisao():
    assert revisao_pelo_nome("PREVIEW BREVE.pdf") == (0, 0)


def _enviar(*arquivos_e_docs):
    """(nome do arquivo, media_type, documentos) na ordem do envio."""
    entradas = []
    for i, (nome, media, docs) in enumerate(arquivos_e_docs):
        arquivo = ArquivoEntrada(id=f"a{i}", nome=nome, caminho=Path(f"/tmp/{nome}"), media_type=media)
        entradas.append((arquivo, ExtracaoArquivo(documentos=docs)))
    return comparar(entradas)


PDF, XLSX = "application/pdf", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLS = "application/vnd.ms-excel"


@pytest.mark.parametrize("pdf_primeiro", [True, False])
def test_mesmo_documento_em_pdf_e_excel_usa_o_pdf_em_qualquer_ordem(pdf_primeiro):
    pdf = ("CI.pdf", PDF, [doc("invoice", 100, 110, ["69101000"], numero="A1")])
    excel = ("CI.xlsx", XLSX, [doc("invoice", 100, 110, ["39221000"], numero="A1")])
    pl = ("PL.pdf", PDF, [doc("packing_list", 100, 110, refs=["A1"])])
    r = _enviar(*([pdf, excel] if pdf_primeiro else [excel, pdf]), pl)
    assert any("usado CI.pdf (original, pág. 1), por ser o PDF (vale mais que Excel ou Word)" in a for a in r.avisos)
    assert campo(r.comparacoes[0], "ncm").valores["invoice"].exibicao == "6910.10.00"


def test_versao_vale_mais_que_o_formato():
    r = _enviar(
        ("INV.xlsx", XLSX, [doc("invoice", 100, 110, numero="A1", versao="draft")]),
        ("INV.pdf", PDF, [doc("invoice", 100, 110, numero="A1", versao="original")]),
    )
    assert any("usado INV.pdf (original, pág. 1), pela versão lida no documento" in a for a in r.avisos)


def test_campo_que_falta_no_documento_usado_vem_da_duplicata():
    r = _enviar(
        ("CI.xlsx", XLSX, [doc("invoice", 100, 110, ["69101000"], numero="A1")]),
        ("CI.pdf", PDF, [doc("invoice", 100, 110, numero="A1")]),
        ("PL.pdf", PDF, [doc("packing_list", 100, 110, ["69101000"], refs=["A1"])]),
    )
    ncm = campo(r.comparacoes[0], "ncm")
    assert ncm.status == "OK"
    assert ncm.valores["invoice"].arquivo_id == "a0"
    assert "NCM de Invoice A1 tirado de CI.xlsx (o arquivo usado não traz)." in r.avisos


def test_proforma_com_o_numero_da_invoice_nao_vence_a_invoice():
    r = _enviar(
        ("INVOICE.pdf", PDF, [doc("invoice", 100, 110, numero="A1")]),
        ("PROFORMA INVOICE.pdf", PDF, [doc("invoice", 100, 110, numero="A1")]),
    )
    assert any("usado INVOICE.pdf (original, pág. 1), porque o outro é proforma" in a for a in r.avisos)


def test_arquivo_que_nao_e_invoice_pl_nem_conhecimento_gera_aviso():
    r = _enviar(
        ("INV.pdf", PDF, [doc("invoice", 100, 110, numero="A1")]),
        ("COMPROVANTE.pdf", PDF, [doc("outro", subtipo="COMPROVANTE DE IMPORTACAO")]),
    )
    assert "COMPROVANTE.pdf não entrou na comparação: não é invoice, packing list nem conhecimento (COMPROVANTE DE IMPORTACAO)." in r.avisos


DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_rascunho_em_word_e_pdf_final_do_mesmo_pl_contam_uma_vez_com_aviso_dos_totais():
    linha = [item(None, "ARAME DE ACO 2MM BOBINA 10KG", 300, "KG")]
    r = _enviar(
        ("INV.pdf", PDF, [doc("invoice", 300, numero="X-77", itens=linha)]),
        ("RASCUNHO.docx", DOCX, [doc("packing_list", 300, 330, refs=["X-77"], volumes=(1, "PALLET"), itens=linha)]),
        ("PL.pdf", PDF, [doc("packing_list", 300, 326, refs=["X-77"], volumes=(1, "PALLET"), itens=linha)]),
        ("AWB.pdf", PDF, [doc("conhecimento", None, 326, subtipo="AWB", numero="999-1", refs=["X-77"], volumes=(1, "PALLET"))]),
    )
    assert len(r.comparacoes) == 1
    assert campo(r.comparacoes[0], "peso_bruto").status == "OK"
    assert any("Mais de um documento Packing List" in a and "peso bruto 326 KG × 330 KG" in a for a in r.avisos)


def test_dois_pl_da_mesma_invoice_com_itens_diferentes_continuam_separados():
    r = _enviar(
        ("INV.pdf", PDF, [doc("invoice", 300, numero="X-77")]),
        ("PL1.pdf", PDF, [doc("packing_list", 100, 110, refs=["X-77"], itens=[item("A1", "PECA A", 10)])]),
        ("PL2.pdf", PDF, [doc("packing_list", 200, 220, refs=["X-77"], itens=[item("B2", "PECA B", 20)])]),
    )
    assert not any("Mais de um documento Packing List" in a for a in r.avisos)


def test_proforma_lida_dentro_do_excel_nao_soma_com_a_invoice_comercial():
    r = _enviar(
        ("PEDIDO.xlsx", XLSX, [
            doc("invoice", numero="PI-9", subtipo="PROFORMA", quantidade=(5000, "PCS"), pagina=None),
            doc("invoice", 30, 33, quantidade=(200, "PCS"), pagina=None),
            doc("packing_list", 30, 33, quantidade=(200, "PCS"), pagina=None),
        ]),
    )
    assert len(r.comparacoes) == 1
    assert campo(r.comparacoes[0], "quantidade").status == "OK"
    assert "Proforma PI-9 (PEDIDO.xlsx) não entrou na comparação: há invoice comercial." in r.avisos


def test_so_proforma_continua_sendo_comparada():
    r = _enviar(
        ("PI.pdf", PDF, [doc("invoice", 30, 33, numero="PI-9", subtipo="PROFORMA")]),
        ("PL.pdf", PDF, [doc("packing_list", 30, 33, refs=["PI-9"])]),
    )
    assert campo(r.comparacoes[0], "peso_bruto").status == "OK"


def test_linhas_repetidas_com_e_sem_quantidade_nao_derrubam_a_escolha():
    linhas = [item(None, "PERFIL DE ALUMINIO", 10, "PCS"), item(None, "PERFIL DE ALUMINIO")]
    r = _enviar(
        ("INV.pdf", PDF, [doc("invoice", 100, numero="X-77")]),
        ("PL.docx", DOCX, [doc("packing_list", 100, 110, refs=["X-77"], itens=linhas)]),
        ("PL.pdf", PDF, [doc("packing_list", 100, 111, refs=["X-77"], itens=linhas)]),
    )
    assert any("Mais de um documento Packing List" in a for a in r.avisos)


def test_rascunho_pelo_nome_perde_para_o_original_com_os_mesmos_totais():
    r = _enviar(
        ("CI ORIGINAL.pdf", PDF, [doc("invoice", 100, 110, versao="desconhecida")]),
        ("CI DRAFT.pdf", PDF, [doc("invoice", 100, 110, versao="desconhecida")]),
    )
    usado = "usado CI ORIGINAL.pdf (pág. 1), pelo nome do arquivo (original × rascunho ou cópia)"
    assert any(usado in a for a in r.avisos)


def test_planilha_resumo_de_duas_invoices_sai_da_soma():
    r = _enviar(
        ("INV1.pdf", PDF, [doc("invoice", 10, 11, numero="7001")]),
        ("INV2.pdf", PDF, [doc("invoice", 20, 22, numero="7002")]),
        ("RESUMO.xlsx", XLSX, [doc("invoice", 30, 33, numero="7001, 7002", pagina=None,
                                   internas=[("Peso líquido e bruto trocados no cabeçalho", "NET 33 / GROSS 30")])]),
        ("BL.pdf", PDF, [doc("conhecimento", None, 33, subtipo="BL", numero="B1", refs=["7001", "7002"])]),
    )
    assert "Invoice 7001, 7002 (RESUMO.xlsx) não entrou na comparação: é o resumo das outras invoices." in r.avisos
    assert campo(r.comparacoes[-1], "peso_bruto").status == "OK"
    assert any("trocados no cabeçalho" in d.mensagem for d in r.divergencias if d.categoria == "interna")


def test_mesmo_pl_lido_com_as_palavras_em_outra_ordem_conta_uma_vez():
    a = [item(None, "PAPEL TERMICO 48 GSM ROLO 80MM", 1000, "M2")]
    b = [item(None, "PAPEL TERMICO ROLO 80MM 48 GSM", 1000, "M2")]
    r = _enviar(
        ("INV.pdf", PDF, [doc("invoice", 500, 520, numero="X-9")]),
        ("PL A.pdf", PDF, [doc("packing_list", 500, 520, refs=["X-9"], itens=a)]),
        ("PL B.pdf", PDF, [doc("packing_list", 490, 520, refs=["X-9"], itens=b)]),
    )
    assert any("Mais de um documento Packing List" in a for a in r.avisos)


@pytest.mark.parametrize("trocar", [False, True])
def test_mesmo_pl_e_reconhecido_em_qualquer_ordem_das_linhas(trocar):
    a = [item(None, "PAPEL TERMICO 80MM", 10, "CX"), item(None, "PAPEL TERMICO 80MM AZUL COM TUBETE", 10, "CX")]
    b = [item(None, "PAPEL TERMICO 80MM VERDE SEM NUCLEO", 10, "CX"), item(None, "PAPEL TERMICO 80MM AZUL COM TUBETE", 10, "CX")]
    r = _enviar(
        ("INV.pdf", PDF, [doc("invoice", 50, 55, numero="X-9")]),
        ("PL A.pdf", PDF, [doc("packing_list", 50, 55, refs=["X-9"], itens=a)]),
        ("PL B.pdf", PDF, [doc("packing_list", 50, 56, refs=["X-9"], itens=b[::-1] if trocar else b)]),
    )
    assert any("Mais de um documento Packing List" in aviso for aviso in r.avisos)


def test_proforma_em_dois_arquivos_e_conferida_por_dentro_uma_vez_com_o_proprio_nome():
    interna = [("Moeda da coluna (USD) diferente da do total (EUR)", "USD × EUR")]
    proforma = dict(numero="PI-9", subtipo="PROFORMA", internas=interna, quantidade=(900, "PCS"))
    r = _enviar(
        ("PI.pdf", PDF, [doc("invoice", **proforma)]),
        ("PEDIDO.xlsx", XLSX, [doc("invoice", **proforma, pagina=None)]),
        ("INV.pdf", PDF, [doc("invoice", 30, 33, numero="C-1")]),
    )
    internas = [d.mensagem for d in r.divergencias if d.categoria == "interna"]
    assert internas == ["Proforma PI-9: Moeda da coluna (USD) diferente da do total (EUR)"]
    assert "Proforma PI-9 (PI.pdf, pág. 1) não entrou na comparação: há invoice comercial." in r.avisos


@pytest.mark.parametrize("planilha", [("CI.xlsx", XLSX), ("CI.xls", XLS)])
def test_mesma_carga_renumerada_em_excel_e_pdf_conta_uma_vez_com_aviso_do_numero(planilha):
    linhas = [item(None, "CAPACETE MODELO ORION TAM M", 120, "PCS"), item(None, "VISEIRA FUME", 40, "PCS")]
    r = _enviar(
        (*planilha, [doc("invoice", 300.4, 350.6884, numero="Z-009", itens=linhas, pagina=None)]),
        ("CI.pdf", PDF, [doc("invoice", 300.4, 350.69, numero="Z-050", itens=linhas)]),
        ("PL.pdf", PDF, [doc("packing_list", 300.4, 350.69, refs=["Z-050"], itens=linhas)]),
    )
    assert len(r.comparacoes) == 1
    assert any("Mais de um documento Invoice Z-050" in a and "com outro número (Z-009)" in a for a in r.avisos)


def test_carga_diferente_em_excel_e_pdf_com_numeros_diferentes_continua_separada():
    r = _enviar(
        ("CI.xlsx", XLSX, [doc("invoice", 300, 350, numero="Z-009", itens=[item(None, "ORION", 120, "PCS")],
                               pagina=None)]),
        ("CI.pdf", PDF, [doc("invoice", 200, 240, numero="Z-050", itens=[item(None, "ORION", 80, "PCS")])]),
    )
    assert not any("Mais de um documento Invoice" in a for a in r.avisos)


def test_duas_invoices_reais_com_a_mesma_carga_citadas_por_pls_diferentes_continuam_separadas():
    linhas = [item(None, "RESINA PEAD SACO 25KG", 1000, "SACOS")]
    r = _enviar(
        ("INV-1.xlsx", XLSX, [doc("invoice", 25000, 25500, numero="R-1", itens=linhas, pagina=None)]),
        ("INV-2.pdf", PDF, [doc("invoice", 25000, 25500, numero="R-2", itens=linhas)]),
        ("PL-1.pdf", PDF, [doc("packing_list", 25000, 25500, numero="P-1", refs=["R-1"], itens=linhas)]),
        ("PL-2.pdf", PDF, [doc("packing_list", 25000, 25500, numero="P-2", refs=["R-2"], itens=linhas)]),
    )
    assert not any("Mais de um documento Invoice" in a or "sem invoice" in a for a in r.avisos)
    assert [c.titulo for c in r.comparacoes] == ["Invoice R-1 × Packing List P-1", "Invoice R-2 × Packing List P-2"]


def test_numero_do_excel_citado_pelo_pl_nao_e_tratado_como_versao_antiga():
    linhas = [item(None, "CAPACETE MODELO ORION TAM M", 120, "PCS")]
    r = _enviar(
        ("CI.xlsx", XLSX, [doc("invoice", 300, 350, numero="Z-009", itens=linhas, pagina=None)]),
        ("CI.pdf", PDF, [doc("invoice", 300, 350, numero="Z-050", itens=linhas)]),
        ("PL.pdf", PDF, [doc("packing_list", 300, 350, refs=["Z-009"], itens=linhas)]),
    )
    assert not any("Mais de um documento Invoice" in a for a in r.avisos)


def test_imagem_e_pdf_com_numeros_diferentes_nao_sao_a_mesma_carga():
    linhas = [item(None, "CAPACETE MODELO ORION TAM M", 120, "PCS")]
    r = _enviar(
        ("CI.png", "image/png", [doc("invoice", 300, 350, numero="Z-009", itens=linhas)]),
        ("CI.pdf", PDF, [doc("invoice", 300, 350, numero="Z-050", itens=linhas)]),
    )
    assert not any("Mais de um documento Invoice" in a for a in r.avisos)


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
