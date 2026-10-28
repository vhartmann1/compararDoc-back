"""Invoice FOB/EXW (frete por conta do comprador) com frete ou seguro somados ao total: a operação pede para tirar."""

from itertools import combinations

from app.schemas import Divergencia
from app.services.comparacao.constantes import INCOTERMS_EF
from app.services.comparacao.identificacao_do_documento import nome_doc, ref_documento
from app.services.comparacao.normalizacao import formatar_dinheiro, normalizar_incoterm
from app.services.comparacao.tipos import Fonte


def divergencias_de_frete_no_total(invoices: list[Fonte]) -> list[Divergencia]:
    return [d for f in invoices if (d := _frete_no_total(f))]


def _frete_no_total(f: Fonte) -> Divergencia | None:
    sigla = normalizar_incoterm(f.doc.incoterm.codigo) if f.doc.incoterm else None
    total, mercadoria = f.doc.valor_total, _soma_das_linhas(f)
    if sigla not in INCOTERMS_EF or total is None or mercadoria is None:
        return None
    somados = _parcelas_que_fecham(f, total.valor - mercadoria)
    if not somados:
        return None
    moeda = total.moeda
    parcelas = " + ".join(f"{nome} {formatar_dinheiro(v, moeda)}" for nome, v in somados)
    conta = f"{formatar_dinheiro(total.valor, moeda)} = mercadoria {formatar_dinheiro(mercadoria, moeda)} + {parcelas}"
    return Divergencia(
        categoria="coerencia", comparacao_id=None, campo="incoterm", documento=ref_documento(f),
        mensagem=f"{nome_doc(f)}: invoice {sigla} com frete/seguro somados ao total ({conta}); pedir para remover",
        evidencia=total.texto_original, pagina=total.pagina,
    )


def _soma_das_linhas(f: Fonte) -> float | None:
    valores = [i.valor_total for i in f.doc.itens]
    return sum(valores) if valores and None not in valores else None


def _parcelas_que_fecham(f: Fonte, diferenca: float) -> list[tuple[str, float]]:
    """Frete e/ou seguro informados cuja soma é exatamente o que o total tem a mais que as linhas."""
    parcelas = [(nome, v.valor) for nome, v in (("frete", f.doc.valor_frete), ("seguro", f.doc.valor_seguro))
                if v is not None and v.valor > 0]
    for n in range(len(parcelas), 0, -1):
        for grupo in combinations(parcelas, n):
            if abs(sum(v for _, v in grupo) - diferenca) < 0.005:
                return list(grupo)
    return []
