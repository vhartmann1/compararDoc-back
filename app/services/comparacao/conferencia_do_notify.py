"""Notify do conhecimento: a própria Capital ou o adquirente (cliente) da invoice; outra empresa vira aviso."""

from app.schemas import Parte
from app.services.comparacao.identificacao_do_documento import nome_doc
from app.services.comparacao.mesma_empresa import relacao_entre_partes
from app.services.comparacao.regras_por_campo.exportador_consignatario import parte_da_capital
from app.services.comparacao.tipos import Fonte


def avisos_do_notify(invoices_e_pls: list[Fonte], conhecimentos: list[Fonte]) -> list[str]:
    clientes = _clientes(invoices_e_pls)
    return [aviso for c in conhecimentos if (aviso := _aviso(c, clientes))]


def _clientes(fontes: list[Fonte]) -> list[Parte]:
    """O adquirente da invoice/PL; sem adquirente, o consignatário/notify que não é a Capital."""
    adquirentes = _fora_da_capital([f.doc.adquirente for f in fontes])
    return adquirentes or _fora_da_capital([p for f in fontes for p in (f.doc.consignatario, f.doc.notify)])


def _fora_da_capital(partes: list[Parte | None]) -> list[Parte]:
    return [p for p in partes if p and p.nome.strip() and not parte_da_capital(p)]


def _aviso(conhecimento: Fonte, clientes: list[Parte]) -> str | None:
    notify = conhecimento.doc.notify
    if notify is None or not notify.nome.strip() or parte_da_capital(notify) or not clientes:
        return None
    if any(relacao_entre_partes(notify, cliente) != "outra" for cliente in clientes):
        return None
    nomes = " / ".join(dict.fromkeys(c.nome.strip() for c in clientes))
    return (f"Notify do {nome_doc(conhecimento)} ({notify.nome.strip()}) não é a Capital Trade nem o adquirente "
            f"da invoice ({nomes}); confira.")
