"""Invoice FOB/EXW com frete ou seguro somados ao total: a operação pede para remover."""

from tests.comparacao.apoio import doc, item, mensagens, rodar


def _invoice(incoterm, total, frete=None, seguro=None):
    itens = [item("A1", "Valvula de esfera", valor=1500.0), item("A2", "Valvula de gaveta", valor=500.0)]
    return doc("invoice", numero="1", incoterm=incoterm, itens=itens, valor_total=total, valor_frete=frete,
               valor_seguro=seguro)


def _somados(r):
    return [m for m in mensagens(r, "coerencia") if "frete/seguro somados ao total" in m]


def test_fob_com_frete_e_seguro_somados_ao_total_e_apontado():
    assert _somados(rodar([_invoice(("FOB", "NINGBO"), 2350.0, frete=300.0, seguro=50.0)]))


def test_exw_com_frete_somado_ao_total_e_apontado():
    assert _somados(rodar([_invoice("EXW", 2300.0, frete=300.0, seguro=50.0)]))


def test_fob_com_frete_so_informado_fora_do_total_passa():
    assert not _somados(rodar([_invoice("FOB", 2000.0, frete=300.0)]))


def test_cif_com_frete_somado_ao_total_passa():
    assert not _somados(rodar([_invoice("CIF", 2350.0, frete=300.0, seguro=50.0)]))
