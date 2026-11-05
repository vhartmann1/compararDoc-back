"""As partes de cada divergência (origem, rótulo, detalhe, ação) recompõem a mensagem."""

from app.services.comparacao.mensagens import Diferenca, divergencia, pedido
from tests.comparacao.apoio import doc, item, rodar
from tests.comparacao.cenarios import caso_4


def _recompor(d):
    """A mensagem montada só com as partes: origem da comparação com ' — ', a do documento com ': '."""
    inicio = (f"{d.origem} — " if d.comparacao_id else f"{d.origem}: ") if d.origem else ""
    rotulo = f"{d.rotulo}: " if d.rotulo else ""
    return inicio + rotulo + d.detalhe + (f"; {d.acao}." if d.acao else "")


def _com_partes(r):
    return [d for d in r.divergencias if d.detalhe is not None]


def test_partes_montam_a_mensagem_com_origem_rotulo_e_acao():
    d = divergencia("comparacao", "par-1", "ncm", "Invoice A1", "NCM", pedido("a invoice cita 1111", "correção"))
    assert d.mensagem == "Invoice A1 — NCM: a invoice cita 1111; pedir correção."
    assert (d.origem, d.rotulo, d.detalhe, d.acao) == ("Invoice A1", "NCM", "a invoice cita 1111", "pedir correção")


def test_sem_origem_nem_rotulo_a_mensagem_e_o_detalhe():
    d = divergencia("coerencia", None, "incoterm", None, None, Diferenca("frete PREPAID com FOB"))
    assert d.mensagem == "frete PREPAID com FOB"
    assert (d.origem, d.rotulo, d.acao) == (None, None, None)


def test_varios_pares_com_conhecimento_recompoem_todas_as_mensagens():
    r = caso_4()
    divergencias = _com_partes(r)
    assert {d.origem for d in divergencias} >= {"Invoice L30514262", "Invoice L30518777"}
    assert all(d.mensagem == _recompor(d) for d in divergencias)


def test_ncm_itens_e_interna_recompoem_e_separam_a_acao():
    r = rodar(
        [doc("invoice", 100, 110, ["3901.10.10"], numero="INV9", itens=[item("X1", "PECA AZUL", 10, valor=5)],
             valor_total=7, internas=[("total escrito diferente", "7 × 5")])],
        [doc("packing_list", 100, 110, ["3901.10.10"], numero="INV9", itens=[item("X1", "PECA AZUL", 12)])],
        [doc("conhecimento", 100, 110, ["3902.20.20"], subtipo="BL")],
        escaneado=False,
    )
    assert all(d.mensagem == _recompor(d) for d in _com_partes(r))
    ncm = next(d for d in r.divergencias if d.campo == "ncm")
    assert (ncm.rotulo, ncm.acao) == ("NCM", "pedir correção")
    assert next(d for d in r.divergencias if d.categoria == "item").rotulo == "Item X1"
    soma = next(d for d in r.divergencias if d.categoria == "interna" and d.acao)
    assert (soma.origem, soma.acao) == ("Invoice INV9", "pedir correção")


def test_interna_escrita_pela_leitura_so_tem_a_origem():
    r = rodar([doc("invoice", 100, numero="INV9", internas=[("total escrito diferente", "7 × 5")])])
    d = next(d for d in r.divergencias if d.categoria == "interna")
    assert d.mensagem == "Invoice INV9: total escrito diferente"
    assert (d.origem, d.rotulo, d.detalhe, d.acao) == ("Invoice INV9", None, None, None)
