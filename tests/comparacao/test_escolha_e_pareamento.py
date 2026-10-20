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


@pytest.mark.parametrize("pdf_primeiro", [True, False])
def test_mesmo_documento_em_pdf_e_excel_usa_o_pdf_em_qualquer_ordem(pdf_primeiro):
    pdf = ("CI.pdf", PDF, [doc("invoice", 100, 110, ["69101000"], numero="A1")])
    excel = ("CI.xlsx", XLSX, [doc("invoice", 100, 110, ["39221000"], numero="A1")])
    pl = ("PL.pdf", PDF, [doc("packing_list", 100, 110, refs=["A1"])])
    r = _enviar(*([pdf, excel] if pdf_primeiro else [excel, pdf]), pl)
    assert any("usado original (CI.pdf" in a for a in r.avisos)
    assert campo(r.comparacoes[0], "ncm").valores["invoice"].exibicao == "6910.10.00"


def test_versao_vale_mais_que_o_formato():
    r = _enviar(
        ("INV.xlsx", XLSX, [doc("invoice", 100, 110, numero="A1", versao="draft")]),
        ("INV.pdf", PDF, [doc("invoice", 100, 110, numero="A1", versao="original")]),
    )
    assert any("usado original (INV.pdf" in a for a in r.avisos)


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
    assert any("usado original (INVOICE.pdf" in a for a in r.avisos)


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

