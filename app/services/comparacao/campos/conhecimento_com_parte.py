"""Conhecimento que traz só parte dos POs/NCMs da invoice/PL: confere com eles e sai da comparação do campo."""

from app.services.comparacao.campos.regras_por_campo.regra import Regra
from app.services.comparacao.tipos import Col, Valor


def conhecimentos_contidos(regra: Regra, informados: list[tuple[Col, Valor]]) -> set[str]:
    """Chaves das colunas de conhecimento contidas no valor de todas as invoices/PLs."""
    outros = [v for col, v in informados if not col.so_conhecimento()]
    if regra.contido_no_outro is None or not outros:
        return set()
    return {col.chave for col, v in informados
            if col.so_conhecimento() and all(regra.contido_no_outro(v.chave, o.chave) for o in outros)}
