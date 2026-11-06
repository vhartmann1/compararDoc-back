"""PL no mesmo arquivo de uma versão ignorada da invoice sai junto com ela: não soma nem pareia."""

from app.tipos_de_arquivo import MEDIA_XLS, MEDIA_XLSX
from tests.comparacao.apoio import campo, doc, enviar, item


def _versao(quantidade_extra, total_qtd):
    linhas = [item(None, "BICICLETA ERGOMETRICA", 10, "PCS"), item(None, "PECA DE REPOSICAO", quantidade_extra, "PCS")]
    return [
        doc("invoice", 500, 600, numero="X-77", quantidade=(total_qtd, "PCS"), itens=linhas, valor_total=1000),
        doc("packing_list", 500, 600, refs=["X-77"], volumes=(12, "CTN"), quantidade=(total_qtd, "PCS"), itens=linhas),
    ]


def _bl():
    return [doc("conhecimento", None, 600, subtipo="BL", numero="BL1", volumes=(12, "CTN"))]


def test_pl_da_versao_antiga_nao_soma_com_o_da_revisada():
    r = enviar(("CI antiga.xls", MEDIA_XLS, _versao(2, 12)), ("CI revisada.xlsx", MEDIA_XLSX, _versao(40, 50)),
               ("BL.pdf", "application/pdf", _bl()))
    consolidado = r.comparacoes[-1]
    assert campo(consolidado, "peso_bruto").status == "OK"
    assert campo(consolidado, "volumes").status == "OK"
    assert not [d for d in r.divergencias if d.campo == "quantidade"]
    assert not any("sem invoice correspondente" in a for a in r.avisos)


def test_o_resultado_nao_depende_da_ordem_dos_arquivos():
    r = enviar(("CI revisada.xlsx", MEDIA_XLSX, _versao(40, 50)), ("CI antiga.xls", MEDIA_XLS, _versao(2, 12)),
               ("BL.pdf", "application/pdf", _bl()))
    assert campo(r.comparacoes[-1], "peso_bruto").status == "OK"


def test_dois_pls_da_mesma_invoice_em_arquivos_sem_versao_continuam_somando():
    pl_a = doc("packing_list", 300, 350, refs=["X-77"], volumes=(8, "CTN"))
    pl_b = doc("packing_list", 200, 250, refs=["X-77"], volumes=(4, "CTN"))
    r = enviar(("CI.xlsx", MEDIA_XLSX, [doc("invoice", 500, 600, numero="X-77", valor_total=1000)]),
               ("PL1.xlsx", MEDIA_XLSX, [pl_a]), ("PL2.xlsx", MEDIA_XLSX, [pl_b]), ("BL.pdf", "application/pdf", _bl()))
    assert campo(r.comparacoes[-1], "peso_bruto").status == "OK"
