"""Casa os itens de um documento com os do outro."""

from collections.abc import Callable

from app.services.comparacao.campos.itens.medidas_do_item import mesmas_medidas
from app.services.comparacao.campos.itens.nome_do_modelo import mesmo_modelo
from app.services.comparacao.campos.itens.palavras_em_outra_ordem import palavras_em_outra_ordem
from app.services.comparacao.campos.itens.produto_e_modelo import mesma_linha_sem_codigo
from app.services.comparacao.campos.itens.tipos import ColItens, ItemAgrupado, Linha
from app.services.comparacao.normalizacao.item import (
    SIMILARIDADE_MINIMA_CASAMENTO,
    descricoes_equivalentes,
    normalizar_codigo_item,
    normalizar_descricao,
    normalizar_lote,
)
from app.services.comparacao.normalizacao.texto import similaridade


def _casar_unicos(
    linhas: list[list[ItemAgrupado]], livres_l: list[int], livres_i: list[ItemAgrupado],
    combina: Callable[[ItemAgrupado, ItemAgrupado], bool],
) -> list[tuple[int, ItemAgrupado]]:
    """Casa item e linha que combinam só um com o outro; tira os casados das listas de livres."""
    pares = []
    for item in list(livres_i):
        linhas_do_item = [i for i in livres_l if any(combina(item, x) for x in linhas[i])]
        if len(linhas_do_item) != 1:
            continue
        i = linhas_do_item[0]
        if sum(1 for outro in livres_i if any(combina(outro, x) for x in linhas[i])) == 1:
            pares.append((i, item))
            livres_l.remove(i)
            livres_i.remove(item)
    return pares


def _mesma_descricao(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    return normalizar_descricao(a.descricao) == normalizar_descricao(b.descricao)


def _mesmo_lote(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    return bool({normalizar_lote(l) for l in a.lotes} & {normalizar_lote(l) for l in b.lotes})


def _mesmo_codigo(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    return bool(a.codigo and b.codigo and normalizar_codigo_item(a.codigo) == normalizar_codigo_item(b.codigo))


def casar(
    linhas: list[list[ItemAgrupado]], itens: list[ItemAgrupado], generico_nao_casa: bool = False
) -> tuple[list[tuple[int, ItemAgrupado]], list[int], list[ItemAgrupado]]:
    """Casa por código, descrição idêntica, lote, medidas, descrição (≥ 0,80) e o último par."""
    casados: list[tuple[int, ItemAgrupado]] = []
    livres_l, livres_i = list(range(len(linhas))), list(itens)
    # 1) pelo código
    for item in itens:
        i = next((i for i in livres_l if any(_mesmo_codigo(item, x) for x in linhas[i])), None)
        if i is not None:
            casados.append((i, item))
            livres_l.remove(i)
            livres_i.remove(item)
    # 1b) descrição idêntica, depois lote, só sem concorrente nos dois lados: lote trocado continua erro de lote
    casados += _casar_unicos(linhas, livres_l, livres_i, _mesma_descricao)
    casados += _casar_unicos(linhas, livres_l, livres_i, _mesmo_lote)
    casados += _casar_unicos(linhas, livres_l, livres_i, lambda a, b: mesmas_medidas(a.descricao, b.descricao))
    # 1c) nome do modelo que começa o do outro (caixas × dúzias): primeiro com a variante, depois só o nome
    casados += _casar_unicos(linhas, livres_l, livres_i, lambda a, b: mesmo_modelo(a, b, com_variante=True))
    casados += _casar_unicos(linhas, livres_l, livres_i, mesmo_modelo)
    # 1d) linha sem código: mesmo produto antes do modelo, mesmo modelo e mesma quantidade
    casados += _casar_unicos(linhas, livres_l, livres_i, mesma_linha_sem_codigo)
    # 1e) mesmas palavras em outra ordem, mesma medida em polegadas e mesma quantidade
    casados += _casar_unicos(linhas, livres_l, livres_i, palavras_em_outra_ordem)
    # 2) pela descrição
    candidatos = sorted(
        ((max(_semelhanca_descricao(item, x) for x in linhas[i]), -n, -i) for n, item in enumerate(livres_i) for i in livres_l),
        reverse=True,
    )
    usados_l, usados_i = set(), set()
    if generico_nao_casa:
        for n in range(len(livres_i)):
            notas = [nota for nota, m, _ in candidatos if -m == n and nota >= SIMILARIDADE_MINIMA_CASAMENTO]
            if len(notas) > 1 and notas.count(IDENTICA) != 1:  # um par idêntico só: não é genérico
                usados_i.add(n)
    genericos = set(usados_i)
    for nota, n, i in candidatos:
        n, i = -n, -i
        if nota < SIMILARIDADE_MINIMA_CASAMENTO or i in usados_l or n in usados_i:
            continue
        casados.append((i, livres_i[n]))
        usados_l.add(i)
        usados_i.add(n)
    livres_l = [i for i in livres_l if i not in usados_l]
    sobras = [item for n, item in enumerate(livres_i) if n in genericos]
    livres_i = [item for n, item in enumerate(livres_i) if n not in usados_i]
    # 3) sobrou exatamente 1 de cada lado: é o mesmo item com dados diferentes
    if len(livres_l) == 1 and len(livres_i) == 1 and not sobras:
        casados.append((livres_l.pop(), livres_i.pop()))
    return casados, livres_l, livres_i + sobras


def casar_base(base: list[ColItens]) -> list[Linha]:
    """Linhas Invoice × Packing List (ou de uma coluna só), na ordem da primeira coluna."""
    primeira = base[0]
    linhas: list[Linha] = [{primeira.col.chave: item} for item in primeira.itens]
    if len(base) == 1:
        return linhas
    segunda = base[1]
    casados, _, sobras = casar([[item] for item in primeira.itens], segunda.itens)
    for i, item in casados:
        linhas[i][segunda.col.chave] = item
    return linhas + [{segunda.col.chave: item} for item in sobras]


IDENTICA = 2.0


def _semelhanca_descricao(a: ItemAgrupado, b: ItemAgrupado) -> float:
    """2 = idêntica; 1 = equivalente; senão a similaridade: o par exato vence o só parecido."""
    if normalizar_descricao(a.descricao) == normalizar_descricao(b.descricao):
        return IDENTICA
    if descricoes_equivalentes(a.descricao, b.descricao):
        return 1.0
    return similaridade(normalizar_descricao(a.descricao), normalizar_descricao(b.descricao))
