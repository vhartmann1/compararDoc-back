"""Valor de cada coluna num campo: o do documento, o da duplicata que traz o campo ou a soma dos documentos."""

from dataclasses import replace

from app.schemas import Divergencia, NomeCampo
from app.services.comparacao.campos.regras_por_campo.regra import Regra
from app.services.comparacao.constantes import (
    CAMPOS_DIVERGENTES_NA_SOMA,
    CAMPOS_FORA_DO_CONHECIMENTO,
    CAMPOS_SOMADOS,
    CAMPOS_UNICOS_NA_SOMA,
    ROTULOS,
)
from app.services.comparacao.documentos.identificacao_do_documento import nome_doc
from app.services.comparacao.tipos import Col, Contexto, Fonte, Valor


def valores_das_colunas(ctx: Contexto, campo: NomeCampo, regra: Regra, colunas: list[Col]) -> dict[str, Valor | None]:
    """O valor de cada coluna; vazio nas colunas em que a regra diz que o campo não se confere."""
    vazias = regra.vazio_em(colunas) if regra.vazio_em else set()
    return {col.chave: None if col.chave in vazias else _valor_coluna(ctx, col, campo, regra) for col in colunas}


def valor_do_documento(ctx: Contexto, f: Fonte, campo: NomeCampo, regra: Regra) -> Valor | None:
    """Valor do documento escolhido; se ele não traz o campo, o da primeira duplicata que traz."""
    valor = regra.obter(f, campo, ctx)
    for dup in f.duplicatas:
        if valor is not None:
            break
        valor = regra.obter(replace(dup, invoice_par=f.invoice_par), campo, ctx)
        if valor is not None:
            aviso = f"{ROTULOS[campo]} de {nome_doc(f)} tirado de {dup.arquivo.nome} (o arquivo usado não traz)."
            if aviso not in ctx.avisos:
                ctx.avisos.append(aviso)
    return valor


def _valor_coluna(ctx: Contexto, col: Col, campo: NomeCampo, regra: Regra) -> Valor | None:
    if campo in CAMPOS_FORA_DO_CONHECIMENTO and col.so_conhecimento():
        return None
    valores = [valor_do_documento(ctx, f, campo, regra) for f in col.fontes]
    if not col.soma or len(valores) == 1:
        return valores[0]
    presentes = [v for v in valores if v is not None]
    if not presentes:
        return None
    if campo in CAMPOS_SOMADOS and len(presentes) < len(valores):
        faltando = [nome_doc(f) for f, v in zip(col.fontes, valores) if v is None]
        ctx.avisos.append(
            f"{ctx.prefixo}{ROTULOS[campo]}: soma incompleta em \"{col.rotulo}\" — "
            f"falta o valor em {', '.join(faltando)}."
        )
        return None
    soma = regra.juntar(presentes, campo, ctx, col)
    if soma is not None and campo in CAMPOS_DIVERGENTES_NA_SOMA and len(soma.chave) > 1:
        partes = [f"{nome_doc(f)} {v.exibicao}" for f, v in zip(col.fontes, valores) if v is not None]
        ctx.divergentes_na_soma.add(campo)
        ctx.divergencias.append(
            Divergencia(
                categoria="comparacao",
                comparacao_id=ctx.comparacao_id,
                campo=campo,
                mensagem=f"{ctx.prefixo}{ROTULOS[campo]}: {' × '.join(partes)}",
            )
        )
    if soma is not None and campo in CAMPOS_UNICOS_NA_SOMA and len(soma.chave) > 1:
        ctx.avisos.append(
            f"{ctx.prefixo}{ROTULOS[campo]}: os documentos de \"{col.rotulo}\" "
            f"não trazem o mesmo valor ({soma.exibicao})."
        )
    return soma
