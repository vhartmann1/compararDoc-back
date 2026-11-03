"""Comparação campo a campo e status de cada campo."""

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from app.schemas import CampoComparado, Coluna, Comparacao, Divergencia, NomeCampo, StatusCampo, ValorCampo
from app.services.comparacao.campos.chegada_por_dta import separar_chegada_por_dta
from app.services.comparacao.campos.conhecimento_com_parte import conhecimentos_contidos
from app.services.comparacao.campos.leitura_incerta_entre_documentos import aviso_de_leitura_incerta
from app.services.comparacao.campos.mensagem_de_ncm import texto_ncm
from app.services.comparacao.campos.regras_por_campo.exportador_consignatario import fabricantes_iguais
from app.services.comparacao.campos.regras_por_campo.pesos_volumes_quantidade import (
    embalagens_distintas,
    nota_fator_mil,
)
from app.services.comparacao.campos.regras_por_campo.regra import Regra
from app.services.comparacao.campos.regras_por_campo.regra_de_cada_campo import REGRAS
from app.services.comparacao.constantes import (
    CAMPOS_DIVERGENTES_NA_SOMA,
    CAMPOS_FORA_DO_CONHECIMENTO,
    CAMPOS_SEM_AVISO_INSUFICIENTE,
    CAMPOS_SEMPRE_VISIVEIS,
    CAMPOS_SOMADOS,
    CAMPOS_UNICOS_NA_SOMA,
    ROTULOS,
)
from app.services.comparacao.documentos.identificacao_do_documento import nome_doc, ref_documento
from app.services.comparacao.documentos.pareamento_invoice_packing_list import pls_em_outra_numeracao
from app.services.comparacao.mensagens import confira, maiuscula, sujeito
from app.services.comparacao.partes.capital_nos_documentos import texto_sem_a_capital
from app.services.comparacao.partes.conferencia_do_adquirente import campo_do_adquirente
from app.services.comparacao.partes.consignatario_pela_modalidade import separar_conhecimentos_da_capital
from app.services.comparacao.partes.endereco_do_consignatario import avisos_de_endereco
from app.services.comparacao.partes.operacao_triangular import (
    CAMPOS_DO_EXPORTADOR,
    Triangulacao,
    aviso_triangular,
    coluna_das_proprias,
    da_mesma_empresa,
    texto_contra_as_proprias,
    triangulacoes,
)
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
        if campo == "consignatario":
            ctx.avisos.extend(f"{ctx.prefixo}{m}" for m in avisos_de_endereco(colunas))
        campos.append(
            CampoComparado(
                campo=campo,
                rotulo=ROTULOS[campo],
                status=status,
                valores={chave: _para_valor_campo(v) for chave, v in valores.items()},
            )
        )
    if adquirente := campo_do_adquirente(ctx, colunas):
        campos.append(adquirente)
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
    if campo in CAMPOS_FORA_DO_CONHECIMENTO and col.so_conhecimento():
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
    restantes, aviso = _separar_aceitos(ctx, campo, regra, informados)
    if aviso:
        ctx.avisos.append(aviso)
    if len(restantes) < len(informados) and len(restantes) <= 1:
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
                confira(f"{ctx.prefixo}Quantidade em unidades que não dá para comparar ({textos})", "manualmente")
            )
            return "INSUFICIENTE"
    if campo == "ncm":
        digitos = _digitos_ncm(ctx, [v for _, v in informados])
        iguais = _iguais_nos_digitos(digitos)

    grupos = _agrupar_iguais(ctx, campo, regra, iguais, informados)
    if len(grupos) == 1:
        if aviso := _aviso_de_comerciais_diferentes(ctx, campo, regra, informados):
            ctx.avisos.append(aviso)
        return "OK"
    if campo == "volumes" and embalagens_distintas([valor for _, valor in grupos]):
        textos = " × ".join(f"{'/'.join(c.nome_curto for c in cols)} {valor.exibicao}" for cols, valor in grupos)
        ctx.avisos.append(confira(f"{ctx.prefixo}Volumes em embalagens diferentes ({textos})", "manualmente"))
        return "INSUFICIENTE"
    if aviso := aviso_de_leitura_incerta(ctx, campo, grupos):
        ctx.avisos.append(aviso)
        return "INSUFICIENTE"

    ordenados = sorted(grupos, key=lambda g: len(g[0]))  # minoria primeiro
    partes = [f"{'/'.join(c.nome_curto for c in cols)} {valor.exibicao}" for cols, valor in ordenados]
    nota = ""
    if campo == "quantidade":
        nota = nota_fator_mil([(v.chave[1], v.exibicao, v.unidade) for _, v in grupos])
    if campo == "ncm":
        partes, nota = [texto_ncm(ordenados, digitos)], ""
    if campo == "consignatario" and (texto := texto_sem_a_capital(ordenados)):
        partes, nota = [texto], ""
    ctx.divergencias.append(
        Divergencia(
            categoria="comparacao",
            comparacao_id=ctx.comparacao_id,
            campo=campo,
            mensagem=f"{ctx.prefixo}{ROTULOS[campo]}: {' × '.join(partes)}{nota}",
        )
    )
    return "DIVERGENTE"


def _separar_aceitos(
    ctx: Contexto, campo: NomeCampo, regra: Regra, informados: list[tuple[Col, Valor]]
) -> tuple[list[tuple[Col, Valor]], str | None]:
    """Conhecimentos que conferem por regra própria saem da comparação geral, com o aviso que a regra dá."""
    if campo == "consignatario":
        return separar_conhecimentos_da_capital(ctx, informados)
    if campo == "porto_destino":
        return separar_chegada_por_dta(ctx, informados)
    contidos = conhecimentos_contidos(regra, informados)
    return [(col, v) for col, v in informados if col.chave not in contidos], None


def _agrupar_iguais(
    ctx: Contexto, campo: NomeCampo, regra: Regra, iguais: Callable[[Any, Any], bool],
    informados: list[tuple[Col, Valor]],
) -> list[tuple[list[Col], Valor]]:
    """Grupos de colunas com o mesmo valor; com `soma_alternativas`, ver `_cabe_no_grupo`."""
    grupos: list[tuple[list[Col], Valor, list[Valor]]] = []
    for col, valor in _na_ordem_de_conferir(regra, informados):
        n = next((n for n, g in enumerate(grupos) if _cabe_no_grupo(regra, iguais, g, valor)), None)
        if n is None:
            grupos.append(([col], valor, [valor]))
            continue
        cols, referencia, membros = grupos[n]
        cols.append(col)
        membros.append(valor)
        if _mesmo_fabricante(regra, cols) and (soma := regra.juntar([referencia, valor], campo, ctx, col)):
            grupos[n] = (cols, replace(soma, exibicao=referencia.exibicao), membros)
    return _na_ordem_das_colunas(informados, [(cols, referencia) for cols, referencia, _ in grupos])


def _na_ordem_de_conferir(regra: Regra, informados: list[tuple[Col, Valor]]) -> list[tuple[Col, Valor]]:
    """Com `conhecimento_e_referencia`, o conhecimento abre o grupo e os demais conferem com ele."""
    if not regra.conhecimento_e_referencia:
        return informados
    return sorted(informados, key=lambda cv: not cv[0].so_conhecimento())


def _aviso_de_comerciais_diferentes(
    ctx: Contexto, campo: NomeCampo, regra: Regra, informados: list[tuple[Col, Valor]]
) -> str | None:
    """Invoice e PL com portos diferentes que o conhecimento aceita (descarga × entrega): confere, com aviso."""
    if not regra.conhecimento_e_referencia:
        return None
    conhecimentos = [(c, v) for c, v in informados if c.so_conhecimento()]
    outros = [(c, v) for c, v in informados if not c.so_conhecimento()]
    pares = [(a, b) for n, a in enumerate(outros) for b in outros[n + 1:]]
    diferentes = [(a, b) for a, b in pares if not regra.iguais(a[1].chave, b[1].chave)]
    if not conhecimentos or not diferentes:
        return None
    (ca, va), (cb, vb) = diferentes[0]
    cc, vc = conhecimentos[0]
    return (f"{ctx.prefixo}{ROTULOS[campo]}: {maiuscula(_quem_diz(ca))} {va.exibicao} e {_quem_diz(cb)} {vb.exibicao}; "
            f"os dois aparecem no {cc.nome_curto}: {vc.exibicao}.")


def _quem_diz(col: Col) -> str:
    quem, plural = sujeito([col.nome_curto])
    return f"{quem} {'dizem' if plural else 'diz'}"


def _na_ordem_das_colunas(
    informados: list[tuple[Col, Valor]], grupos: list[tuple[list[Col], Valor]]
) -> list[tuple[list[Col], Valor]]:
    """Grupos e colunas de cada grupo na ordem original das colunas (a mensagem não muda com a conferência)."""
    posicao = {col.chave: n for n, (col, _) in enumerate(informados)}
    ordenados = [(sorted(cols, key=lambda c: posicao[c.chave]), valor) for cols, valor in grupos]
    return sorted(ordenados, key=lambda g: posicao[g[0][0].chave])


def _mesmo_fabricante(regra: Regra, cols: list[Col]) -> bool:
    return regra.soma_alternativas and fabricantes_iguais([f for c in cols for f in c.fontes])


def _cabe_no_grupo(
    regra: Regra, iguais: Callable[[Any, Any], bool], grupo: tuple[list[Col], Valor, list[Valor]], valor: Valor
) -> bool:
    """Grupo do mesmo fabricante: basta a soma das alternativas; fabricantes diferentes: tem de bater com todos."""
    cols, referencia, membros = grupo
    if not regra.soma_alternativas or _mesmo_fabricante(regra, cols):
        return iguais(referencia.chave, valor.chave)
    return all(iguais(m.chave, valor.chave) for m in membros)


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
        v = _valor_do_documento(ctx, f, campo, regra)
        if v is not None and not any(regra.iguais(v.chave, o.chave) for o in [conhecimento, *(x for _, x in lados)]):
            lados.append((f, v))
    return lados


def _informados(colunas: list[Col], valores: dict[str, Valor | None]) -> int:
    return sum(valores[col.chave] is not None for col in colunas)


def _status_mais_grave(status: list[StatusCampo]) -> StatusCampo:
    """DIVERGENTE vence INSUFICIENTE, que vence OK."""
    return next(s for s in ("DIVERGENTE", "INSUFICIENTE", "OK", "NAO_ENCONTRADO") if s in status)


def _iguais_nos_digitos(digitos: int) -> Callable[[Any, Any], bool]:
    return lambda a, b: {c[:digitos] for c in a} == {c[:digitos] for c in b}


def _digitos_ncm(ctx: Contexto, valores: list[Valor]) -> int:
    """Compara com 8 dígitos; se algum documento só traz HS (6) ou posição (4), compara por aí."""
    menor = min(len(c) for v in valores for c in v.chave)
    digitos = 8 if menor >= 8 else 6 if menor >= 6 else 4
    if digitos < 8:
        ctx.avisos.append(
            f"{ctx.prefixo}NCM comparado pelos {digitos} primeiros dígitos "
            "(algum documento traz só o HS Code ou a posição)."
        )
    return digitos


def _para_valor_campo(v: Valor | None) -> ValorCampo | None:
    if v is None:
        return None
    return ValorCampo(exibicao=v.exibicao, texto_original=v.texto_original, arquivo_id=v.arquivo_id, pagina=v.pagina)
