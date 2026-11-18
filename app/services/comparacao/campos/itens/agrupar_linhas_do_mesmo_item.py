"""Junta as linhas do mesmo item em cada coluna: mesmo código ou, sem código, mesma descrição."""

from dataclasses import replace

from app.schemas import ItemExtraido
from app.services.comparacao.campos.itens.tipos import ItemAgrupado
from app.services.comparacao.normalizacao.formatacao import formatar_contagem
from app.services.comparacao.normalizacao.item import normalizar_codigo_item, normalizar_descricao
from app.services.comparacao.normalizacao.quantidades import unidade_quantidade
from app.services.comparacao.tipos import Fonte


def agrupar_itens(
    fontes: list[Fonte], por_descricao: bool = False, codigos_base: set[str] | None = None,
    juntar: dict[str, str] | None = None, separar_codigos: bool = False,
) -> list[ItemAgrupado]:
    """Agrupa por código; ou descrição, código base, linha geral (`juntar`) e código que o outro não usa."""
    grupos: dict[str, list[tuple[ItemExtraido, str]]] = {}
    bases: dict[str, str] = {}
    gerais: dict[str, str] = {}
    linhas = [(item, f.arquivo.id) for f in fontes for item in f.doc.itens]
    repetidas = _descricoes_com_varios_codigos(linhas) if por_descricao else set()
    sem_par = _codigos_de_varios_itens(linhas, codigos_base or set()) if separar_codigos else set()
    for i, (item, arquivo_id) in enumerate(linhas):
        descricao = normalizar_descricao(item.descricao)
        codigo = normalizar_codigo_item(item.codigo) if item.codigo and descricao not in repetidas else ""
        codigo = "" if codigo in sem_par else codigo
        base = codigo_base(item.codigo, codigos_base) if codigo and codigos_base else None
        if base:
            codigo = normalizar_codigo_item(base)
            bases[codigo] = base
        geral = (juntar or {}).get(descricao) if not codigo else None
        if geral:
            chave = f"#geral-{normalizar_descricao(geral)}"
            gerais[chave] = geral
        else:
            chave = codigo or (f"#descricao-{descricao}" if descricao else f"#linha-{i}")
        grupos.setdefault(chave, []).append((item, arquivo_id))
    agrupados = []
    for chave, g in grupos.items():
        item = _juntar_linhas([l for l, _ in g], g[0][1])
        if chave in gerais:
            item = replace(item, descricao=gerais[chave])  # a soma das linhas detalhadas leva a descrição geral
        agrupados.append(replace(item, codigo=bases[chave]) if chave in bases else item)
    return agrupados


def codigo_base(codigo: str, codigos_do_outro: set[str]) -> str | None:
    """'7700100 010' -> '7700100' quando o outro documento usa só o código base; senão None."""
    partes = codigo.strip().split()
    if len(partes) < 2 or normalizar_codigo_item(codigo) in codigos_do_outro:
        return None
    return partes[0] if normalizar_codigo_item(partes[0]) in codigos_do_outro else None


def _descricoes_com_varios_codigos(linhas: list[tuple[ItemExtraido, str]]) -> set[str]:
    codigos: dict[str, set[str]] = {}
    for item, _ in linhas:
        if item.codigo:
            codigos.setdefault(normalizar_descricao(item.descricao), set()).add(normalizar_codigo_item(item.codigo))
    return {descricao for descricao, cods in codigos.items() if len(cods) > 1}


def _codigos_de_varios_itens(linhas: list[tuple[ItemExtraido, str]], codigos_do_outro: set[str]) -> set[str]:
    """Código que o outro documento não usa, em linhas de descrições diferentes: não junta, cada uma é um item."""
    descricoes: dict[str, set[str]] = {}
    for item, _ in linhas:
        if item.codigo:
            descricoes.setdefault(normalizar_codigo_item(item.codigo), set()).add(normalizar_descricao(item.descricao))
    return {codigo for codigo, d in descricoes.items() if len(d) > 1 and codigo not in codigos_do_outro}


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
        descricoes=_descricoes_das_linhas(linhas),
    )


def _descricoes_das_linhas(linhas: list[ItemExtraido]) -> tuple[str, ...]:
    """Linhas juntas pelo mesmo código guardam cada descrição: a segunda pode trazer outro modelo."""
    codigos = {normalizar_codigo_item(l.codigo) for l in linhas if l.codigo}
    if len(codigos) != 1 or not all(l.codigo for l in linhas):
        return ()
    return tuple(dict.fromkeys(l.descricao.strip() for l in linhas))


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
