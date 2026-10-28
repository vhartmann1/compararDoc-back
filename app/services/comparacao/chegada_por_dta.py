"""AWB que chega em Guarulhos/Viracopos com destino em SC na invoice: vem por DTA, aviso em vez de divergência."""

from app.services.comparacao.conhecimento_com_parte import so_conhecimento
from app.services.comparacao.normalizacao import normalizar_porto, uf_do_porto
from app.services.comparacao.tipos import Col, Contexto, Valor

AEROPORTOS_DA_DTA = {normalizar_porto(a) for a in ("GUARULHOS", "VIRACOPOS")}


def separar_chegada_por_dta(
    ctx: Contexto, informados: list[tuple[Col, Valor]]
) -> tuple[list[tuple[Col, Valor]], str | None]:
    """(colunas que seguem na comparação, aviso); o AWB que chega por DTA sai se as invoices/PLs indicam SC."""
    outros = [(col, v) for col, v in informados if not so_conhecimento(col)]
    if not outros or not all(_em_sc(v) for _, v in outros):
        return informados, None
    por_dta = [(col, v) for col, v in informados if _chega_por_dta(col, v)]
    if not por_dta:
        return informados, None
    return [(col, v) for col, v in informados if not _chega_por_dta(col, v)], _aviso(ctx, por_dta, outros)


def _chega_por_dta(col: Col, valor: Valor) -> bool:
    """AWB cujas alternativas (descarga e entrega) são todas Guarulhos/Viracopos."""
    awb = so_conhecimento(col) and all("AWB" in (f.doc.subtipo or "").upper() for f in col.fontes)
    return awb and all(alternativas <= AEROPORTOS_DA_DTA for alternativas in valor.chave)


def _em_sc(valor: Valor) -> bool:
    return all(uf_do_porto(p) == "SC" for alternativas in valor.chave for p in alternativas)


def _aviso(ctx: Contexto, por_dta: list[tuple[Col, Valor]], outros: list[tuple[Col, Valor]]) -> str:
    chegada = " / ".join(f"{col.nome_curto} chega em {v.exibicao}" for col, v in por_dta)
    destino = " / ".join(dict.fromkeys(v.exibicao for _, v in outros))
    return f"{ctx.prefixo}Porto de destino: {chegada} e a invoice indica {destino}: confirmar DTA com o cliente/agente."
