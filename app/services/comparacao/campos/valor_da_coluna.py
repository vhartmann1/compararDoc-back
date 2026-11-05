"""Valor de cada coluna num campo: o do documento, o da duplicata que traz o campo ou a soma dos documentos."""

from dataclasses import dataclass, replace

from app.schemas import NomeCampo
from app.services.comparacao.campos.regras_por_campo.regra import Regra
from app.services.comparacao.constantes import (
    CAMPOS_DIVERGENTES_NA_SOMA,
    CAMPOS_FORA_DO_CONHECIMENTO,
    CAMPOS_SOMADOS,
    CAMPOS_UNICOS_NA_SOMA,
    ROTULOS,
)
from app.services.comparacao.documentos.identificacao_do_documento import nome_doc
from app.services.comparacao.mensagens import Diferenca, divergencia
from app.services.comparacao.tipos import Apontamentos, Col, Contexto, Fonte, Valor


@dataclass
class ValoresDoCampo:
    """O valor de cada coluna e o que se apontou ao montá-los; divergência aqui só vem da soma de uma coluna."""

    valores: dict[str, Valor | None]
    apontamentos: Apontamentos


def valores_das_colunas(ctx: Contexto, campo: NomeCampo, regra: Regra, colunas: list[Col]) -> ValoresDoCampo:
    """O valor de cada coluna; vazio nas colunas em que a regra diz que o campo não se confere."""
    vazias = regra.vazio_em(colunas) if regra.vazio_em else set()
    valores: dict[str, Valor | None] = {}
    apontamentos = Apontamentos()
    for col in colunas:
        valor, da_coluna = (None, Apontamentos()) if col.chave in vazias else _valor_coluna(ctx, col, campo, regra)
        valores[col.chave] = valor
        apontamentos += da_coluna
    return ValoresDoCampo(valores, apontamentos)


def valor_do_documento(ctx: Contexto, f: Fonte, campo: NomeCampo, regra: Regra) -> tuple[Valor | None, list[str]]:
    """Valor do documento escolhido; se ele não traz o campo, o da primeira duplicata que traz."""
    valor, avisos = _obter(ctx, f, campo, regra)
    for dup in f.duplicatas:
        if valor is not None:
            break
        valor, da_duplicata = _obter(ctx, replace(dup, invoice_par=f.invoice_par), campo, regra)
        avisos += da_duplicata
        if valor is not None:
            avisos.append(f"{ROTULOS[campo]} de {nome_doc(f)} tirado de {dup.arquivo.nome} (o arquivo usado não traz).")
    return valor, avisos


def _obter(ctx: Contexto, f: Fonte, campo: NomeCampo, regra: Regra) -> tuple[Valor | None, list[str]]:
    valor = regra.obter(f, campo, ctx)
    if valor is None and regra.aviso_sem_valor and (aviso := regra.aviso_sem_valor(f, campo, ctx)):
        return None, [aviso]
    return valor, []


def _valor_coluna(ctx: Contexto, col: Col, campo: NomeCampo, regra: Regra) -> tuple[Valor | None, Apontamentos]:
    if campo in CAMPOS_FORA_DO_CONHECIMENTO and col.so_conhecimento():
        return None, Apontamentos()
    lidos = [valor_do_documento(ctx, f, campo, regra) for f in col.fontes]
    valores = [v for v, _ in lidos]
    avisos = [a for _, avisos in lidos for a in avisos]
    if not col.soma or len(valores) == 1:
        return valores[0], Apontamentos(avisos)
    presentes = [v for v in valores if v is not None]
    if not presentes:
        return None, Apontamentos(avisos)
    if campo in CAMPOS_SOMADOS and len(presentes) < len(valores):
        faltando = [nome_doc(f) for f, v in zip(col.fontes, valores) if v is None]
        return None, Apontamentos(avisos + [
            f"{ctx.prefixo}{ROTULOS[campo]}: soma incompleta em \"{col.rotulo}\" — "
            f"falta o valor em {', '.join(faltando)}."
        ])
    soma, da_soma = _somar(ctx, col, campo, regra, presentes, valores)
    return soma, Apontamentos(avisos) + da_soma


def _somar(
    ctx: Contexto, col: Col, campo: NomeCampo, regra: Regra, presentes: list[Valor], valores: list[Valor | None]
) -> tuple[Valor | None, Apontamentos]:
    """A soma dos documentos da coluna, com a divergência ou o aviso quando eles não trazem o mesmo valor."""
    soma = regra.juntar(presentes, campo, ctx, col)
    if soma is None:
        aviso = regra.aviso_sem_soma(presentes, ctx, col) if regra.aviso_sem_soma else None
        return None, Apontamentos([aviso] if aviso else [])
    apontamentos = Apontamentos()
    if campo in CAMPOS_DIVERGENTES_NA_SOMA and len(soma.chave) > 1:
        partes = [f"{nome_doc(f)} {v.exibicao}" for f, v in zip(col.fontes, valores) if v is not None]
        apontamentos.divergencias.append(divergencia("comparacao", ctx.comparacao_id, campo, ctx.origem,
                                                     ROTULOS[campo], Diferenca(" × ".join(partes))))
    if campo in CAMPOS_UNICOS_NA_SOMA and len(soma.chave) > 1:
        apontamentos.avisos.append(
            f"{ctx.prefixo}{ROTULOS[campo]}: os documentos de \"{col.rotulo}\" "
            f"não trazem o mesmo valor ({soma.exibicao})."
        )
    return soma, apontamentos
