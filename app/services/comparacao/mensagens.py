"""Pedaços que se repetem nas mensagens: o que pedir, o que conferir e a divergência interna de um documento."""

from app.schemas import Divergencia
from app.services.comparacao.documentos.identificacao_do_documento import nome_doc, ref_documento
from app.services.comparacao.tipos import Fonte


def pedir(mensagem: str, o_que: str) -> str:
    """'a soma não bate', 'correção' -> 'a soma não bate; pedir correção.'"""
    return f"{mensagem}; pedir {o_que}."


def confira(mensagem: str, como: str | None = None) -> str:
    """'unidades diferentes', 'manualmente' -> 'unidades diferentes; confira manualmente.'"""
    return f"{mensagem}; confira {como}." if como else f"{mensagem}; confira."


def divergencia_interna(
    f: Fonte, mensagem: str, evidencia: str | None = None, pagina: int | None = None
) -> Divergencia:
    """Contradição dentro do próprio documento, com o nome dele na frente da mensagem."""
    return Divergencia(categoria="interna", comparacao_id=None, campo=None, mensagem=f"{nome_doc(f)}: {mensagem}",
                       documento=ref_documento(f), evidencia=evidencia, pagina=pagina)
