"""Pareamento: qual packing list pertence a qual invoice."""

from app.schemas import DocumentoExtraido
from app.services.comparacao.identificacao_do_documento import nome_doc, numero_normalizado
from app.services.comparacao.normalizacao import mesmo_numero, numero_sem_serie
from app.services.comparacao.tipos import Fonte


def parear(
    invoices: list[Fonte], pls: list[Fonte], avisos: list[str]
) -> list[tuple[Fonte | None, Fonte | None]]:
    cobertas = {p: [i for i in invoices if _pl_da_invoice(p.doc, i.doc)] for p in pls}
    de_varias = [p for p in pls if len(cobertas[p]) > 1]  # um PL para várias invoices: só entra na soma
    na_soma = {i for p in de_varias for i in cobertas[p]}
    livres = [p for p in pls if p not in de_varias]
    grupos: list[tuple[Fonte | None, Fonte | None]] = []
    for inv in invoices:
        pl = next((p for p in livres if _pl_da_invoice(p.doc, inv.doc)), None)
        if pl:
            livres.remove(pl)
        grupos.append((inv, pl))

    sem_pl = [i for i, (inv, pl) in enumerate(grupos) if pl is None and inv not in na_soma]
    if len(sem_pl) == 1 and len(livres) == 1:
        i = sem_pl[0]
        inv, pl = grupos[i][0], livres.pop()
        grupos[i] = (inv, pl)
        avisos.append(
            f"{nome_doc(inv)} e {nome_doc(pl)} foram comparados juntos, mas o packing list "
            "não cita o número da invoice."
        )
    grupos.extend((None, pl) for pl in de_varias + livres)
    for pl in de_varias:
        numeros = ", ".join(i.doc.numero for i in cobertas[pl])
        avisos.append(f"{nome_doc(pl)} cobre as invoices {numeros}: comparado só na soma.")

    for inv, pl in grupos:
        if inv and pl:
            pl.invoice_par = inv.doc
        elif inv and pls and inv not in na_soma:
            avisos.append(f"{nome_doc(inv)} sem packing list correspondente.")
        elif pl and invoices and pl not in de_varias:
            avisos.append(f"{nome_doc(pl)} sem invoice correspondente.")
    return grupos


def _pl_da_invoice(pl: DocumentoExtraido, inv: DocumentoExtraido) -> bool:
    numero = numero_normalizado(inv.numero)
    if not numero:
        return False
    citados = {numero_normalizado(n) for n in pl.invoices_referenciadas}
    if numero == numero_normalizado(pl.numero) or any(mesmo_numero(numero, c) for c in citados):
        return True
    return bool(pl.numero) and numero_sem_serie(inv.numero) == numero_sem_serie(pl.numero)
