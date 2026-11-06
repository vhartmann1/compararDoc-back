"""Campos do exportador com conhecimento triangular: ele só confere com as invoices/PLs da mesma empresa."""

from app.schemas import NomeCampo, StatusCampo
from app.services.comparacao.campos.regras_por_campo.regra import Regra
from app.services.comparacao.campos.status_do_campo import Status, status_do_campo
from app.services.comparacao.campos.valor_da_coluna import valor_do_documento
from app.services.comparacao.constantes import ROTULOS
from app.services.comparacao.mensagens import Diferenca, divergencia
from app.services.comparacao.partes.operacao_triangular import (
    Triangulacao,
    coluna_das_proprias,
    da_mesma_empresa,
    empresa_do_shipper,
    texto_contra_as_proprias,
)
from app.services.comparacao.tipos import Apontamentos, Col, Contexto, Fonte, Valor


def status_com_triangulacao(
    ctx: Contexto, campo: NomeCampo, regra: Regra, colunas: list[Col], valores: dict[str, Valor | None],
    triangulares: list[Triangulacao], divergente_na_soma: bool = False,
) -> Status:
    """Conhecimento triangular fora da comparação geral; só confere com as invoices/PLs da mesma empresa."""
    chaves = {c.chave for t in triangulares for c in (t.conhecimento, *t.acompanham)}
    restantes = [col for col in colunas if col.chave not in chaves]
    geral = _informados(restantes, valores) > 1
    conferidos = [status_do_campo(ctx, campo, regra, restantes, valores, divergente_na_soma)] if geral else []
    conferidos += [_conferir_com_as_proprias(ctx, campo, regra, t, valores) for t in triangulares]
    apontamentos = sum((a for _, a in conferidos), Apontamentos())
    if status := [s for s, _ in conferidos if s]:
        return _status_mais_grave(status), apontamentos
    status: StatusCampo = "INSUFICIENTE" if any(v is not None for v in valores.values()) else "NAO_ENCONTRADO"
    return status, apontamentos


def _conferir_com_as_proprias(
    ctx: Contexto, campo: NomeCampo, regra: Regra, t: Triangulacao, valores: dict[str, Valor | None]
) -> tuple[StatusCampo | None, Apontamentos]:
    """Conhecimento × invoices/PLs da mesma empresa do shipper; status None se falta um dos lados."""
    conhecimento = valores[t.conhecimento.chave]
    col = coluna_das_proprias(t)
    lidos = [valor_do_documento(ctx, f, campo, regra) for f in t.proprias]
    avisos = [a for _, avisos in lidos for a in avisos]
    presentes = [v for v, _ in lidos if v is not None]
    if conhecimento is None or not presentes:
        return None, Apontamentos(avisos)
    proprias = presentes[0] if len(presentes) == 1 else regra.juntar(presentes, campo, ctx, col)
    if regra.iguais(proprias.chave, conhecimento.chave):
        return "OK", Apontamentos(avisos)
    lados, dos_lados = _lados_que_divergem(ctx, campo, regra, t, conhecimento)
    if lados:
        rotulo = f"{ROTULOS[campo]} ({empresa_do_shipper(t)})"
        diferenca = texto_contra_as_proprias(t, conhecimento, lados, cortar=campo == "endereco_exportador")
    else:
        rotulo = ROTULOS[campo]
        diferenca = Diferenca(f"{t.conhecimento.nome_curto} {conhecimento.exibicao} × "
                              f"{col.nome_curto} {proprias.exibicao}")
    apontada = divergencia("comparacao", ctx.comparacao_id, campo, ctx.origem, rotulo, diferenca)
    return "DIVERGENTE", Apontamentos(avisos + dos_lados, [apontada])


def _lados_que_divergem(
    ctx: Contexto, campo: NomeCampo, regra: Regra, t: Triangulacao, conhecimento: Valor
) -> tuple[list[tuple[Fonte, Valor]], list[str]]:
    """Os documentos da mesma empresa do shipper que divergem do conhecimento; sem nenhum, os das próprias."""
    avisos: list[str] = []
    for fontes in (da_mesma_empresa(t), t.proprias):
        lados, lidos = _um_por_valor(ctx, campo, regra, fontes, conhecimento)
        avisos += lidos
        if lados:
            return lados, avisos
    return [], avisos


def _um_por_valor(
    ctx: Contexto, campo: NomeCampo, regra: Regra, fontes: list[Fonte], conhecimento: Valor
) -> tuple[list[tuple[Fonte, Valor]], list[str]]:
    """O primeiro documento de cada valor diferente do conhecimento, e os avisos da leitura dos valores."""
    lados: list[tuple[Fonte, Valor]] = []
    avisos: list[str] = []
    for f in fontes:
        v, lidos = valor_do_documento(ctx, f, campo, regra)
        avisos += lidos
        if v is not None and not any(regra.iguais(v.chave, o.chave) for o in [conhecimento, *(x for _, x in lados)]):
            lados.append((f, v))
    return lados, avisos


def _informados(colunas: list[Col], valores: dict[str, Valor | None]) -> int:
    return sum(valores[col.chave] is not None for col in colunas)


def _status_mais_grave(status: list[StatusCampo]) -> StatusCampo:
    """DIVERGENTE vence INSUFICIENTE, que vence OK."""
    return next(s for s in ("DIVERGENTE", "INSUFICIENTE", "OK", "NAO_ENCONTRADO") if s in status)
