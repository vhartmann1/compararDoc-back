"""Duas versões do mesmo documento com valor total, preços ou nº de invoice citado diferentes: divergência."""

from app.schemas import Divergencia
from app.services.comparacao.identificacao_do_documento import e_proforma, nome_doc
from app.services.comparacao.mensagens import divergencia_interna
from app.services.comparacao.normalizacao.dinheiro import iguais_no_centavo, normalizar_moeda
from app.services.comparacao.normalizacao.numeros_de_documento import numero_da_invoice_para_conferir
from app.services.comparacao.regras_por_campo.ncm_invoice_po_portos import numeros_iguais
from app.services.comparacao.tipos import Fonte


def divergencias_entre_versoes(fontes: list[Fonte]) -> list[Divergencia]:
    valores = [d for f in fontes for dup in f.duplicatas if (d := _divergencia(f, dup))]
    return valores + [d for f in fontes if (d := _numeros_citados_diferentes(f))]


def _numeros_citados_diferentes(usada: Fonte) -> Divergencia | None:
    """Uma divergência por documento, com a versão usada e cada número diferente que outra versão cita."""
    if not _citados(usada):
        return None
    lados = [usada]
    for dup in sorted(usada.duplicatas, key=lambda f: f.ordem):
        if (citados := _citados(dup)) and not any(numeros_iguais(citados, _citados(x)) for x in lados):
            lados.append(dup)
    if len(lados) == 1:
        return None
    textos = [f"{f.arquivo.nome} {', '.join(f.doc.invoices_referenciadas)}" for f in lados]
    return divergencia_interna(usada, f"duas versões citam nº de invoice diferente — {' × '.join(textos)}",
                               " × ".join(textos))


def _citados(f: Fonte) -> frozenset[str]:
    return frozenset(n for t in f.doc.invoices_referenciadas if (n := numero_da_invoice_para_conferir(t)))


def avisos_entre_versoes(fontes: list[Fonte]) -> list[str]:
    """Versões cujos totais diferem só pelo frete (e seguro) declarado: uma traz o total FOB, a outra o CIF/CFR."""
    return [
        f"{nome_doc(f)}: {' × '.join(map(_valor, sorted((f, dup), key=lambda x: x.ordem)))}; "
        "a diferença é o frete/seguro declarado (uma versão traz o total FOB)."
        for f in fontes for dup in f.duplicatas if f.doc.tipo == "invoice" and _diferenca_e_frete(f, dup)
    ]


def _divergencia(usada: Fonte, outra: Fonte) -> Divergencia | None:
    if usada.doc.tipo != "invoice" or e_proforma(outra.doc) or not _valores_diferentes(usada, outra):
        return None
    lados = sorted((usada, outra), key=lambda f: f.ordem)
    return divergencia_interna(usada, f"duas versões com valores diferentes — {' × '.join(map(_valor, lados))}",
                               " × ".join(f"{f.arquivo.nome}: {_precos(f)}" for f in lados))


def _valores_diferentes(a: Fonte, b: Fonte) -> bool:
    if _diferenca_e_frete(a, b):
        return False
    ta, tb = a.doc.valor_total, b.doc.valor_total
    if ta and tb and not _mesma_moeda(ta.moeda, tb.moeda):
        return False  # outra moeda: os valores não se comparam
    if ta and tb and not iguais_no_centavo(ta.valor, tb.valor):
        return True
    pa, pb = _valores_das_linhas(a), _valores_das_linhas(b)
    return bool(pa and pb) and len(pa) == len(pb) and any(not iguais_no_centavo(x, y) for x, y in zip(pa, pb))


def _diferenca_e_frete(a: Fonte, b: Fonte) -> bool:
    """A diferença entre os totais é o frete, ou frete + seguro, declarado em alguma das versões."""
    ta, tb = a.doc.valor_total, b.doc.valor_total
    if not (ta and tb and _mesma_moeda(ta.moeda, tb.moeda)) or iguais_no_centavo(ta.valor, tb.valor):
        return False
    return any(iguais_no_centavo(abs(ta.valor - tb.valor), p) for f in (a, b) for p in _parcelas_de_frete(f))


def _parcelas_de_frete(f: Fonte) -> list[float]:
    frete, seguro = f.doc.valor_frete, f.doc.valor_seguro
    if frete is None:
        return []
    return [frete.valor] + ([frete.valor + seguro.valor] if seguro else [])


def _mesma_moeda(a: str | None, b: str | None) -> bool:
    return not a or not b or normalizar_moeda(a) == normalizar_moeda(b)


def _valores_das_linhas(f: Fonte) -> list[float] | None:
    """Valores das linhas em ordem crescente; None se falta algum ou se não somam o total (leitura duvidosa)."""
    valores = [i.valor_total for i in f.doc.itens]
    if not valores or None in valores:
        return None
    total = f.doc.valor_total
    return sorted(valores) if total is None or abs(sum(valores) - total.valor) <= 0.01 * len(valores) else None


def _valor(f: Fonte) -> str:
    total = f.doc.valor_total
    return " ".join(filter(None, (f.arquivo.nome, total.moeda, f"{total.valor:.2f}"))) if total else f.arquivo.nome


def _precos(f: Fonte) -> str:
    return ", ".join(f"{i.descricao} {i.valor_total:.2f}" for i in f.doc.itens if i.valor_total is not None)
