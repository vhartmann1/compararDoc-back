"""Versões do mesmo packing list que citam outro nº de invoice: o número errado é apontado, não aceito."""

from tests.comparacao.apoio import arquivo, doc, mensagens
from app.schemas import ExtracaoArquivo
from app.services.comparacao import comparar


def _pl(refs):
    return doc("packing_list", 90, 100, numero="PL20250311XYZ", refs=refs)


def _rodar(*arquivos):
    entradas = [(arquivo(nome).model_copy(update={"nome": f"{nome}.pdf"}), ExtracaoArquivo(documentos=docs))
                for nome, docs in arquivos]
    return comparar(entradas)


def _versoes(r):
    return [m for m in mensagens(r, "interna") if "versões" in m]


def test_versao_antiga_com_um_zero_a_mais_no_numero_e_apontada():
    r = _rodar(("CI", [doc("invoice", 90, 100, numero="20250311XYZ")]),
               ("PL REV-1", [_pl(["20250311XYZ"])]), ("PL", [_pl(["202500311XYZ"])]))
    assert _versoes(r) == ["Packing List PL20250311XYZ: duas versões citam nº de invoice diferente — "
                           "PL REV-1.pdf 20250311XYZ × PL.pdf 202500311XYZ"]
    assert not [m for m in mensagens(r, "comparacao") if m.startswith("Nº da invoice")]


def test_versoes_com_o_mesmo_numero_nao_divergem():
    r = _rodar(("CI", [doc("invoice", 90, 100, numero="20250311XYZ")]),
               ("PL REV-1", [_pl(["20250311XYZ"])]), ("PL", [_pl(["20250311-XYZ"])]))
    assert _versoes(r) == []


def test_versao_que_nao_cita_invoice_nao_diverge():
    r = _rodar(("CI", [doc("invoice", 90, 100, numero="20250311XYZ")]),
               ("PL REV-1", [_pl(["20250311XYZ"])]), ("PL", [_pl([])]))
    assert _versoes(r) == []


def test_duas_versoes_erradas_iguais_dao_uma_mensagem_so():
    r = _rodar(("CI", [doc("invoice", 90, 100, numero="20250311XYZ")]), ("PL REV-1", [_pl(["20250311XYZ"])]),
               ("PL", [_pl(["202500311XYZ"])]), ("PL copia", [_pl(["202500311XYZ"])]))
    assert len(_versoes(r)) == 1
