"""Invoice com notify: o notify do conhecimento tem de ser o mesmo; sem notify na invoice, vale a regra antiga."""

from tests.comparacao.apoio import doc, rodar
from tests.comparacao.cenarios import CAPITAL

CLIENTE = ("Lume Bicicletas Comercio Ltda", "12.345.678/0001-90")
OUTRO = ("Praia Alta Despachos Ltda", "98.765.432/0001-10")


def _com(notify_invoice, notify_bl):
    return rodar([doc("invoice", numero="1", consignatario=CAPITAL, adquirente=CLIENTE, notify=notify_invoice)],
                 [doc("conhecimento", subtipo="BL", consignatario=CAPITAL, notify=notify_bl)])


def _do_notify(r):
    return [d.mensagem for d in r.divergencias if "notify da invoice" in d.mensagem]


def test_notify_do_bl_diferente_do_da_invoice_e_apontado():
    assert _do_notify(_com(OUTRO, CLIENTE))


def test_notify_capital_no_bl_com_cliente_como_notify_na_invoice_e_apontado():
    assert _do_notify(_com(CLIENTE, CAPITAL))


def test_mesmo_notify_passa_com_o_nome_escrito_diferente():
    assert not _do_notify(_com(CLIENTE, ("LUME BICICLETAS COMERCIO LTDA.", "12345678000190")))


def test_sem_notify_na_invoice_capital_ou_cliente_passam():
    for notify in (CAPITAL, CLIENTE):
        r = _com(None, notify)
        assert not _do_notify(r)
        assert not any(a.startswith("Notify do") for a in r.avisos)
