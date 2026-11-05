"""Páginas juntadas: o mesmo documento dividido em arquivos vira um só, com os itens de todos."""

from app.schemas import DocumentoExtraido
from app.services.comparacao.documentos.duplicatas import mesma_linha, totais
from app.services.comparacao.documentos.identificacao_do_documento import nome_doc
from app.services.comparacao.normalizacao.dinheiro import iguais_no_centavo
from app.services.comparacao.tipos import Fonte


def juntar_paginas(mesmas: list[Fonte]) -> tuple[list[Fonte], list[str]]:
    """Mesmo número em arquivos com itens que não se repetem e totais só em um: são páginas, viram um documento."""
    if len(mesmas) < 2 or not _sao_paginas(mesmas):
        return mesmas, []
    paginas = sorted(mesmas, key=lambda f: (f.arquivo.nome, f.ordem))
    base = next(f for f in paginas if _tem_totais(f))
    doc = _documento_juntado(base.doc, [f.doc for f in paginas])
    juntada = Fonte(base.arquivo, doc, base.ordem, escaneado=base.escaneado)
    nomes = ", ".join(f.arquivo.nome for f in paginas)
    aviso = (
        f"{nome_doc(juntada)} veio em {len(paginas)} arquivos ({nomes}): itens juntados, totais de {base.arquivo.nome}."
    )
    return [juntada], [aviso]


def _sao_paginas(fontes: list[Fonte]) -> bool:
    """Todos com itens, nenhuma linha repetida entre arquivos e totais em um só (ou totais que batem com a soma)."""
    if not all(f.doc.itens for f in fontes):
        return False
    pares = [(a, b) for i, a in enumerate(fontes) for b in fontes[i + 1:]]
    if any(mesma_linha(x, y, False) for a, b in pares for x in a.doc.itens for y in b.doc.itens):
        return False
    com_totais = [f for f in fontes if _tem_totais(f)]
    return len(com_totais) == 1 or bool(com_totais) and all(_total_e_a_soma(f, fontes) for f in com_totais)


def _tem_totais(f: Fonte) -> bool:
    return any(totais(f)) or f.doc.valor_total is not None


def _total_e_a_soma(f: Fonte, fontes: list[Fonte]) -> bool:
    valores = [i.valor_total for g in fontes for i in g.doc.itens]
    total = f.doc.valor_total
    return total is not None and None not in valores and iguais_no_centavo(round(sum(valores), 2), total.valor)


def _documento_juntado(base: DocumentoExtraido, paginas: list[DocumentoExtraido]) -> DocumentoExtraido:
    """O documento com os totais, com os itens de todas as páginas e os campos que só outra página traz."""
    vazios = {
        nome: valor
        for nome in DocumentoExtraido.model_fields
        if not getattr(base, nome) and (valor := next((v for d in paginas if (v := getattr(d, nome))), None))
    }
    return base.model_copy(update=vazios | {"itens": [i for d in paginas for i in d.itens]})
