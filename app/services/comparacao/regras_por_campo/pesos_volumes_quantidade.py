"""Regras de peso, volumes e quantidade."""

from app.schemas import NomeCampo
from app.services.comparacao.constantes import ROTULOS, TOLERANCIA_PESO_KG
from app.services.comparacao.identificacao_do_documento import nome_doc
from app.services.comparacao.normalizacao import embalagem, formatar_contagem, formatar_kg, para_kg, unidade_quantidade
from app.services.comparacao.regras_por_campo.regra import texto_soma
from app.services.comparacao.tipos import Col, Contexto, Fonte, Valor


def obter_peso(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    medida = f.doc.peso_liquido_total if campo == "peso_liquido" else f.doc.peso_bruto_total
    if medida is None:
        return None
    kg = para_kg(medida)
    if kg is None:
        ctx.avisos.append(
            f"{ctx.prefixo}{ROTULOS[campo]} ({nome_doc(f)}) em unidade não reconhecida "
            f"(\"{medida.texto_original}\"); não comparado."
        )
        return None
    return Valor(kg, formatar_kg(kg), medida.texto_original, f.arquivo.id, medida.pagina)


def somar_peso(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    total = round(sum(v.chave for v in valores), 3)
    return Valor(total, formatar_kg(total), texto_soma(valores), None, None)


def pesos_iguais(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCIA_PESO_KG + 1e-9


def obter_volumes(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    c = f.doc.volumes_total
    if c is None:
        return None
    unidade = c.unidade.strip().upper()
    return Valor(c.valor, formatar_contagem(c.valor, unidade), c.texto_original, f.arquivo.id, c.pagina, unidade)


def embalagens_distintas(valores: list[Valor]) -> bool:
    """Cada valor numa embalagem conhecida e diferente das outras (paletes × caixas): os números não se comparam."""
    embalagens = [embalagem(v.unidade or "") for v in valores]
    return None not in embalagens and len(set(embalagens)) == len(embalagens)


def somar_volumes(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor:
    total = sum(v.chave for v in valores)
    unidades = list(dict.fromkeys(v.unidade for v in valores if v.unidade))
    unidade = "/".join(unidades)
    return Valor(total, formatar_contagem(total, unidade), texto_soma(valores), None, None, unidade)


def obter_quantidade(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    c = f.doc.quantidade_total
    if c is None:
        return None
    canonica, fator = unidade_quantidade(c.unidade)
    unidade = c.unidade.strip().upper()
    chave = (canonica, round(c.valor * fator, 3))
    return Valor(chave, formatar_contagem(c.valor, unidade), c.texto_original, f.arquivo.id, c.pagina, unidade)


def somar_quantidade(valores: list[Valor], campo: NomeCampo, ctx: Contexto, col: Col) -> Valor | None:
    canonicas = {v.chave[0] for v in valores}
    if len(canonicas) > 1:
        ctx.avisos.append(
            f"{ctx.prefixo}Quantidade: não dá para somar \"{col.rotulo}\" — unidades diferentes "
            f"({', '.join(v.exibicao for v in valores)})."
        )
        return None
    canonica = canonicas.pop()
    total = round(sum(v.chave[1] for v in valores), 3)
    unidades = {v.unidade for v in valores}
    if len(unidades) == 1:  # mesma unidade do documento: soma na unidade original
        unidade = unidades.pop()
        _, fator = unidade_quantidade(unidade)
        exibicao = formatar_contagem(round(total / fator, 3), unidade)
    else:
        unidade, exibicao = canonica, formatar_contagem(total, canonica)
    return Valor((canonica, total), exibicao, texto_soma(valores), None, None, unidade)


def quantidades_iguais(a: tuple[str, float], b: tuple[str, float]) -> bool:
    return a[0] == b[0] and abs(a[1] - b[1]) < 1e-6


def nota_fator_mil(valores: list[tuple[float, str, str | None]]) -> str:
    """Valores (total na unidade canônica, exibição, unidade do documento) que diferem por exatamente
    1000× indicam unidade trocada — ex.: PL "24.000 TONS" (960 × 25 kg) × Invoice "24 TO"."""
    totais = sorted({round(total, 6): (total, exibicao, unidade) for total, exibicao, unidade in valores}.values())
    if len(totais) != 2 or totais[0][0] <= 0 or abs(totais[1][0] / totais[0][0] - 1000) > 1e-6:
        return ""
    total, exibicao, unidade = totais[1]
    _, fator = unidade_quantidade(unidade or "")
    if fator == 1000:  # rotulado como tonelada; se o número for kg, vale 1000× menos
        return f" — provável unidade errada: {exibicao} equivale a {formatar_contagem(total / fator / 1000, 't')} se for kg"
    return " — provável unidade errada (os valores diferem exatamente 1.000 vezes)"
