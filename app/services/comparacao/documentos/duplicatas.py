"""Duplicatas: o mesmo documento enviado mais de uma vez (outro formato, outra versão, renumerado)."""

import re

from app.schemas import DocumentoExtraido, ItemExtraido
from app.services.comparacao.constantes import MEDIAS_DE_ESCRITORIO
from app.services.comparacao.documentos.identificacao_do_documento import numero_normalizado
from app.services.comparacao.normalizacao.dinheiro import iguais_no_centavo
from app.services.comparacao.normalizacao.item import descricoes_equivalentes, normalizar_codigo_item
from app.services.comparacao.normalizacao.quantidades import unidade_quantidade
from app.services.comparacao.normalizacao.texto import sem_acento
from app.services.comparacao.tipos import Fonte
from app.tipos_de_arquivo import MEDIA_PDF, MEDIA_XLS, MEDIA_XLSX

MEDIAS_DE_PLANILHA = (MEDIA_XLS, MEDIA_XLSX)


def grupos_de_duplicatas(fontes: list[Fonte], citados: set[str]) -> list[list[Fonte]]:
    """`citados`: números de invoice citados por PL/BL; um número citado nunca é tratado como versão descartável."""
    grupos: list[list[Fonte]] = []
    for f in fontes:
        grupo = next((g for g in grupos if any(_mesmo_documento(x, f, citados) for x in g)), None)
        if grupo:
            grupo.append(f)
        else:
            grupos.append([f])
    return grupos

def _mesmo_documento(a: Fonte, b: Fonte, citados: set[str]) -> bool:
    """Mesmo número (ou carga renumerada em outro formato); sem número, os mesmos totais ou a mesma invoice e itens."""
    if _detalhe_em_planilha(a, b) or _detalhe_em_planilha(b, a):
        return True
    na, nb = numero_normalizado(a.doc.numero), numero_normalizado(b.doc.numero)
    if na and nb:
        return na == nb or _mesma_carga_em_outro_formato(a, b, citados)
    ra = {numero_normalizado(n) for n in a.doc.invoices_referenciadas}
    rb = {numero_normalizado(n) for n in b.doc.invoices_referenciadas}
    if ra and rb and ra != rb:
        return False
    if ra and ra == rb and a.ordem[0] != b.ordem[0] and _mesmos_itens(a, b):
        return True  # rascunho em Word e versão final em PDF: os totais podem ter mudado
    return _mesmos_totais(a, b)


def _mesma_carga_em_outro_formato(a: Fonte, b: Fonte, citados: set[str]) -> bool:
    """Excel/Word × PDF com outro número, mesmos totais e itens, e o número do Excel/Word não citado: renumerado."""
    pdf, office = (a, b) if a.arquivo.media_type == MEDIA_PDF else (b, a)
    if pdf.arquivo.media_type != MEDIA_PDF or office.arquivo.media_type not in MEDIAS_DE_ESCRITORIO:
        return False
    if numero_normalizado(office.doc.numero) in citados:
        return False  # outro documento cita esse número: é outra invoice, não uma versão antiga
    return _mesmos_totais(a, b) and _mesmos_itens(a, b)


def _detalhe_em_planilha(planilha: Fonte, pdf: Fonte) -> bool:
    """PL em planilha com os pesos (e a quantidade, se houver) do PL em PDF e sem citar outra invoice: é o detalhe."""
    if planilha.doc.tipo != "packing_list" or pdf.doc.tipo != "packing_list":
        return False
    if planilha.arquivo.media_type not in MEDIAS_DE_PLANILHA or pdf.arquivo.media_type != MEDIA_PDF:
        return False
    return _mesmos_pesos_e_quantidade(planilha.doc, pdf.doc) and not _citam_outras_invoices(planilha.doc, pdf.doc)


def _mesmos_pesos_e_quantidade(x: DocumentoExtraido, y: DocumentoExtraido) -> bool:
    pesos = [(x.peso_liquido_total, y.peso_liquido_total), (x.peso_bruto_total, y.peso_bruto_total)]
    qa, qb = x.quantidade_total, y.quantidade_total
    return all(p and q and iguais_no_centavo(p.valor, q.valor) for p, q in pesos) and (
        not (qa and qb) or iguais_no_centavo(qa.valor, qb.valor)
    )


def _citam_outras_invoices(x: DocumentoExtraido, y: DocumentoExtraido) -> bool:
    """Os dois citam invoices e nenhuma em comum: são PLs de outras invoices, não detalhe um do outro."""
    rx = {numero_normalizado(n) for n in x.invoices_referenciadas}
    ry = {numero_normalizado(n) for n in y.invoices_referenciadas}
    return bool(rx and ry) and not rx & ry


def _mesmos_totais(a: Fonte, b: Fonte) -> bool:
    """Ao menos 2 totais iguais; se um deles é a quantidade e só há 2, também o mesmo número de linhas."""
    iguais = [iguais_no_centavo(x.valor, y.valor) for x, y in zip(totais(a), totais(b)) if x and y]
    qa, qb = _quantidade(a), _quantidade(b)
    if qa and qb:
        iguais.append(qa[0] == qb[0] and iguais_no_centavo(qa[1], qb[1]))
    if len(iguais) < 2 or not all(iguais):
        return False
    return len(iguais) > 2 or not (qa and qb) or _mesmo_numero_de_linhas(a, b)


def _quantidade(f: Fonte) -> tuple[str, float] | None:
    """Quantidade total na unidade canônica: 2 TON -> ('KG', 2000)."""
    q = f.doc.quantidade_total
    if q is None:
        return None
    canonica, fator = unidade_quantidade(q.unidade)
    return canonica, q.valor * fator


def _mesmo_numero_de_linhas(a: Fonte, b: Fonte) -> bool:
    return bool(a.doc.itens) and len(a.doc.itens) == len(b.doc.itens)


def _mesmos_itens(a: Fonte, b: Fonte) -> bool:
    """Cada linha de um tem par no outro: primeiro todos os pares exatos, depois as sobras por descrição equivalente."""
    sobra_a, sobra_b = list(a.doc.itens), list(b.doc.itens)
    for exata in (True, False):
        for x in list(sobra_a):
            par = next((y for y in sobra_b if mesma_linha(x, y, exata)), None)
            if par is not None:
                sobra_a.remove(x)
                sobra_b.remove(par)
    return bool(a.doc.itens) and not sobra_a and not sobra_b


def mesma_linha(x: ItemExtraido, y: ItemExtraido, exata: bool) -> bool:
    """Mesma quantidade e mesmo código; sem código, as mesmas palavras (em qualquer ordem) ou descrição parecida."""
    if (x.quantidade is None) != (y.quantidade is None):
        return False
    if x.quantidade is not None and not iguais_no_centavo(x.quantidade, y.quantidade):
        return False
    if x.codigo and y.codigo:
        return normalizar_codigo_item(x.codigo) == normalizar_codigo_item(y.codigo)
    if _palavras(x.descricao) == _palavras(y.descricao):
        return True
    return not exata and descricoes_equivalentes(x.descricao, y.descricao)


def _palavras(descricao: str) -> list[str]:
    return sorted(re.findall(r"[A-Z0-9]+", sem_acento(descricao).upper()))


def totais(f: Fonte) -> tuple:
    return f.doc.peso_bruto_total, f.doc.peso_liquido_total, f.doc.volumes_total
