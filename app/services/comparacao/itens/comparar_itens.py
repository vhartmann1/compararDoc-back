"""Comparação de itens (Invoice × Packing List, + Conhecimento na única/consolidado)."""

from app.schemas import Coluna, ComparacaoItens, Divergencia, LinhaItem, ValorItem
from app.services.comparacao.colunas_da_comparacao import coluna_soma, colunas_conhecimento, colunas_par, listar_pares
from app.services.comparacao.encurtar_texto import encurtar
from app.services.comparacao.identificacao_do_documento import ref_documento
from app.services.comparacao.itens.agrupar_linhas_do_mesmo_item import agrupar_itens
from app.services.comparacao.itens.casar_itens import casar, casar_base
from app.services.comparacao.itens.chave_da_linha import chaves_unicas
from app.services.comparacao.itens.diferencas_do_item import diferencas_item
from app.services.comparacao.itens.linhas_detalhadas import linhas_a_juntar
from app.services.comparacao.itens.nome_do_modelo import unidades_de_familias_diferentes
from app.services.comparacao.itens.tipos import ColItens, ItemAgrupado
from app.services.comparacao.normalizacao import normalizar_codigo_item, unidade_quantidade
from app.services.comparacao.tipos import Col, Fonte


def comparar_todos_os_itens(
    grupos: list[tuple[Fonte | None, Fonte | None]], conhecimentos: list[Fonte], avisos: list[str]
) -> tuple[list[ComparacaoItens], list[Divergencia]]:
    cols_conhecimento = [
        ColItens(c, agrupar_itens(c.fontes), conhecimento=True) for c in colunas_conhecimento(conhecimentos)
    ]
    cols_conhecimento = [c for c in cols_conhecimento if c.itens]
    resultado: list[ComparacaoItens] = []
    divergencias: list[Divergencia] = []

    def gerar(comparacao_id: str, prefixo: str, base: list[ColItens], extras: list[ColItens], so_conhecimento: bool):
        if len(base) == 2 or (base and extras):
            comparacao, divs = _comparar_itens(comparacao_id, prefixo, base, extras, avisos, so_conhecimento)
            resultado.append(comparacao)
            divergencias.extend(divs)

    for comparacao_id, prefixo, inv, pl in listar_pares(grupos):
        base = _agrupar_par(colunas_par(inv, pl))
        extras = cols_conhecimento if comparacao_id == "unica" else []
        gerar(comparacao_id, prefixo, [c for c in base if c.itens], extras, so_conhecimento=False)

    if len(grupos) > 1 and cols_conhecimento:
        invoices = [inv for inv, _ in grupos if inv]
        pls = [pl for _, pl in grupos if pl]
        somas = []
        if invoices:
            somas.append(coluna_soma("soma_invoices", invoices, "Invoices", "das", "invoice", "invoices"))
        if pls:
            somas.append(coluna_soma("soma_packing_lists", pls, "Packing Lists", "dos", "packing list", "packing lists"))
        base = [ColItens(c, agrupar_itens(c.fontes)) for c in somas]
        # invoice × PL já foram comparados em cada par: aqui só interessa o que envolve o conhecimento
        gerar("consolidado", "Consolidado — ", [c for c in base if c.itens], cols_conhecimento, so_conhecimento=True)
    return resultado, divergencias


def _agrupar_par(colunas: list[Col]) -> list[ColItens]:
    """Agrupa as linhas de cada documento; as opções de cada coluna vão todas na mesma chamada."""
    base = [ColItens(c, agrupar_itens(c.fontes)) for c in colunas]
    if len(base) != 2:
        return base
    opcoes: list[dict] = [{}, {}]
    sem_codigo = [all(not item.codigo for item in ci.itens) for ci in base]
    if any(sem_codigo) and not all(sem_codigo):
        # um documento sem código nenhum: o outro também é agrupado pela descrição, só assim os totais se casam
        opcoes = [{} if sem else {"por_descricao": True} for sem in sem_codigo]
    elif not any(sem_codigo):  # variantes de um lado ('7700100 010') contra o código base do outro ('7700100')
        codigos = [{normalizar_codigo_item(i.codigo) for i in ci.itens if i.codigo} for ci in base]
        separar = _unidades_sem_familia_comum(base)  # caixas × dúzias: o código pode ser só o nome do modelo
        opcoes = [{"codigos_base": codigos[1 - n], "separar_codigos": separar} for n in range(2)]
    base = [ColItens(ci.col, agrupar_itens(ci.col.fontes, **o)) if o else ci for ci, o in zip(base, opcoes)]
    # um documento resume em uma linha o que o outro detalha (por tamanho, cor)
    juntar = [linhas_a_juntar(base[1 - n].itens, ci.itens) for n, ci in enumerate(base)]
    return [
        ColItens(ci.col, agrupar_itens(ci.col.fontes, **o, juntar=j)) if j else ci
        for ci, o, j in zip(base, opcoes, juntar)
    ]


def _unidades_sem_familia_comum(base: list[ColItens]) -> bool:
    """Toda linha com unidade e nenhuma família de unidade em comum entre os dois documentos."""
    unidades = [[(l.unidade or "").strip() for f in ci.col.fontes for l in f.doc.itens] for ci in base]
    if not all(u and all(u) for u in unidades):
        return False
    familias = [{unidade_quantidade(u)[0] for u in us} for us in unidades]
    return not familias[0] & familias[1]


def _unidades_sem_conversao(base: list[ColItens], linhas: list) -> list[str]:
    """Aviso dos pares Invoice × PL com quantidade em unidades de famílias diferentes (caixas × dúzias)."""
    if len(base) != 2:
        return []
    pares = [(linha[base[0].col.chave], linha[base[1].col.chave]) for linha in linhas if len(linha) == 2]
    unidades = sorted({(a.unidade or "?", b.unidade or "?") for a, b in pares if unidades_de_familias_diferentes(a, b)})
    return [
        f"Itens: quantidade em unidades diferentes ({base[0].col.nome_curto} {a} × {base[1].col.nome_curto} {b}); "
        "não comparada."
        for a, b in unidades
    ]


def _valor_item(item: ItemAgrupado | None) -> ValorItem | None:
    if item is None:
        return None
    return ValorItem(
        descricao=item.descricao,
        quantidade=item.quantidade_exibicao,
        lotes=item.lotes,
        validades=item.validades,
        arquivo_id=item.arquivo_id,
        pagina=item.pagina,
    )


def _comparar_itens(
    comparacao_id: str,
    prefixo: str,
    base: list[ColItens],
    conhecimentos: list[ColItens],
    avisos: list[str],
    so_conhecimento: bool,
) -> tuple[ComparacaoItens, list[Divergencia]]:
    linhas = casar_base(base)
    avisos.extend(f"{prefixo}{texto}" for texto in _unidades_sem_conversao(base, linhas))
    for c in conhecimentos:
        casados, _, sobras = casar([list(l.values()) for l in linhas], c.itens, generico_nao_casa=True)
        for i, item in casados:
            linhas[i][c.col.chave] = item
        for item in sobras:  # BL costuma ter descrição genérica: não é divergência
            avisos.append(
                f"{prefixo}{c.col.nome_curto} descreve '{encurtar(item.descricao)}'; "
                "não foi possível relacionar aos itens."
            )

    colunas = base + conhecimentos
    linhas_item: list[LinhaItem] = []
    divergencias: list[Divergencia] = []
    bases = [[linha[c.col.chave] for c in base if c.col.chave in linha] for linha in linhas]
    chaves = chaves_unicas(
        [
            (next((x.codigo for x in [*itens_base, *linha.values()] if x.codigo), None), itens_base[0].descricao)
            for linha, itens_base in zip(linhas, bases)
        ]
    )
    for linha, itens_base, chave in zip(linhas, bases, chaves):
        primeiro = itens_base[0]
        difs = diferencas_item(linha, colunas, so_conhecimento)
        if len(base) == 2 and len(itens_base) == 1 and not so_conhecimento:
            difs.insert(0, ("ausente", "só na Invoice" if base[0].col.chave in linha else "só no Packing List"))
        linhas_item.append(
            LinhaItem(
                chave=chave,
                status="DIVERGENTE" if difs else "OK",
                diferencas=[nome for nome, _ in difs],
                valores={c.col.chave: _valor_item(linha.get(c.col.chave)) for c in colunas},
            )
        )
        if difs:
            divergencias.append(
                Divergencia(
                    categoria="item",
                    comparacao_id=comparacao_id,
                    campo=None,
                    mensagem=f"{prefixo}Item {chave}: {'; '.join(texto for _, texto in difs)}",
                    pagina=primeiro.pagina,
                    item_chave=chave,
                )
            )
    colunas_saida = [
        Coluna(chave=c.col.chave, rotulo=c.col.rotulo, documentos=[ref_documento(f) for f in c.col.fontes]) for c in colunas
    ]
    titulo = "Itens — " + " × ".join(c.col.rotulo for c in colunas)
    return (
        ComparacaoItens(comparacao_id=comparacao_id, titulo=titulo, colunas=colunas_saida, linhas=linhas_item),
        divergencias,
    )
