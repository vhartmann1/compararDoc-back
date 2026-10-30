"""Uma linha de um documento que o outro detalha em várias (por tamanho, cor): quais linhas somar para comparar."""

from app.services.comparacao.itens.tipos import ItemAgrupado
from app.services.comparacao.normalizacao.item import normalizar_descricao, normalizar_referencia


def linhas_a_juntar(resumo: list[ItemAgrupado], detalhe: list[ItemAgrupado]) -> dict[str, str]:
    """{descrição normalizada da linha detalhada: descrição da linha geral}; só sem código, cada uma num grupo."""
    do_resumo = {normalizar_descricao(x.descricao) for x in resumo}
    descricoes_do_detalhe = {normalizar_descricao(y.descricao) for y in detalhe}
    referencias = [normalizar_referencia(x.referencia) for x in resumo if x.referencia]
    livres = [y for y in detalhe if not y.codigo and normalizar_descricao(y.descricao) not in do_resumo]
    juntar: dict[str, str] = {}
    # a linha geral mais específica escolhe primeiro: 'CASCO BRANCO' leva 'CASCO BRANCO S' antes de 'CASCO'
    for x in sorted(resumo, key=lambda x: len(normalizar_descricao(x.descricao).split()), reverse=True):
        geral = normalizar_descricao(x.descricao)
        if x.codigo or geral in descricoes_do_detalhe:
            continue  # tem código ou par exato: o casamento normal resolve
        disponiveis = [y for y in livres if normalizar_descricao(y.descricao) not in juntar]
        partes = [y for y in disponiveis if _comeca_com(normalizar_descricao(y.descricao), geral)]
        if len(partes) < 2 and x.referencia and referencias.count(normalizar_referencia(x.referencia)) == 1:
            partes = [y for y in disponiveis if _mesma_referencia(y, x)]
        if len(partes) >= 2:
            juntar.update({normalizar_descricao(y.descricao): x.descricao for y in partes})
    return juntar


def _mesma_referencia(y: ItemAgrupado, x: ItemAgrupado) -> bool:
    return bool(y.referencia) and normalizar_referencia(y.referencia) == normalizar_referencia(x.referencia)


def _comeca_com(descricao: str, geral: str) -> bool:
    """'TAMPA AZUL M' começa com 'TAMPA AZUL' (palavra a palavra, com 2 palavras ou mais)."""
    palavras, inicio = descricao.split(), geral.split()
    return len(inicio) >= 2 and len(palavras) > len(inicio) and palavras[: len(inicio)] == inicio
