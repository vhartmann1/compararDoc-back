"""Inconsistências internas (do modelo + determinísticas)."""

import re

from app.schemas import Divergencia
from app.services.comparacao.cabecalho_e_assinatura import divergencias_do_cabecalho
from app.services.comparacao.encurtar_texto import encurtar
from app.services.comparacao.identificacao_do_documento import nome_doc, ref_documento
from app.services.comparacao.normalizacao import formatar_dinheiro, normalizar_moeda, normalizar_pais
from app.services.comparacao.tipos import Fonte


def divergencias_internas(f: Fonte) -> list[Divergencia]:
    nome = nome_doc(f)
    divergencias = [
        Divergencia(
            categoria="interna",
            comparacao_id=None,
            campo=None,
            mensagem=f"{nome}: {sem_leitura_entre_parenteses(i.descricao)}",
            documento=ref_documento(f),
            evidencia=i.evidencia,
            pagina=i.pagina,
        )
        for i in f.doc.inconsistencias_internas
    ]
    divergencias.extend(divergencias_do_cabecalho(f))
    if so_amostras(f):
        return divergencias  # invoice de amostras: o valor das linhas é só para a alfândega
    moeda = normalizar_moeda(f.doc.moeda.valor) if f.doc.moeda else None
    for item in f.doc.itens:
        if item.sem_valor_comercial and (item.valor_total or 0) > 0:
            identificacao = item.codigo or encurtar(item.descricao)
            valor = formatar_dinheiro(item.valor_total, moeda)
            divergencias.append(
                Divergencia(
                    categoria="interna",
                    comparacao_id=None,
                    campo=None,
                    mensagem=f"{nome}: item {identificacao} marcado como FOC (sem valor comercial), mas cobrado {valor}",
                    documento=ref_documento(f),
                    evidencia=f"{identificacao} — FOC — {valor}",
                    pagina=item.pagina,
                )
            )
    return divergencias


LIDO_COMO = re.compile(r"(?i)\s*\(lid[oa]s? como [^()]*\)")


def sem_leitura_entre_parenteses(texto: str) -> str:
    """'escrito 101,00.00 (lido como 10.100,00)' -> 'escrito 101,00.00': como o modelo leu não interessa ao usuário."""
    return LIDO_COMO.sub("", texto)


def so_amostras(f: Fonte) -> bool:
    """Todas as linhas sem valor comercial: o documento inteiro é de amostras, não há linha cobrada para contradizer."""
    return bool(f.doc.itens) and all(i.sem_valor_comercial for i in f.doc.itens)


def avisos_amostras(invoices: list[Fonte]) -> list[str]:
    return [
        f"{nome_doc(f)}: todos os itens sem valor comercial (amostras); os valores informados servem só para a alfândega."
        for f in invoices
        if so_amostras(f)
    ]


def avisos_pais_origem(invoices: list[Fonte]) -> list[str]:
    avisos = []
    for f in invoices:
        origem, exportador = f.doc.pais_origem, f.doc.exportador
        if origem and exportador and exportador.pais:
            if normalizar_pais(origem.valor) != normalizar_pais(exportador.pais):
                avisos.append(
                    f"{nome_doc(f)}: país de origem da mercadoria ({origem.valor}) diferente do país do "
                    f"exportador ({exportador.pais}) — confira se é esperado."
                )
    return avisos
