"""Casa os itens de um documento com os do outro."""

from app.services.comparacao.itens.tipos import ColItens, ItemAgrupado, Linha
from app.services.comparacao.normalizacao import (
    SIMILARIDADE_MINIMA_CASAMENTO,
    descricoes_equivalentes,
    normalizar_codigo_item,
    normalizar_descricao,
    similaridade,
)


def _mesmo_codigo(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    return bool(a.codigo and b.codigo and normalizar_codigo_item(a.codigo) == normalizar_codigo_item(b.codigo))


def casar(
    linhas: list[list[ItemAgrupado]], itens: list[ItemAgrupado], generico_nao_casa: bool = False
) -> tuple[list[tuple[int, ItemAgrupado]], list[int], list[ItemAgrupado]]:
    """Casa `itens` com `linhas` (cada linha = itens já casados entre si): por código, pela descrição
    (≥ 0,80, melhor par primeiro) e, se sobrar exatamente 1 de cada lado, um com o outro.
    Com `generico_nao_casa` (conhecimento), item cuja descrição serve para mais de uma linha
    (ex.: "SYNTHETIC SHOES") não casa pela descrição.
    Devolve (casamentos (índice da linha, item), linhas que sobraram, itens que sobraram)."""
    casados: list[tuple[int, ItemAgrupado]] = []
    livres_l, livres_i = list(range(len(linhas))), list(itens)
    # 1) pelo código
    for item in itens:
        i = next((i for i in livres_l if any(_mesmo_codigo(item, x) for x in linhas[i])), None)
        if i is not None:
            casados.append((i, item))
            livres_l.remove(i)
            livres_i.remove(item)
    # 2) pela descrição
    candidatos = sorted(
        ((max(_semelhanca_descricao(item, x) for x in linhas[i]), -n, -i) for n, item in enumerate(livres_i) for i in livres_l),
        reverse=True,
    )
    usados_l, usados_i = set(), set()
    if generico_nao_casa:
        for n in range(len(livres_i)):
            if sum(1 for nota, m, _ in candidatos if -m == n and nota >= SIMILARIDADE_MINIMA_CASAMENTO) > 1:
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


def _semelhanca_descricao(a: ItemAgrupado, b: ItemAgrupado) -> float:
    if descricoes_equivalentes(a.descricao, b.descricao):
        return 1.0
    return similaridade(normalizar_descricao(a.descricao), normalizar_descricao(b.descricao))
