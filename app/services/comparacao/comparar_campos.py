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
    ROTULOS,
)
from app.services.comparacao.consignatario_pela_modalidade import separar_conhecimentos_da_capital
from app.services.comparacao.identificacao_do_documento import nome_doc, ref_documento
from app.services.comparacao.pareamento_invoice_packing_list import pls_em_outra_numeracao
from app.services.comparacao.operacao_triangular import (
    CAMPOS_DO_EXPORTADOR,
    Triangulacao,
    aviso_triangular,
    coluna_das_proprias,
    triangulacoes,
)
from app.services.comparacao.regras_por_campo.pesos_volumes_quantidade import embalagens_distintas, nota_fator_mil
from app.services.comparacao.regras_por_campo.regra import Regra
from app.services.comparacao.regras_por_campo.regra_de_cada_campo import REGRAS
from app.services.comparacao.tipos import Col, Contexto, Fonte, Valor


def comparar_colunas(ctx: Contexto, colunas: list[Col]) -> Comparacao:
    campos: list[CampoComparado] = []
    triangulares = triangulacoes(colunas)
    ctx.avisos.extend(aviso_triangular(ctx.prefixo, t) for t in triangulares)
    sem_numero = _pls_sem_numero_de_invoice(colunas)
    for campo, regra in REGRAS.items():
        valores = {col.chave: _valor_fora_do_pl_sem_numero(ctx, col, campo, regra, sem_numero) for col in colunas}
        if campo not in CAMPOS_SEMPRE_VISIVEIS and all(v is None for v in valores.values()):
            continue
        if campo in CAMPOS_DO_EXPORTADOR and triangulares:
            status = _status_com_triangulacao(ctx, campo, regra, colunas, valores, triangulares)
        else:
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


def _pls_sem_numero_de_invoice(colunas: list[Col]) -> list[Fonte]:
    """PLs que citam as invoices por outra numeração: não têm nº de invoice para conferir."""
    fontes = [f for col in colunas for f in col.fontes]
    invoices = [f for f in fontes if f.doc.tipo == "invoice"]
    return pls_em_outra_numeracao(invoices, [f for f in fontes if f.doc.tipo == "packing_list"])


def _valor_fora_do_pl_sem_numero(
    ctx: Contexto, col: Col, campo: NomeCampo, regra: Regra, sem_numero: list[Fonte]
) -> Valor | None:
    """Coluna com PL em outra numeração fica sem nº da invoice; nos demais casos, o valor da coluna."""
    if campo == "numero_invoice" and any(f in sem_numero for f in col.fontes):
        return None
    return _valor_coluna(ctx, col, campo, regra)


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
    if campo == "consignatario":
        restantes, aviso = separar_conhecimentos_da_capital(ctx, informados)
        if aviso:
            ctx.avisos.append(aviso)
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


def _status_com_triangulacao(
    ctx: Contexto, campo: NomeCampo, regra: Regra, colunas: list[Col], valores: dict[str, Valor | None],
    triangulares: list[Triangulacao],
) -> StatusCampo:
    """Conhecimento triangular fora da comparação geral; só confere com as invoices/PLs da mesma empresa."""
    chaves = {t.conhecimento.chave for t in triangulares}
    restantes = [col for col in colunas if col.chave not in chaves]
    status = [_status_campo(ctx, campo, regra, restantes, valores)] if _informados(restantes, valores) > 1 else []
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
    presentes = [v for f in t.proprias if (v := _valor_do_documento(ctx, f, campo, regra)) is not None]
    if conhecimento is None or not presentes:
        return None
    proprias = presentes[0] if len(presentes) == 1 else regra.juntar(presentes, campo, ctx, col)
    if regra.iguais(proprias.chave, conhecimento.chave):
        return "OK"
    mensagem = f"{ctx.prefixo}{ROTULOS[campo]}: {t.conhecimento.nome_curto} {conhecimento.exibicao} × "
    ctx.divergencias.append(
        Divergencia(categoria="comparacao", comparacao_id=ctx.comparacao_id, campo=campo,
                    mensagem=f"{mensagem}{col.nome_curto} {proprias.exibicao}")
    )
    return "DIVERGENTE"


def _informados(colunas: list[Col], valores: dict[str, Valor | None]) -> int:
    return sum(valores[col.chave] is not None for col in colunas)


def _status_mais_grave(status: list[StatusCampo]) -> StatusCampo:
    """DIVERGENTE vence INSUFICIENTE, que vence OK."""
    return next(s for s in ("DIVERGENTE", "INSUFICIENTE", "OK", "NAO_ENCONTRADO") if s in status)


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
