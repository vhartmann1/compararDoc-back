"""Conhecimento que traz só parte dos POs ou dos NCMs da invoice confere; o que ele tem a mais continua divergindo."""

from tests.comparacao.apoio import campo, doc, rodar


def _com(po_invoice=None, po_bl=None, ncms_invoice=(), ncms_bl=(), subtipo="BL"):
    return rodar([doc("invoice", numero="1", po=po_invoice, ncms=ncms_invoice),
                  doc("packing_list", numero="1", po=po_invoice, ncms=ncms_invoice)],
                 [doc("conhecimento", subtipo=subtipo, po=po_bl, ncms=ncms_bl)])


def _do_campo(r, nome):
    return [d for d in r.divergencias if d.campo == nome]


def test_bl_sem_um_dos_pos_da_invoice_confere():
    r = _com(po_invoice="PO 4510, PO 4511", po_bl="PO 4510")
    assert not _do_campo(r, "po")
    assert campo(r.comparacoes[0], "po").status == "OK"


def test_bl_com_po_que_a_invoice_nao_tem_diverge():
    assert _do_campo(_com(po_invoice="PO 4510, PO 4511", po_bl="PO 4510, PO 4599"), "po")


def test_po_da_invoice_e_do_pl_diferentes_continua_divergindo_mesmo_com_o_bl_contido():
    r = rodar([doc("invoice", numero="1", po="PO 4510, PO 4511"), doc("packing_list", numero="1", po="PO 4512")],
              [doc("conhecimento", subtipo="BL", po="PO 4510")])
    assert _do_campo(r, "po")


def test_awb_com_hs_de_seis_digitos_de_parte_dos_ncms_confere():
    r = _com(ncms_invoice=["8714.91.20", "8714.99.90"], ncms_bl=["8714.91"], subtipo="AWB")
    assert not _do_campo(r, "ncm")


def test_conhecimento_com_ncm_a_mais_continua_divergindo():
    r = _com(ncms_invoice=["8714.91.20", "8714.99.90"], ncms_bl=["8714.91", "4011.50"], subtipo="AWB")
    assert _do_campo(r, "ncm")


def test_conhecimento_com_posicao_que_nao_e_de_nenhum_ncm_da_invoice_diverge():
    assert _do_campo(_com(ncms_invoice=["8714.91.20"], ncms_bl=["8714.99"]), "ncm")
