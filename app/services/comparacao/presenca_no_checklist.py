"""Checklist da fatura: o que a invoice tem de trazer (hoje, o CNPJ do consignatário)."""

from app.schemas import Divergencia
from app.services.comparacao.identificacao_do_documento import nome_doc, ref_documento
from app.services.comparacao.tipos import Fonte


def divergencias_do_checklist(invoices: list[Fonte]) -> list[Divergencia]:
    return [_interna(f, m) for f in invoices if (m := _sem_cnpj(f))]


def _sem_cnpj(f: Fonte) -> str | None:
    p = f.doc.consignatario
    if p is None or not p.nome.strip() or (p.cnpj and p.cnpj.strip()):
        return None
    return "consignatário sem CNPJ (o checklist da fatura pede o importador com CNPJ)"


def _interna(f: Fonte, mensagem: str) -> Divergencia:
    return Divergencia(categoria="interna", comparacao_id=None, campo=None, mensagem=f"{nome_doc(f)}: {mensagem}",
                       documento=ref_documento(f), pagina=f.doc.paginas[0] if f.doc.paginas else None)
