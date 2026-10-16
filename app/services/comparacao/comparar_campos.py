"""Comparação campo a campo e status de cada campo."""

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from app.schemas import CampoComparado, Coluna, Comparacao, Divergencia, NomeCampo, StatusCampo, ValorCampo
from app.services.comparacao.constantes import (
    CAMPOS_DIVERGENTES_NA_SOMA,
    CAMPOS_FORA_DO_CONHECIMENTO,
    CAMPOS_SEM_AVISO_INSUFICIENTE,
    CAMPOS_SEMPRE_VISIVEIS,
    CAMPOS_SOMADOS,
    CAMPOS_UNICOS_NA_SOMA,
    MODALIDADES_CAPITAL_CONSIGNATARIA,
    ROTULOS,
)
from app.services.comparacao.identificacao_do_documento import nome_doc, ref_documento
from app.services.comparacao.regras_por_campo.exportador_consignatario import conhecimento_consignado_a_capital
from app.services.comparacao.regras_por_campo.pesos_volumes_quantidade import embalagens_distintas, nota_fator_mil
from app.services.comparacao.regras_por_campo.regra import Regra
from app.services.comparacao.regras_por_campo.regra_de_cada_campo import REGRAS
from app.services.comparacao.tipos import Col, Contexto, Fonte, Valor


def comparar_colunas(ctx: Contexto, colunas: list[Col]) -> Comparacao:
    campos: list[CampoComparado] = []
    for campo, regra in REGRAS.items():
        valores = {col.chave: _valor_coluna(ctx, col, campo, regra) for col in colunas}
        if campo not in CAMPOS_SEMPRE_VISIVEIS and all(v is None for v in valores.values()):
            continue
        status = _status_campo(ctx, campo, regra, colunas, valores)
        campos.append(
            CampoComparado(
                campo=campo,
                rotulo=ROTULOS[campo],
                status=status,
                valores={chave: _para_valor_campo(v) for chave, v in valores.items()},
            )
        )
    return Comparacao(
        id=ctx.comparacao_id,
        titulo=" × ".join(col.rotulo for col in colunas),
        colunas=[Coluna(chave=c.chave, rotulo=c.rotulo, documentos=[ref_documento(f) for f in c.fontes]) for c in colunas],
        campos=campos,
    )


def _valor_do_documento(ctx: Contexto, f: Fonte, campo: NomeCampo, regra: Regra) -> Valor | None:
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
    if campo in CAMPOS_FORA_DO_CONHECIMENTO and all(f.doc.tipo == "conhecimento" for f in col.fontes):
        return None
    valores = [_valor_do_documento(ctx, f, campo, regra) for f in col.fontes]
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


def _status_campo(
    ctx: Contexto, campo: NomeCampo, regra: Regra, colunas: list[Col], valores: dict[str, Valor | None]
) -> StatusCampo:
    if campo in ctx.divergentes_na_soma:
        return "DIVERGENTE"  # mensagem já registrada ao montar a soma
    informados = [(col, valores[col.chave]) for col in colunas if valores[col.chave] is not None]
    if not informados:
        return "NAO_ENCONTRADO"
    if campo == "consignatario" and ctx.modalidade in MODALIDADES_CAPITAL_CONSIGNATARIA:
        restantes = [(col, v) for col, v in informados if not conhecimento_consignado_a_capital(col, v)]
        if len(restantes) < len(informados):
            aceitos = ", ".join(col.nome_curto for col, v in informados if (col, v) not in restantes)
            ctx.avisos.append(
                f"{ctx.prefixo}Consignatário: {aceitos} em nome da Capital Trade — aceito pela modalidade "
                f"{'conta e ordem' if ctx.modalidade == 'conta_e_ordem' else 'encomenda'}."
            )
            if len(restantes) <= 1:
                return "OK"
            informados = restantes
    if len(informados) == 1:
        if len(colunas) > 1 and campo not in CAMPOS_SEM_AVISO_INSUFICIENTE:
            ctx.avisos.append(
                f"{ctx.prefixo}{ROTULOS[campo]} informado só em {informados[0][0].nome_curto}; "
                "nada com o que comparar."
            )
        return "INSUFICIENTE"

    iguais = regra.iguais
    if campo == "quantidade":
        unidades = {v.chave[0] for _, v in informados}
        if len(unidades) > 1:
            textos = " × ".join(f"{col.nome_curto} {v.exibicao}" for col, v in informados)
            ctx.avisos.append(
                f"{ctx.prefixo}Quantidade em unidades que não dá para comparar ({textos}); confira manualmente."
            )
            return "INSUFICIENTE"
    if campo == "ncm":
        iguais = _iguais_ncm(ctx, [v for _, v in informados])

    grupos: list[tuple[list[Col], Valor]] = []
    for col, valor in informados:
        for cols, referencia in grupos:
            if iguais(referencia.chave, valor.chave):
                cols.append(col)
                break
        else:
            grupos.append(([col], valor))
    if len(grupos) == 1:
        return "OK"
    if campo == "volumes" and embalagens_distintas([valor for _, valor in grupos]):
        textos = " × ".join(f"{'/'.join(c.nome_curto for c in cols)} {valor.exibicao}" for cols, valor in grupos)
        ctx.avisos.append(f"{ctx.prefixo}Volumes em embalagens diferentes ({textos}); confira manualmente.")
        return "INSUFICIENTE"

    ordenados = sorted(grupos, key=lambda g: len(g[0]))  # minoria primeiro
    partes = [f"{'/'.join(c.nome_curto for c in cols)} {valor.exibicao}" for cols, valor in ordenados]
    nota = ""
    if campo == "quantidade":
        nota = nota_fator_mil([(v.chave[1], v.exibicao, v.unidade) for _, v in grupos])
    ctx.divergencias.append(
        Divergencia(
            categoria="comparacao",
            comparacao_id=ctx.comparacao_id,
            campo=campo,
            mensagem=f"{ctx.prefixo}{ROTULOS[campo]}: {' × '.join(partes)}{nota}",
        )
    )
    return "DIVERGENTE"


def _iguais_ncm(ctx: Contexto, valores: list[Valor]) -> Callable[[Any, Any], bool]:
    """Compara com 8 dígitos; se algum documento só traz HS (6) ou posição (4), compara por aí."""
    menor = min(len(c) for v in valores for c in v.chave)
    digitos = 8 if menor >= 8 else 6 if menor >= 6 else 4
    if digitos < 8:
        ctx.avisos.append(
            f"{ctx.prefixo}NCM comparado pelos {digitos} primeiros dígitos "
            "(algum documento traz só o HS Code ou a posição)."
        )
    return lambda a, b: {c[:digitos] for c in a} == {c[:digitos] for c in b}


def _para_valor_campo(v: Valor | None) -> ValorCampo | None:
    if v is None:
        return None
    return ValorCampo(exibicao=v.exibicao, texto_original=v.texto_original, arquivo_id=v.arquivo_id, pagina=v.pagina)
