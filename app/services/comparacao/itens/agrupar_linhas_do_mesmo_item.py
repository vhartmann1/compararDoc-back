"""Junta as linhas do mesmo item em cada coluna: mesmo código ou, sem código, mesma descrição."""

from app.schemas import ItemExtraido
from app.services.comparacao.itens.tipos import ItemAgrupado
from app.services.comparacao.normalizacao import (
    formatar_contagem,
    normalizar_codigo_item,
    normalizar_descricao,
    unidade_quantidade,
)
from app.services.comparacao.tipos import Fonte


def agrupar_itens(fontes: list[Fonte], por_descricao: bool = False) -> list[ItemAgrupado]:
    """Agrupa as linhas de todos os documentos da coluna (vários, quando é uma soma); `por_descricao` junta códigos que dividem a mesma descrição."""
    grupos: dict[str, list[tuple[ItemExtraido, str]]] = {}
    linhas = [(item, f.arquivo.id) for f in fontes for item in f.doc.itens]
    repetidas = _descricoes_com_varios_codigos(linhas) if por_descricao else set()
    for i, (item, arquivo_id) in enumerate(linhas):
        descricao = normalizar_descricao(item.descricao)
        codigo = normalizar_codigo_item(item.codigo) if item.codigo and descricao not in repetidas else ""
        grupos.setdefault(codigo or (f"#descricao-{descricao}" if descricao else f"#linha-{i}"), []).append(
            (item, arquivo_id)
        )
    return [_juntar_linhas([l for l, _ in g], g[0][1]) for g in grupos.values()]


def _descricoes_com_varios_codigos(linhas: list[tuple[ItemExtraido, str]]) -> set[str]:
    codigos: dict[str, set[str]] = {}
    for item, _ in linhas:
        if item.codigo:
            codigos.setdefault(normalizar_descricao(item.descricao), set()).add(normalizar_codigo_item(item.codigo))
    return {descricao for descricao, cods in codigos.items() if len(cods) > 1}


def _juntar_linhas(linhas: list[ItemExtraido], arquivo_id: str) -> ItemAgrupado:
    quantidade, exibicao = _somar_quantidades_itens(linhas)
    unidades = {(l.unidade or "").strip().upper() for l in linhas}
    return ItemAgrupado(
        codigo=" / ".join(dict.fromkeys(l.codigo.strip() for l in linhas if l.codigo and l.codigo.strip())) or None,
        descricao=linhas[0].descricao.strip(),
        referencia=next((l.referencia.strip() for l in linhas if l.referencia and l.referencia.strip()), None),
        quantidade=quantidade,
        quantidade_exibicao=exibicao,
        unidade=unidades.pop() if len(unidades) == 1 else None,
        lotes=list(dict.fromkeys(lote.strip() for l in linhas for lote in l.lotes if lote.strip())),
        validades=list(dict.fromkeys(v.strip() for l in linhas for v in l.validades if v.strip())),
        arquivo_id=arquivo_id,
        pagina=linhas[0].pagina,
    )


def _somar_quantidades_itens(linhas: list[ItemExtraido]) -> tuple[tuple[str, float] | None, str | None]:
    if any(l.quantidade is None for l in linhas):
        return None, None
    convertidas = [(*unidade_quantidade(l.unidade or ""), l) for l in linhas]
    canonicas = {canonica for canonica, _, _ in convertidas}
    if len(canonicas) > 1:
        return None, " + ".join(formatar_contagem(l.quantidade, (l.unidade or "").upper()) for l in linhas)
    canonica = canonicas.pop()
    total = round(sum(l.quantidade * fator for _, fator, l in convertidas), 6)
    unidades = {(l.unidade or "").strip().upper() for l in linhas}
    if len(unidades) == 1:  # mesma unidade do documento: exibe na unidade original
        exibicao = formatar_contagem(sum(l.quantidade for l in linhas), unidades.pop())
    else:
        exibicao = formatar_contagem(total, canonica)
    return (canonica, total), exibicao
