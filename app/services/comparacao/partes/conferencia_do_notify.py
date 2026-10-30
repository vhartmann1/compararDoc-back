"""Notify do conhecimento: o da invoice, se ela tem; senão a Capital ou o adquirente (outra empresa vira aviso)."""

from app.schemas import Divergencia, Parte
from app.services.comparacao.documentos.identificacao_do_documento import nome_doc, ref_documento
from app.services.comparacao.mensagens import confira
from app.services.comparacao.partes.capital import parte_da_capital
from app.services.comparacao.partes.mesma_empresa import relacao_entre_partes
from app.services.comparacao.partes.parte_preenchida import parte_preenchida
from app.services.comparacao.tipos import Fonte


def divergencias_do_notify(invoices: list[Fonte], conhecimentos: list[Fonte]) -> list[Divergencia]:
    pedidos = _preenchidas([f.doc.notify for f in invoices])
    return [d for c in conhecimentos if pedidos and (d := _outro_que_o_da_invoice(c, pedidos))]


def avisos_do_notify(invoices: list[Fonte], invoices_e_pls: list[Fonte], conhecimentos: list[Fonte]) -> list[str]:
    if _preenchidas([f.doc.notify for f in invoices]):
        return []  # a invoice diz qual é o notify: vale `divergencias_do_notify`
    clientes = _clientes(invoices_e_pls)
    return [aviso for c in conhecimentos if (aviso := _aviso(c, clientes))]


def _outro_que_o_da_invoice(conhecimento: Fonte, pedidos: list[Parte]) -> Divergencia | None:
    notify = conhecimento.doc.notify
    if not parte_preenchida(notify):
        return None
    if any(relacao_entre_partes(notify, pedido) != "outra" for pedido in pedidos):
        return None
    nomes = " / ".join(dict.fromkeys(p.nome.strip() for p in pedidos))
    return Divergencia(
        categoria="comparacao", comparacao_id=None, campo="adquirente", documento=ref_documento(conhecimento),
        mensagem=f"Notify do {nome_doc(conhecimento)} ({notify.nome.strip()}) diferente do notify da invoice ({nomes})",
        pagina=notify.pagina,
    )


def _preenchidas(partes: list[Parte | None]) -> list[Parte]:
    return [p for p in partes if parte_preenchida(p)]


def _clientes(fontes: list[Fonte]) -> list[Parte]:
    """O adquirente da invoice/PL; sem adquirente, o consignatário/notify que não é a Capital."""
    adquirentes = _fora_da_capital([f.doc.adquirente for f in fontes])
    return adquirentes or _fora_da_capital([p for f in fontes for p in (f.doc.consignatario, f.doc.notify)])


def _fora_da_capital(partes: list[Parte | None]) -> list[Parte]:
    return [p for p in _preenchidas(partes) if not parte_da_capital(p)]


def _aviso(conhecimento: Fonte, clientes: list[Parte]) -> str | None:
    notify = conhecimento.doc.notify
    if not parte_preenchida(notify) or parte_da_capital(notify) or not clientes:
        return None
    if any(relacao_entre_partes(notify, cliente) != "outra" for cliente in clientes):
        return None
    nomes = " / ".join(dict.fromkeys(c.nome.strip() for c in clientes))
    return confira(f"Notify do {nome_doc(conhecimento)} ({notify.nome.strip()}) não é a Capital Trade nem o "
                   f"adquirente da invoice ({nomes})")
