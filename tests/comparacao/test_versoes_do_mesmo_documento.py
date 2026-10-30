"""Mesmo documento em mais de um arquivo: qual versão fica e quando são documentos diferentes."""

import pytest

from app.tipos_de_arquivo import MEDIA_DOCX, MEDIA_PDF, MEDIA_XLS, MEDIA_XLSX
from tests.comparacao.apoio import campo, doc, enviar, item, rodar


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


def test_mesmo_documento_em_dois_formatos_um_sem_numero_conta_uma_vez():
    r = rodar(
        [doc("invoice", 100, 110, numero="A1", volumes=(20, "CTNS")), doc("packing_list", 100, 110, volumes=(20, "CTNS"))],
        [doc("invoice", 100, 110, volumes=(20, "CARTONS")), doc("packing_list", 100, 110, volumes=(20, "CARTONS"))],
    )
    assert campo(r.comparacoes[0], "peso_bruto").status == "OK"
    assert any("Mais de um documento Invoice" in a for a in r.avisos)


@pytest.mark.parametrize("pdf_primeiro", [True, False])
def test_mesmo_documento_em_pdf_e_excel_usa_o_pdf_em_qualquer_ordem(pdf_primeiro):
    pdf = ("CI.pdf", MEDIA_PDF, [doc("invoice", 100, 110, ["69101000"], numero="A1")])
    excel = ("CI.xlsx", MEDIA_XLSX, [doc("invoice", 100, 110, ["39221000"], numero="A1")])
    pl = ("PL.pdf", MEDIA_PDF, [doc("packing_list", 100, 110, refs=["A1"])])
    r = enviar(*([pdf, excel] if pdf_primeiro else [excel, pdf]), pl)
    assert any("usado CI.pdf (original, pág. 1), por ser o PDF (vale mais que Excel ou Word)" in a for a in r.avisos)
    assert campo(r.comparacoes[0], "ncm").valores["invoice"].exibicao == "6910.10.00"


def test_versao_vale_mais_que_o_formato():
    r = enviar(
        ("INV.xlsx", MEDIA_XLSX, [doc("invoice", 100, 110, numero="A1", versao="draft")]),
        ("INV.pdf", MEDIA_PDF, [doc("invoice", 100, 110, numero="A1", versao="original")]),
    )
    assert any("usado INV.pdf (original, pág. 1), pela versão lida no documento" in a for a in r.avisos)


def test_campo_que_falta_no_documento_usado_vem_da_duplicata():
    r = enviar(
        ("CI.xlsx", MEDIA_XLSX, [doc("invoice", 100, 110, ["69101000"], numero="A1")]),
        ("CI.pdf", MEDIA_PDF, [doc("invoice", 100, 110, numero="A1")]),
        ("PL.pdf", MEDIA_PDF, [doc("packing_list", 100, 110, ["69101000"], refs=["A1"])]),
    )
    ncm = campo(r.comparacoes[0], "ncm")
    assert ncm.status == "OK"
    assert ncm.valores["invoice"].arquivo_id == "a0"
    assert "NCM de Invoice A1 tirado de CI.xlsx (o arquivo usado não traz)." in r.avisos


def test_proforma_com_o_numero_da_invoice_nao_vence_a_invoice():
    r = enviar(
        ("INVOICE.pdf", MEDIA_PDF, [doc("invoice", 100, 110, numero="A1")]),
        ("PROFORMA INVOICE.pdf", MEDIA_PDF, [doc("invoice", 100, 110, numero="A1")]),
    )
    assert any("usado INVOICE.pdf (original, pág. 1), porque o outro é proforma" in a for a in r.avisos)


def test_rascunho_em_word_e_pdf_final_do_mesmo_pl_contam_uma_vez_com_aviso_dos_totais():
    linha = [item(None, "ARAME DE ACO 2MM BOBINA 10KG", 300, "KG")]
    r = enviar(
        ("INV.pdf", MEDIA_PDF, [doc("invoice", 300, numero="X-77", itens=linha)]),
        ("RASCUNHO.docx", MEDIA_DOCX,
         [doc("packing_list", 300, 330, refs=["X-77"], volumes=(1, "PALLET"), itens=linha)]),
        ("PL.pdf", MEDIA_PDF, [doc("packing_list", 300, 326, refs=["X-77"], volumes=(1, "PALLET"), itens=linha)]),
        ("AWB.pdf", MEDIA_PDF, [doc("conhecimento", None, 326, subtipo="AWB", numero="999-1", refs=["X-77"], volumes=(1, "PALLET"))]),
    )
    assert len(r.comparacoes) == 1
    assert campo(r.comparacoes[0], "peso_bruto").status == "OK"
    assert any("Mais de um documento Packing List" in a and "peso bruto 326 KG × 330 KG" in a for a in r.avisos)


def test_dois_pl_da_mesma_invoice_com_itens_diferentes_continuam_separados():
    r = enviar(
        ("INV.pdf", MEDIA_PDF, [doc("invoice", 300, numero="X-77")]),
        ("PL1.pdf", MEDIA_PDF, [doc("packing_list", 100, 110, refs=["X-77"], itens=[item("A1", "PECA A", 10)])]),
        ("PL2.pdf", MEDIA_PDF, [doc("packing_list", 200, 220, refs=["X-77"], itens=[item("B2", "PECA B", 20)])]),
    )
    assert not any("Mais de um documento Packing List" in a for a in r.avisos)


def test_linhas_repetidas_com_e_sem_quantidade_nao_derrubam_a_escolha():
    linhas = [item(None, "PERFIL DE ALUMINIO", 10, "PCS"), item(None, "PERFIL DE ALUMINIO")]
    r = enviar(
        ("INV.pdf", MEDIA_PDF, [doc("invoice", 100, numero="X-77")]),
        ("PL.docx", MEDIA_DOCX, [doc("packing_list", 100, 110, refs=["X-77"], itens=linhas)]),
        ("PL.pdf", MEDIA_PDF, [doc("packing_list", 100, 111, refs=["X-77"], itens=linhas)]),
    )
    assert any("Mais de um documento Packing List" in a for a in r.avisos)


def test_rascunho_pelo_nome_perde_para_o_original_com_os_mesmos_totais():
    r = enviar(
        ("CI ORIGINAL.pdf", MEDIA_PDF, [doc("invoice", 100, 110, versao="desconhecida")]),
        ("CI DRAFT.pdf", MEDIA_PDF, [doc("invoice", 100, 110, versao="desconhecida")]),
    )
    usado = "usado CI ORIGINAL.pdf (pág. 1), pelo nome do arquivo (original × rascunho ou cópia)"
    assert any(usado in a for a in r.avisos)


def test_mesmo_pl_lido_com_as_palavras_em_outra_ordem_conta_uma_vez():
    a = [item(None, "PAPEL TERMICO 48 GSM ROLO 80MM", 1000, "M2")]
    b = [item(None, "PAPEL TERMICO ROLO 80MM 48 GSM", 1000, "M2")]
    r = enviar(
        ("INV.pdf", MEDIA_PDF, [doc("invoice", 500, 520, numero="X-9")]),
        ("PL A.pdf", MEDIA_PDF, [doc("packing_list", 500, 520, refs=["X-9"], itens=a)]),
        ("PL B.pdf", MEDIA_PDF, [doc("packing_list", 490, 520, refs=["X-9"], itens=b)]),
    )
    assert any("Mais de um documento Packing List" in a for a in r.avisos)


@pytest.mark.parametrize("trocar", [False, True])
def test_mesmo_pl_e_reconhecido_em_qualquer_ordem_das_linhas(trocar):
    a = [item(None, "PAPEL TERMICO 80MM", 10, "CX"), item(None, "PAPEL TERMICO 80MM AZUL COM TUBETE", 10, "CX")]
    b = [item(None, "PAPEL TERMICO 80MM VERDE SEM NUCLEO", 10, "CX"), item(None, "PAPEL TERMICO 80MM AZUL COM TUBETE", 10, "CX")]
    r = enviar(
        ("INV.pdf", MEDIA_PDF, [doc("invoice", 50, 55, numero="X-9")]),
        ("PL A.pdf", MEDIA_PDF, [doc("packing_list", 50, 55, refs=["X-9"], itens=a)]),
        ("PL B.pdf", MEDIA_PDF, [doc("packing_list", 50, 56, refs=["X-9"], itens=b[::-1] if trocar else b)]),
    )
    assert any("Mais de um documento Packing List" in aviso for aviso in r.avisos)


@pytest.mark.parametrize("planilha", [("CI.xlsx", MEDIA_XLSX), ("CI.xls", MEDIA_XLS)])
def test_mesma_carga_renumerada_em_excel_e_pdf_conta_uma_vez_com_aviso_do_numero(planilha):
    linhas = [item(None, "CAPACETE MODELO ORION TAM M", 120, "PCS"), item(None, "VISEIRA FUME", 40, "PCS")]
    r = enviar(
        (*planilha, [doc("invoice", 300.4, 350.6884, numero="Z-009", itens=linhas, pagina=None)]),
        ("CI.pdf", MEDIA_PDF, [doc("invoice", 300.4, 350.69, numero="Z-050", itens=linhas)]),
        ("PL.pdf", MEDIA_PDF, [doc("packing_list", 300.4, 350.69, refs=["Z-050"], itens=linhas)]),
    )
    assert len(r.comparacoes) == 1
    assert any("Mais de um documento Invoice Z-050" in a and "com outro número (Z-009)" in a for a in r.avisos)


def test_carga_diferente_em_excel_e_pdf_com_numeros_diferentes_continua_separada():
    r = enviar(
        ("CI.xlsx", MEDIA_XLSX, [doc("invoice", 300, 350, numero="Z-009", itens=[item(None, "ORION", 120, "PCS")],
                               pagina=None)]),
        ("CI.pdf", MEDIA_PDF, [doc("invoice", 200, 240, numero="Z-050", itens=[item(None, "ORION", 80, "PCS")])]),
    )
    assert not any("Mais de um documento Invoice" in a for a in r.avisos)


def test_duas_invoices_reais_com_a_mesma_carga_citadas_por_pls_diferentes_continuam_separadas():
    linhas = [item(None, "RESINA PEAD SACO 25KG", 1000, "SACOS")]
    r = enviar(
        ("INV-1.xlsx", MEDIA_XLSX, [doc("invoice", 25000, 25500, numero="R-1", itens=linhas, pagina=None)]),
        ("INV-2.pdf", MEDIA_PDF, [doc("invoice", 25000, 25500, numero="R-2", itens=linhas)]),
        ("PL-1.pdf", MEDIA_PDF, [doc("packing_list", 25000, 25500, numero="P-1", refs=["R-1"], itens=linhas)]),
        ("PL-2.pdf", MEDIA_PDF, [doc("packing_list", 25000, 25500, numero="P-2", refs=["R-2"], itens=linhas)]),
    )
    assert not any("Mais de um documento Invoice" in a or "sem invoice" in a for a in r.avisos)
    assert [c.titulo for c in r.comparacoes] == ["Invoice R-1 × Packing List P-1", "Invoice R-2 × Packing List P-2"]


def test_numero_do_excel_citado_pelo_pl_nao_e_tratado_como_versao_antiga():
    linhas = [item(None, "CAPACETE MODELO ORION TAM M", 120, "PCS")]
    r = enviar(
        ("CI.xlsx", MEDIA_XLSX, [doc("invoice", 300, 350, numero="Z-009", itens=linhas, pagina=None)]),
        ("CI.pdf", MEDIA_PDF, [doc("invoice", 300, 350, numero="Z-050", itens=linhas)]),
        ("PL.pdf", MEDIA_PDF, [doc("packing_list", 300, 350, refs=["Z-009"], itens=linhas)]),
    )
    assert not any("Mais de um documento Invoice" in a for a in r.avisos)


def test_imagem_e_pdf_com_numeros_diferentes_nao_sao_a_mesma_carga():
    linhas = [item(None, "CAPACETE MODELO ORION TAM M", 120, "PCS")]
    r = enviar(
        ("CI.png", "image/png", [doc("invoice", 300, 350, numero="Z-009", itens=linhas)]),
        ("CI.pdf", MEDIA_PDF, [doc("invoice", 300, 350, numero="Z-050", itens=linhas)]),
    )
    assert not any("Mais de um documento Invoice" in a for a in r.avisos)


def _media(nome):
    return MEDIA_XLSX if nome.endswith(".xlsx") else MEDIA_PDF


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
def test_revisao_mais_nova_pelo_nome_do_arquivo_vence_mesmo_enviada_antes(antigo, revisado):
    r = enviar((revisado, _media(revisado), [doc("invoice", 100, 110, numero="A1")]),
               (antigo, _media(antigo), [doc("invoice", 100, 110, numero="A1")]))
    usado = f"usado {revisado} (original, pág. 1), por ser a revisão mais nova pelo nome do arquivo"
    assert any(usado in a for a in r.avisos)


def test_nome_com_rev_no_meio_de_palavra_nao_e_revisao():
    r = enviar(("PREVIEW BREVE.pdf", MEDIA_PDF, [doc("invoice", 100, 110, numero="A1")]),
               ("CI.pdf", MEDIA_PDF, [doc("invoice", 100, 110, numero="A1")]))
    assert any("usado CI.pdf (original, pág. 1), por ser o último enviado" in a for a in r.avisos)
