"""PL no arquivo de uma versão ignorada da invoice: é da mesma versão e sai junto, se houver outro PL dela."""

from dataclasses import dataclass

from app.services.comparacao.documentos.identificacao_do_documento import nome_curto_do_arquivo, numero_normalizado
from app.services.comparacao.documentos.preferencia_entre_versoes import preferencia
from app.services.comparacao.tipos import Fonte


@dataclass
class PlsSemVersaoIgnorada:
    ficam: list[Fonte]
    avisos: list[str]


def sem_pls_das_versoes_ignoradas(invoices: list[Fonte], pls: list[Fonte]) -> PlsSemVersaoIgnorada:
    ficam, avisos = list(pls), []
    for invoice in invoices:
        for pl, usado in _pls_que_saem(invoice, ficam):
            ficam.remove(pl)
            usado.duplicatas.extend([pl, *pl.duplicatas])
            avisos.append(f"Packing List de {nome_curto_do_arquivo(pl.arquivo.nome)} é da versão ignorada da invoice "
                          f"{invoice.doc.numero}; usado o de {nome_curto_do_arquivo(usado.arquivo.nome)}.")
    return PlsSemVersaoIgnorada(ficam, avisos)


def _pls_que_saem(invoice: Fonte, pls: list[Fonte]) -> list[tuple[Fonte, Fonte]]:
    """Cada PL da invoice no arquivo de uma versão ignorada, com o PL de fora dessas versões que fica no lugar."""
    numero = numero_normalizado(invoice.doc.numero)
    ignorados = {d.arquivo.id for d in invoice.duplicatas} - {invoice.arquivo.id}
    da_invoice = [pl for pl in pls if numero and numero in _citadas(pl)]
    validos = [pl for pl in da_invoice if pl.arquivo.id not in ignorados]
    if not validos:
        return []
    usado = max(validos, key=lambda pl: (pl.arquivo.id == invoice.arquivo.id, preferencia(pl)))
    return [(pl, usado) for pl in da_invoice if pl.arquivo.id in ignorados]


def _citadas(pl: Fonte) -> set[str]:
    return {numero_normalizado(n) for n in pl.doc.invoices_referenciadas}
