"""Inconsistências internas (do modelo + determinísticas)."""

from app.schemas import Divergencia
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
            mensagem=f"{nome}: {i.descricao}",
            documento=ref_documento(f),
            evidencia=i.evidencia,
            pagina=i.pagina,
        )
        for i in f.doc.inconsistencias_internas
    ]
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
