"""Conhecimento que cita como PO o nº de uma invoice do processo: é a referência da invoice, só aviso."""

from app.services.comparacao.campos.regras_por_campo.ncm_invoice_po_portos import numeros_contidos
from app.services.comparacao.campos.regras_por_campo.regra import Informados
from app.services.comparacao.normalizacao.numeros_de_documento import normalizar_po
from app.services.comparacao.tipos import Col, Contexto, Valor


def separar_po_que_e_numero_da_invoice(ctx: Contexto, informados: Informados) -> tuple[Informados, str | None]:
    """(colunas que seguem na comparação, aviso); sai o conhecimento contido nos POs ou só com nº de invoice."""
    numeros = {normalizar_po(f.doc.numero) for col, _ in informados for f in col.fontes
               if f.doc.tipo == "invoice" and f.doc.numero}
    citam_invoice = [col.chave for col, v in informados if col.so_conhecimento() and v.chave <= numeros]
    restantes = [(col, v) for col, v in informados
                 if col.chave not in citam_invoice and not _contido(col, v, informados)]
    if not citam_invoice:
        return restantes, None
    quem = " / ".join(f"{col.nome_curto} {v.exibicao}" for col, v in informados if col.chave in citam_invoice)
    return restantes, f"{ctx.prefixo}PO: {quem} é o nº da invoice, não um PO; conferido com o nº da invoice."


def _contido(col: Col, valor: Valor, informados: Informados) -> bool:
    """Conhecimento com parte dos POs das invoices/PLs: confere (a regra comum do PO)."""
    outros = [v for c, v in informados if not c.so_conhecimento()]
    return col.so_conhecimento() and bool(outros) and all(numeros_contidos(valor.chave, o.chave) for o in outros)
