"""Regras de peso, volumes e quantidade."""

from app.schemas import Medida, NomeCampo
from app.services.comparacao.campos.regras_por_campo.regra import Grupos, Informados, texto_dos_grupos, texto_soma
from app.services.comparacao.constantes import ROTULOS, TOLERANCIA_PESO_KG
from app.services.comparacao.documentos.identificacao_do_documento import nome_doc
from app.services.comparacao.mensagens import Diferenca, confira
from app.services.comparacao.normalizacao.formatacao import formatar_contagem, formatar_kg
from app.services.comparacao.normalizacao.quantidades import embalagem, para_kg, unidade_quantidade
from app.services.comparacao.tipos import Col, Contexto, Fonte, Valor


def obter_peso(f: Fonte, campo: NomeCampo, ctx: Contexto) -> Valor | None:
    medida = _medida_do_peso(f, campo)
    if medida is None:
        return None
    kg = para_kg(medida)
    if kg is None:
        return None
    return Valor(kg, formatar_kg(kg), medida.texto_original, f.arquivo.id, medida.pagina)


def aviso_de_peso_sem_unidade(f: Fonte, campo: NomeCampo, ctx: Contexto) -> str | None:
    """Peso lido numa unidade que não se converte para kg: fica fora da comparação, com aviso."""
    medida = _medida_do_peso(f, campo)
    if medida is None or para_kg(medida) is not None:
        return None
    return (f"{ctx.prefixo}{ROTULOS[campo]} ({nome_doc(f)}) em unidade não reconhecida "
            f"(\"{medida.texto_original}\"); não comparado.")


def _medida_do_peso(f: Fonte, campo: NomeCampo) -> Medida | None:
    return f.doc.peso_liquido_total if campo == "peso_liquido" else f.doc.peso_bruto_total


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


def embalagens_incomparaveis(ctx: Contexto, grupos: Grupos) -> str | None:
    """Volumes em paletes × caixas: não é divergência, é para conferir à mão."""
    if not embalagens_distintas([valor for _, valor in grupos]):
        return None
    textos = " × ".join(f"{'/'.join(c.nome_curto for c in cols)} {valor.exibicao}" for cols, valor in grupos)
    return confira(f"{ctx.prefixo}Volumes em embalagens diferentes ({textos})", "manualmente")


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


def aviso_de_quantidade_sem_soma(valores: list[Valor], ctx: Contexto, col: Col) -> str | None:
    """Documentos da coluna em unidades que não se somam (peças + kg)."""
    if len({v.chave[0] for v in valores}) <= 1:
        return None
    return (f"{ctx.prefixo}Quantidade: não dá para somar \"{col.rotulo}\" — unidades diferentes "
            f"({', '.join(v.exibicao for v in valores)}).")


def quantidades_iguais(a: tuple[str, float], b: tuple[str, float]) -> bool:
    return a[0] == b[0] and abs(a[1] - b[1]) < 1e-6


def unidades_incomparaveis(ctx: Contexto, informados: Informados) -> str | None:
    """Quantidade em unidades que não se convertem (peças × kg): conferir à mão."""
    if len({v.chave[0] for _, v in informados}) <= 1:
        return None
    textos = " × ".join(f"{col.nome_curto} {v.exibicao}" for col, v in informados)
    return confira(f"{ctx.prefixo}Quantidade em unidades que não dá para comparar ({textos})", "manualmente")


def texto_da_quantidade(ordenados: Grupos, grupos: Grupos) -> Diferenca:
    """Os valores, com a nota de unidade trocada quando diferem 1000×."""
    nota = nota_fator_mil([(v.chave[1], v.exibicao, v.unidade) for _, v in grupos])
    return Diferenca(texto_dos_grupos(ordenados).detalhe + nota)


def nota_fator_mil(valores: list[tuple[float, str, str | None]]) -> str:
    """Totais que diferem exatamente 1000× indicam unidade trocada (toneladas × kg)."""
    totais = sorted({round(total, 6): (total, exibicao, unidade) for total, exibicao, unidade in valores}.values())
    if len(totais) != 2 or totais[0][0] <= 0 or abs(totais[1][0] / totais[0][0] - 1000) > 1e-6:
        return ""
    total, exibicao, unidade = totais[1]
    _, fator = unidade_quantidade(unidade or "")
    if fator == 1000:  # rotulado como tonelada; se o número for kg, vale 1000× menos
        return f" — provável unidade errada: {exibicao} equivale a {formatar_contagem(total / fator / 1000, 't')} se for kg"
    return " — provável unidade errada (os valores diferem exatamente 1.000 vezes)"
