"""Status de um campo entre as colunas: OK, divergente, insuficiente ou não encontrado, com a mensagem."""

from dataclasses import replace

from app.schemas import Divergencia, NomeCampo, StatusCampo
from app.services.comparacao.campos.conhecimento_com_parte import conhecimentos_contidos
from app.services.comparacao.campos.leitura_incerta_entre_documentos import aviso_de_leitura_incerta
from app.services.comparacao.campos.regras_por_campo.exportador_consignatario import fabricantes_iguais
from app.services.comparacao.campos.regras_por_campo.regra import Grupos, Iguais, Informados, Regra
from app.services.comparacao.constantes import CAMPOS_SEM_AVISO_INSUFICIENTE, ROTULOS
from app.services.comparacao.mensagens import maiuscula, sujeito
from app.services.comparacao.tipos import Col, Contexto, Valor


def status_do_campo(
    ctx: Contexto, campo: NomeCampo, regra: Regra, colunas: list[Col], valores: dict[str, Valor | None]
) -> StatusCampo:
    if campo in ctx.divergentes_na_soma:
        return "DIVERGENTE"  # mensagem já registrada ao montar a soma
    informados = [(col, valores[col.chave]) for col in colunas if valores[col.chave] is not None]
    if not informados:
        return "NAO_ENCONTRADO"
    restantes, aviso = _separar_aceitos(ctx, regra, informados)
    if aviso:
        ctx.avisos.append(aviso)
    if len(restantes) < len(informados) and len(restantes) <= 1:
        return "OK"
    if len(restantes) == 1:
        if len(colunas) > 1 and campo not in CAMPOS_SEM_AVISO_INSUFICIENTE:
            ctx.avisos.append(
                f"{ctx.prefixo}{ROTULOS[campo]} informado só em {restantes[0][0].nome_curto}; "
                "nada com o que comparar."
            )
        return "INSUFICIENTE"
    return _comparar_informados(ctx, campo, regra, restantes)


def _comparar_informados(ctx: Contexto, campo: NomeCampo, regra: Regra, informados: Informados) -> StatusCampo:
    """Dois ou mais valores: agrupa os iguais e, se sobra mais de um grupo, registra a divergência."""
    if regra.incomparavel and (aviso := regra.incomparavel(ctx, informados)):
        ctx.avisos.append(aviso)
        return "INSUFICIENTE"
    comparador = regra.comparador_para(ctx, [v for _, v in informados])
    grupos = _agrupar_iguais(ctx, campo, regra, comparador.iguais, informados)
    if len(grupos) == 1:
        if aviso := _aviso_de_comerciais_diferentes(ctx, campo, regra, informados):
            ctx.avisos.append(aviso)
        return "OK"
    if aviso := _aviso_sem_divergencia(ctx, campo, regra, grupos):
        ctx.avisos.append(aviso)
        return "INSUFICIENTE"
    ordenados = sorted(grupos, key=lambda g: len(g[0]))  # minoria primeiro
    ctx.divergencias.append(
        Divergencia(
            categoria="comparacao",
            comparacao_id=ctx.comparacao_id,
            campo=campo,
            mensagem=f"{ctx.prefixo}{ROTULOS[campo]}: {comparador.texto(ordenados, grupos)}",
        )
    )
    return "DIVERGENTE"


def _aviso_sem_divergencia(ctx: Contexto, campo: NomeCampo, regra: Regra, grupos: Grupos) -> str | None:
    """Grupos que não se comparam (embalagens, leitura incerta): aviso em vez de divergência."""
    if regra.incomparavel_nos_grupos and (aviso := regra.incomparavel_nos_grupos(ctx, grupos)):
        return aviso
    return aviso_de_leitura_incerta(ctx, campo, grupos)


def _separar_aceitos(ctx: Contexto, regra: Regra, informados: Informados) -> tuple[Informados, str | None]:
    """Conhecimentos que conferem por regra própria saem da comparação geral, com o aviso que a regra dá."""
    if regra.separar_aceitos:
        return regra.separar_aceitos(ctx, informados)
    contidos = conhecimentos_contidos(regra, informados)
    return [(col, v) for col, v in informados if col.chave not in contidos], None


def _agrupar_iguais(ctx: Contexto, campo: NomeCampo, regra: Regra, iguais: Iguais, informados: Informados) -> Grupos:
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


def _na_ordem_de_conferir(regra: Regra, informados: Informados) -> Informados:
    """Com `conhecimento_e_referencia`, o conhecimento abre o grupo e os demais conferem com ele."""
    if not regra.conhecimento_e_referencia:
        return informados
    return sorted(informados, key=lambda cv: not cv[0].so_conhecimento())


def _aviso_de_comerciais_diferentes(
    ctx: Contexto, campo: NomeCampo, regra: Regra, informados: Informados
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


def _na_ordem_das_colunas(informados: Informados, grupos: Grupos) -> Grupos:
    """Grupos e colunas de cada grupo na ordem original das colunas (a mensagem não muda com a conferência)."""
    posicao = {col.chave: n for n, (col, _) in enumerate(informados)}
    ordenados = [(sorted(cols, key=lambda c: posicao[c.chave]), valor) for cols, valor in grupos]
    return sorted(ordenados, key=lambda g: posicao[g[0][0].chave])


def _mesmo_fabricante(regra: Regra, cols: list[Col]) -> bool:
    return regra.soma_alternativas and fabricantes_iguais([f for c in cols for f in c.fontes])


def _cabe_no_grupo(regra: Regra, iguais: Iguais, grupo: tuple[list[Col], Valor, list[Valor]], valor: Valor) -> bool:
    """Grupo do mesmo fabricante: basta a soma das alternativas; fabricantes diferentes: tem de bater com todos."""
    cols, referencia, membros = grupo
    if not regra.soma_alternativas or _mesmo_fabricante(regra, cols):
        return iguais(referencia.chave, valor.chave)
    return all(iguais(m.chave, valor.chave) for m in membros)
