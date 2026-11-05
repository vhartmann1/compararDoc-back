"""Campos do exportador com conhecimento triangular: ele só confere com as invoices/PLs da mesma empresa."""

from app.schemas import Divergencia, NomeCampo, StatusCampo
from app.services.comparacao.campos.regras_por_campo.regra import Regra
from app.services.comparacao.campos.status_do_campo import status_do_campo
from app.services.comparacao.campos.valor_da_coluna import valor_do_documento
from app.services.comparacao.constantes import ROTULOS
from app.services.comparacao.partes.operacao_triangular import (
    Triangulacao,
    coluna_das_proprias,
    da_mesma_empresa,
    texto_contra_as_proprias,
)
from app.services.comparacao.tipos import Col, Contexto, Fonte, Valor


def status_com_triangulacao(
    ctx: Contexto, campo: NomeCampo, regra: Regra, colunas: list[Col], valores: dict[str, Valor | None],
    triangulares: list[Triangulacao],
) -> StatusCampo:
    """Conhecimento triangular fora da comparação geral; só confere com as invoices/PLs da mesma empresa."""
    chaves = {t.conhecimento.chave for t in triangulares}
    restantes = [col for col in colunas if col.chave not in chaves]
    status = [status_do_campo(ctx, campo, regra, restantes, valores)] if _informados(restantes, valores) > 1 else []
    status += [s for t in triangulares if (s := _conferir_com_as_proprias(ctx, campo, regra, t, valores))]
    if status:
        return _status_mais_grave(status)
    return "INSUFICIENTE" if any(v is not None for v in valores.values()) else "NAO_ENCONTRADO"


def _conferir_com_as_proprias(
    ctx: Contexto, campo: NomeCampo, regra: Regra, t: Triangulacao, valores: dict[str, Valor | None]
) -> StatusCampo | None:
    """Conhecimento × invoices/PLs da mesma empresa do shipper; None se falta um dos lados."""
    conhecimento = valores[t.conhecimento.chave]
    col = coluna_das_proprias(t)
    presentes = [v for f in t.proprias if (v := valor_do_documento(ctx, f, campo, regra)) is not None]
    if conhecimento is None or not presentes:
        return None
    proprias = presentes[0] if len(presentes) == 1 else regra.juntar(presentes, campo, ctx, col)
    if regra.iguais(proprias.chave, conhecimento.chave):
        return "OK"
    if lados := _lados_que_divergem(ctx, campo, regra, t, conhecimento):
        mensagem = texto_contra_as_proprias(f"{ctx.prefixo}{ROTULOS[campo]}", t, conhecimento, lados,
                                            cortar=campo == "endereco_exportador")
    else:
        mensagem = (f"{ctx.prefixo}{ROTULOS[campo]}: {t.conhecimento.nome_curto} {conhecimento.exibicao} × "
                    f"{col.nome_curto} {proprias.exibicao}")
    ctx.divergencias.append(
        Divergencia(categoria="comparacao", comparacao_id=ctx.comparacao_id, campo=campo, mensagem=mensagem)
    )
    return "DIVERGENTE"


def _lados_que_divergem(
    ctx: Contexto, campo: NomeCampo, regra: Regra, t: Triangulacao, conhecimento: Valor
) -> list[tuple[Fonte, Valor]]:
    """Os documentos da mesma empresa do shipper que divergem do conhecimento; sem nenhum, os das próprias."""
    for fontes in (da_mesma_empresa(t), t.proprias):
        if lados := _um_por_valor(ctx, campo, regra, fontes, conhecimento):
            return lados
    return []


def _um_por_valor(
    ctx: Contexto, campo: NomeCampo, regra: Regra, fontes: list[Fonte], conhecimento: Valor
) -> list[tuple[Fonte, Valor]]:
    """O primeiro documento de cada valor diferente do conhecimento."""
    lados: list[tuple[Fonte, Valor]] = []
    for f in fontes:
        v = valor_do_documento(ctx, f, campo, regra)
        if v is not None and not any(regra.iguais(v.chave, o.chave) for o in [conhecimento, *(x for _, x in lados)]):
            lados.append((f, v))
    return lados


def _informados(colunas: list[Col], valores: dict[str, Valor | None]) -> int:
    return sum(valores[col.chave] is not None for col in colunas)


def _status_mais_grave(status: list[StatusCampo]) -> StatusCampo:
    """DIVERGENTE vence INSUFICIENTE, que vence OK."""
    return next(s for s in ("DIVERGENTE", "INSUFICIENTE", "OK", "NAO_ENCONTRADO") if s in status)
