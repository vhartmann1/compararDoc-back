"""Documento dividido em arquivos (páginas) e planilha de detalhe do PL: nem descartar nem somar em dobro."""

from pathlib import Path

import pytest

from app.schemas import ArquivoEntrada, ExtracaoArquivo, ValorMonetario
from app.services.comparacao.escolha_dos_documentos import escolher_documentos
from app.services.comparacao.versoes_com_valor_diferente import divergencias_entre_versoes
from app.services.leitura.arquivo_para_conteudo import MEDIA_PDF, MEDIA_XLS
from tests.comparacao.apoio import doc, item

ORDENS = [False, True]


def _arquivo(nome, media=MEDIA_PDF):
    return ArquivoEntrada(id=nome, nome=nome, caminho=Path(f"/tmp/{nome}"), media_type=media)


def _escolher(*arquivos, invertido=False):
    ordem = list(reversed(arquivos)) if invertido else list(arquivos)
    avisos: list[str] = []
    entradas = [(arq, ExtracaoArquivo(documentos=docs)) for arq, docs in ordem]
    return escolher_documentos(entradas, avisos).por_tipo, avisos


def _valor(v):
    return ValorMonetario(valor=v, moeda="USD", texto_original=f"USD {v}", pagina=1)


def _invoice(itens, total=None, liquido=None, bruto=None):
    d = doc("invoice", liquido, bruto, numero="Z-100", itens=itens)
    return d.model_copy(update={"valor_total": _valor(total) if total else None})


PAGINA_1 = [item("AB-1", "MOCHILA ESCOLAR", 10, valor=100.0), item("AB-2", "ESTOJO ESCOLAR", 20, valor=40.0)]
PAGINA_2 = [item("AB-3", "LANCHEIRA TERMICA", 5, valor=60.0)]


@pytest.mark.parametrize("invertido", ORDENS)
def test_invoice_dividida_em_dois_arquivos_vira_um_documento_com_todos_os_itens(invertido):
    por_tipo, _ = _escolher(
        (_arquivo("INV -1.jpg", "image/jpeg"), [_invoice(PAGINA_1)]),
        (_arquivo("INV -2.jpg", "image/jpeg"), [_invoice(PAGINA_2, total=200.0, liquido=90, bruto=100)]),
        invertido=invertido,
    )
    [invoice] = por_tipo["invoice"]
    assert sorted(i.codigo for i in invoice.doc.itens) == ["AB-1", "AB-2", "AB-3"]
    assert invoice.doc.valor_total.valor == 200.0 and invoice.doc.peso_bruto_total.valor == 100
    assert invoice.duplicatas == [] and divergencias_entre_versoes([invoice]) == []


def test_paginas_com_o_mesmo_total_que_bate_com_a_soma_de_todas_tambem_se_juntam():
    por_tipo, _ = _escolher(
        (_arquivo("A.pdf"), [_invoice(PAGINA_1, total=200.0)]),
        (_arquivo("B.pdf"), [_invoice(PAGINA_2, total=200.0)]),
    )
    [invoice] = por_tipo["invoice"]
    assert len(invoice.doc.itens) == 3 and invoice.duplicatas == []


def test_rascunho_e_original_com_os_mesmos_itens_continuam_versoes():
    por_tipo, _ = _escolher(
        (_arquivo("INV DRAFT.pdf"), [_invoice(PAGINA_1, total=140.0)]),
        (_arquivo("INV.pdf"), [_invoice(PAGINA_1, total=140.0)]),
    )
    [invoice] = por_tipo["invoice"]
    assert invoice.arquivo.nome == "INV.pdf" and len(invoice.doc.itens) == 2 and len(invoice.duplicatas) == 1


def test_itens_diferentes_mas_os_dois_com_totais_proprios_continuam_versoes():
    por_tipo, _ = _escolher(
        (_arquivo("A.pdf"), [_invoice(PAGINA_1, total=140.0)]),
        (_arquivo("B.pdf"), [_invoice(PAGINA_2, total=60.0)]),
    )
    [invoice] = por_tipo["invoice"]
    assert len(invoice.duplicatas) == 1


def _pl_pdf(liquido=16000, bruto=17500):
    return doc("packing_list", liquido, bruto, numero="PL-7", volumes=(40, "PALLETS"), quantidade=(4000, "ROLLS"),
               itens=[item(None, "FILME PLASTICO", 4000)])


def _detalhe_xls(liquido=16000, bruto=17500, quantidade=(4000, "NO OF NUMBER")):
    linhas = [item(None, f"PALETE {n}", 100) for n in range(40)]
    return doc("packing_list", liquido, bruto, numero="DET-9/25", pagina=None, quantidade=quantidade, itens=linhas)


@pytest.mark.parametrize("invertido", ORDENS)
def test_planilha_com_os_mesmos_pesos_do_pl_em_pdf_e_detalhe_e_sai_da_soma(invertido):
    por_tipo, _ = _escolher(
        (_arquivo("PACKING LIST.pdf"), [_pl_pdf()]),
        (_arquivo("packing details.xls", MEDIA_XLS), [_detalhe_xls()]),
        invertido=invertido,
    )
    [pl] = por_tipo["packing_list"]
    assert pl.arquivo.nome == "PACKING LIST.pdf"


@pytest.mark.parametrize(
    "detalhe",
    [_detalhe_xls(liquido=15000), _detalhe_xls(bruto=16500), _detalhe_xls(quantidade=(3000, "PCS"))],
    ids=["liquido-diferente", "bruto-diferente", "quantidade-diferente"],
)
def test_planilha_e_pdf_com_totais_diferentes_continuam_somando(detalhe):
    por_tipo, _ = _escolher(
        (_arquivo("PACKING LIST.pdf"), [_pl_pdf()]),
        (_arquivo("packing 2.xls", MEDIA_XLS), [detalhe]),
    )
    assert len(por_tipo["packing_list"]) == 2


def test_planilha_sem_peso_liquido_nao_e_detalhe_so_pelo_bruto():
    por_tipo, _ = _escolher(
        (_arquivo("PACKING LIST.pdf"), [_pl_pdf()]),
        (_arquivo("packing 2.xls", MEDIA_XLS), [_detalhe_xls(liquido=None)]),
    )
    assert len(por_tipo["packing_list"]) == 2


def test_planilha_com_os_mesmos_pesos_mas_de_outras_invoices_continua_somando():
    pdf = _pl_pdf().model_copy(update={"invoices_referenciadas": ["FAB-1"]})
    planilha = _detalhe_xls().model_copy(update={"invoices_referenciadas": ["REV-1", "REV-2"]})
    por_tipo, _ = _escolher(
        (_arquivo("PACKING LIST.pdf"), [pdf]),
        (_arquivo("packing 2.xls", MEDIA_XLS), [planilha]),
    )
    assert len(por_tipo["packing_list"]) == 2
