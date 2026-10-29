"""Contas internas da invoice e do packing list: soma das linhas × total e peso bruto × líquido."""

from dataclasses import dataclass
from math import fsum

from app.schemas import Contagem, Divergencia, ItemExtraido, Medida
from app.services.comparacao.encurtar_texto import encurtar
from app.services.comparacao.frete_somado_ao_total import parcelas_que_fecham
from app.services.comparacao.identificacao_do_documento import nome_doc, nome_doc_escaneado, ref_documento
from app.services.comparacao.normalizacao import (
    formatar_contagem,
    formatar_dinheiro,
    formatar_kg,
    para_kg,
    unidade_quantidade,
)
from app.services.comparacao.tipos import Fonte

TIPOS_COM_LINHAS = {"invoice", "packing_list"}
ARREDONDAMENTO_KG_POR_LINHA = 0.01


@dataclass
class ContaQueNaoFecha:
    erro: str  # "a soma das linhas (USD 10,00) não bate com o total (USD 10,02)"
    evidencia: str | None
    pagina: int | None


def divergencias_das_somas(f: Fonte) -> list[Divergencia]:
    """Documento digital: a conta errada é do documento e vira divergência interna."""
    if f.escaneado is not False:
        return []
    return [
        Divergencia(categoria="interna", comparacao_id=None, campo=None, documento=ref_documento(f),
                    mensagem=f"{nome_doc(f)}: {c.erro}; pedir correção.", evidencia=c.evidencia, pagina=c.pagina)
        for c in contas_que_nao_fecham(f)
    ]


def avisos_das_somas(fontes: list[Fonte]) -> list[str]:
    """Documento escaneado (ou sem saber): a conta pode ser erro de leitura, então é só aviso."""
    return [
        f"{nome_doc_escaneado(f)}: {c.erro}; conferir na imagem, pode ser leitura do scan."
        for f in fontes if f.escaneado is not False
        for c in contas_que_nao_fecham(f)
    ]


def contas_que_nao_fecham(f: Fonte) -> list[ContaQueNaoFecha]:
    if f.doc.tipo not in TIPOS_COM_LINHAS:
        return []
    contas = [_soma_dos_valores(f), _soma_das_quantidades(f), _soma_dos_volumes(f),
              _soma_dos_pesos(f, "peso_liquido", "pesos líquidos"), _soma_dos_pesos(f, "peso_bruto", "pesos brutos"),
              _bruto_menor_no_total(f)]
    return [c for c in contas if c] + [c for i in f.doc.itens if (c := _bruto_menor_na_linha(i))]


def _soma_dos_valores(f: Fonte) -> ContaQueNaoFecha | None:
    total, valores = f.doc.valor_total, [i.valor_total for i in f.doc.itens]
    if total is None or not valores or None in valores:
        return None
    soma = fsum(valores)
    if abs(soma - total.valor) < 0.005 or parcelas_que_fecham(f, abs(total.valor - soma)):
        return None  # fecha sozinha ou com o frete/seguro informados, no total ou nas linhas (CFR com total FOB)
    moeda = total.moeda or (f.doc.moeda.valor if f.doc.moeda else None)
    erro = (f"a soma das linhas ({formatar_dinheiro(soma, moeda)}) não bate com o total "
            f"({formatar_dinheiro(total.valor, moeda)})")
    return ContaQueNaoFecha(erro, total.texto_original, total.pagina)


def _soma_das_quantidades(f: Fonte) -> ContaQueNaoFecha | None:
    linhas = [(i.quantidade, i.unidade) for i in f.doc.itens]
    if any(q is None or u is None for q, u in linhas):
        return None
    return _soma_na_unidade_do_total(f.doc.quantidade_total, linhas, "das quantidades")


def _soma_dos_volumes(f: Fonte) -> ContaQueNaoFecha | None:
    volumes = [i.volumes for i in f.doc.itens]
    if None in volumes:
        return None
    return _soma_na_unidade_do_total(f.doc.volumes_total, [(v.valor, v.unidade) for v in volumes], "dos volumes")


def _soma_na_unidade_do_total(
    total: Contagem | None, linhas: list[tuple[float, str]], rotulo: str
) -> ContaQueNaoFecha | None:
    """Soma só as linhas na mesma unidade do total (convertendo, ex. TON em KG)."""
    if total is None or not linhas:
        return None
    unidade, fator_total = unidade_quantidade(total.unidade)
    convertidas = [(valor, *unidade_quantidade(u)) for valor, u in linhas]
    na_unidade = [valor * fator for valor, u, fator in convertidas if u == unidade]
    if not na_unidade:
        return None
    soma = fsum(na_unidade) / fator_total
    if abs(soma - total.valor) < 0.001:
        return None
    erro = (f"a soma {rotulo} das linhas ({formatar_contagem(soma, total.unidade)}) não bate com o total "
            f"({formatar_contagem(total.valor, total.unidade)})")
    return ContaQueNaoFecha(erro, total.texto_original, total.pagina)


def _soma_dos_pesos(f: Fonte, campo: str, rotulo: str) -> ContaQueNaoFecha | None:
    total: Medida | None = getattr(f.doc, f"{campo}_total")
    pesos = [_kg(getattr(i, campo)) for i in f.doc.itens]
    total_kg = _kg(total)
    if total_kg is None or not pesos or None in pesos:
        return None
    soma = fsum(pesos)
    if abs(soma - total_kg) <= ARREDONDAMENTO_KG_POR_LINHA * len(pesos) + 1e-9:
        return None
    erro = f"a soma dos {rotulo} das linhas ({formatar_kg(soma)}) não bate com o total ({formatar_kg(total_kg)})"
    return ContaQueNaoFecha(erro, total.texto_original, total.pagina)


def _bruto_menor_no_total(f: Fonte) -> ContaQueNaoFecha | None:
    liquido, bruto = f.doc.peso_liquido_total, f.doc.peso_bruto_total
    return _bruto_menor(liquido, bruto, "do total", bruto.pagina if bruto else None)


def _bruto_menor_na_linha(item: ItemExtraido) -> ContaQueNaoFecha | None:
    linha = f"da linha {item.codigo or encurtar(item.descricao)}"
    return _bruto_menor(item.peso_liquido, item.peso_bruto, linha, item.pagina)


def _bruto_menor(
    liquido: Medida | None, bruto: Medida | None, onde: str, pagina: int | None
) -> ContaQueNaoFecha | None:
    kg_liquido, kg_bruto = _kg(liquido), _kg(bruto)
    if kg_liquido is None or kg_bruto is None or kg_bruto >= kg_liquido:
        return None
    erro = f"o peso bruto {onde} ({formatar_kg(kg_bruto)}) é menor que o líquido ({formatar_kg(kg_liquido)})"
    return ContaQueNaoFecha(erro, f"{bruto.texto_original} × {liquido.texto_original}", pagina)


def _kg(medida: Medida | None) -> float | None:
    return para_kg(medida) if medida else None
