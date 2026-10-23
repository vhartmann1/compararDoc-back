"""Duas versões do mesmo documento com valor total ou preços diferentes: divergência, não só aviso."""

from app.schemas import Divergencia
from app.services.comparacao.identificacao_do_documento import e_proforma, nome_doc, ref_documento
from app.services.comparacao.normalizacao import normalizar_moeda
from app.services.comparacao.tipos import Fonte

TOLERANCIA = 0.005 + 1e-9  # Excel sem arredondar × PDF impresso


def divergencias_entre_versoes(fontes: list[Fonte]) -> list[Divergencia]:
    return [d for f in fontes for dup in f.duplicatas if (d := _divergencia(f, dup))]


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
    return Divergencia(
        categoria="interna",
        comparacao_id=None,
        campo=None,
        mensagem=f"{nome_doc(usada)}: duas versões com valores diferentes — {' × '.join(map(_valor, lados))}",
        documento=ref_documento(usada),
        evidencia=" × ".join(f"{f.arquivo.nome}: {_precos(f)}" for f in lados),
    )


def _valores_diferentes(a: Fonte, b: Fonte) -> bool:
    if _diferenca_e_frete(a, b):
        return False
    ta, tb = a.doc.valor_total, b.doc.valor_total
    if ta and tb and not _mesma_moeda(ta.moeda, tb.moeda):
        return False  # outra moeda: os valores não se comparam
    if ta and tb and abs(ta.valor - tb.valor) > TOLERANCIA:
        return True
    pa, pb = _valores_das_linhas(a), _valores_das_linhas(b)
    return bool(pa and pb) and len(pa) == len(pb) and any(abs(x - y) > TOLERANCIA for x, y in zip(pa, pb))


def _diferenca_e_frete(a: Fonte, b: Fonte) -> bool:
    """A diferença entre os totais é o frete, ou frete + seguro, declarado em alguma das versões."""
    ta, tb = a.doc.valor_total, b.doc.valor_total
    if not (ta and tb and _mesma_moeda(ta.moeda, tb.moeda)) or abs(ta.valor - tb.valor) <= TOLERANCIA:
        return False
    return any(abs(abs(ta.valor - tb.valor) - p) <= TOLERANCIA for f in (a, b) for p in _parcelas_de_frete(f))


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
