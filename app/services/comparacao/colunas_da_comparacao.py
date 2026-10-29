"""Montagem das comparações: quais documentos viram coluna em cada uma."""

from app.services.comparacao.identificacao_do_documento import nome_doc
from app.services.comparacao.tipos import Col, Fonte


def montar_comparacoes(
    grupos: list[tuple[Fonte | None, Fonte | None]], conhecimentos: list[Fonte]
) -> list[tuple[str, str, list[Col]]]:
    """Lista de (id, prefixo das mensagens, colunas)."""
    cols_conhecimento = colunas_conhecimento(conhecimentos)
    if len(grupos) <= 1:
        inv, pl = grupos[0] if grupos else (None, None)
        colunas = colunas_par(inv, pl) + cols_conhecimento
        return [("unica", "", colunas)] if colunas else []

    resultado: list[tuple[str, str, list[Col]]] = [
        (comparacao_id, prefixo, colunas_par(inv, pl)) for comparacao_id, prefixo, inv, pl in listar_pares(grupos)
    ]

    if conhecimentos:
        invoices = [inv for inv, _ in grupos if inv]
        pls = [pl for _, pl in grupos if pl]
        colunas = []
        if invoices:
            colunas.append(coluna_soma("soma_invoices", invoices, "Invoices", "das", "invoice", "invoices"))
        if pls:
            colunas.append(
                coluna_soma("soma_packing_lists", pls, "Packing Lists", "dos", "packing list", "packing lists")
            )
        resultado.append(("consolidado", "Consolidado — ", colunas + cols_conhecimento))
    return resultado


def listar_pares(grupos: list[tuple[Fonte | None, Fonte | None]]) -> list[tuple[str, str, Fonte | None, Fonte | None]]:
    """(id da comparação, prefixo das mensagens, invoice, packing list) de cada par."""
    if len(grupos) <= 1:
        return [("unica", "", inv, pl) for inv, pl in grupos]
    resultado = []
    for n, (inv, pl) in enumerate(grupos, start=1):
        resultado.append((f"par-{n}", f"{nome_doc(inv or pl)} — ", inv, pl))
    return resultado


def colunas_par(inv: Fonte | None, pl: Fonte | None) -> list[Col]:
    colunas = []
    if inv:
        colunas.append(Col("invoice", nome_doc(inv), "Invoice", [inv]))
    if pl:
        colunas.append(Col("packing_list", nome_doc(pl), "Packing List", [pl]))
    return colunas


def colunas_conhecimento(conhecimentos: list[Fonte]) -> list[Col]:
    colunas = []
    for i, f in enumerate(conhecimentos):
        chave = "conhecimento" if i == 0 else f"conhecimento_{i + 1}"
        curto = nome_doc(f) if len(conhecimentos) > 1 else (f.doc.subtipo or "Conhecimento")
        colunas.append(Col(chave, nome_doc(f), curto, [f]))
    return colunas


def coluna_soma(chave: str, fontes: list[Fonte], curto: str, artigo: str, singular: str, plural: str) -> Col:
    if len(fontes) == 1:
        return Col(chave, nome_doc(fontes[0]), curto, fontes, soma=True)
    return Col(chave, f"Soma {artigo} {len(fontes)} {plural}", curto, fontes, soma=True)
