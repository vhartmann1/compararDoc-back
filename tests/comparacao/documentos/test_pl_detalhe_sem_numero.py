import pytest

from app.schemas import ExtracaoArquivo
from app.services.comparacao.documentos.escolha_dos_documentos import escolher_documentos
from tests.comparacao.apoio import arquivo, doc, item, mensagens, rodar

ORDENS = [False, True]


def _copia():
    itens = [item(None, "PNEU 185/60R14 TL 82H", 30), item(None, "PNEU 205/55R16 TL 94W", 20)]
    detalhe = [item(None, "185/60R14PR 82H MARCA TL", 30), item(None, "205/55R16PR 94W MARCA TL", 20)]
    return [
        doc("invoice", 900, 1000, numero="A1", quantidade=(50, "PCS"), itens=itens),
        doc("packing_list", 900, 1000, refs=["A1"], quantidade=(50, "PCS"), exportador="EXPORTADORA X", itens=itens),
        doc("packing_list", bruto=1000, quantidade=(50, "UNIT"), itens=detalhe),
    ]


def _pls(*arquivos, invertido=False):
    ordem = list(reversed(arquivos)) if invertido else list(arquivos)
    entradas = [(arquivo(f"a{i}"), ExtracaoArquivo(documentos=docs)) for i, docs in enumerate(ordem)]
    return escolher_documentos(entradas).por_tipo["packing_list"]


@pytest.mark.parametrize("invertido", ORDENS)
def test_lista_por_conteiner_sem_numero_com_os_mesmos_totais_nao_entra_na_soma(invertido):
    copias = [_copia(), _copia(), [doc("conhecimento", subtipo="BL", bruto=1000)]]
    r = rodar(*(reversed(copias) if invertido else copias))
    assert mensagens(r, "comparacao") == []


@pytest.mark.parametrize("invertido", ORDENS)
def test_entre_pl_e_lista_sem_numero_fica_o_pl_identificado(invertido):
    pls = _pls(_copia(), _copia(), invertido=invertido)
    assert [f.doc.invoices_referenciadas for f in pls] == [["A1"]]


def test_dois_pls_sem_numero_com_totais_diferentes_continuam_somando():
    r = rodar(
        [doc("invoice", 900, 1000, numero="A1", quantidade=(50, "PCS")),
         doc("packing_list", bruto=600, quantidade=(30, "PCS")),
         doc("packing_list", bruto=400, quantidade=(20, "PCS"))],
        [doc("conhecimento", subtipo="BL", bruto=1000)],
    )
    assert mensagens(r, "comparacao") == []


@pytest.mark.parametrize("invertido", ORDENS)
@pytest.mark.parametrize(
    "outro",
    [
        dict(bruto=1000, quantidade=(50, "PCS")),
        dict(liquido=800, bruto=1000, quantidade=(50, "PCS")),
        dict(bruto=1000, quantidade=(50, "KG")),
    ],
    ids=["so-peso-bruto-e-quantidade", "liquido-diferente", "pecas-x-kg"],
)
def test_pls_sem_numero_que_so_coincidem_em_parte_continuam_os_dois(outro, invertido):
    primeiro = doc("packing_list", liquido=900 if "liquido" in outro else None, bruto=1000, quantidade=(50, "PCS"))
    assert len(_pls([primeiro], [doc("packing_list", **outro)], invertido=invertido)) == 2
