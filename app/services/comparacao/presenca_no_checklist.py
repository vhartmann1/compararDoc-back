"""Checklist da fatura: o que a invoice tem de trazer (CNPJ do consignatário, fabricante, volumes)."""

import re

from app.schemas import Divergencia
from app.services.comparacao.identificacao_do_documento import nome_doc
from app.services.comparacao.mensagens import divergencia_interna, pedir
from app.services.comparacao.normalizacao.texto import sem_acento
from app.services.comparacao.parte_preenchida import parte_preenchida
from app.services.comparacao.tipos import Fonte

SEM_NOME = re.compile(
    r"(DESCONHECID[OA]|UNKNOWN|N/?A|NAO INFORMADO|NOT (INFORMED|AVAILABLE|SPECIFIED)|TB[AD]|[-?.]+)"
)


def divergencias_do_checklist(invoices: list[Fonte]) -> list[Divergencia]:
    return [_interna(f, m) for f in invoices if (m := _sem_cnpj(f))]


def _sem_cnpj(f: Fonte) -> str | None:
    p = f.doc.consignatario
    if not parte_preenchida(p) or (p.cnpj and p.cnpj.strip()):
        return None
    return "consignatário sem CNPJ (o checklist da fatura pede o importador com CNPJ)"


def _interna(f: Fonte, mensagem: str) -> Divergencia:
    return divergencia_interna(f, mensagem, pagina=f.doc.paginas[0] if f.doc.paginas else None)


def avisos_do_checklist(grupos: list[tuple[Fonte | None, Fonte | None]], conhecimentos: list[Fonte]) -> list[str]:
    avisos = []
    for inv, pl in grupos:
        if inv is None:
            continue
        avisos += [m for m in (_fabricante_sem_nome(inv), _sem_volumes(inv, [pl, *conhecimentos])) if m]
    return avisos


def _fabricante_sem_nome(f: Fonte) -> str | None:
    """'FACTORY: UNKNOWN': o campo existe, mas sem o nome do fabricante."""
    p = f.doc.fabricante
    if p is None or not SEM_NOME.fullmatch(sem_acento(p.nome).upper().strip()):
        return None
    return pedir(f"{nome_doc(f)}: fabricante sem nome ('{p.nome.strip()}')", "inclusão")


def _sem_volumes(f: Fonte, outros: list[Fonte | None]) -> str | None:
    """Invoice sem quantidade nem espécie de volumes, que o PL ou o conhecimento traz."""
    com_volumes = next((o for o in outros if o and o.doc.volumes_total), None)
    if f.doc.volumes_total or com_volumes is None:
        return None
    return pedir(f"{nome_doc(f)}: sem quantidade e espécie de volumes ({nome_doc(com_volumes)} traz "
                 f"{com_volumes.doc.volumes_total.texto_original})", "inclusão")
