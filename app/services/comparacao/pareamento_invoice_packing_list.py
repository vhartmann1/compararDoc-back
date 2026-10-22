"""Pareamento: qual packing list pertence a qual invoice."""

from app.schemas import DocumentoExtraido
from app.services.comparacao.identificacao_do_documento import nome_doc, numero_normalizado
from app.services.comparacao.normalizacao import mesmo_numero, numero_sem_serie, numeros_quase_iguais, para_kg
from app.services.comparacao.regras_por_campo.pesos_volumes_quantidade import pesos_iguais
from app.services.comparacao.tipos import Fonte


def parear(
    invoices: list[Fonte], pls: list[Fonte], avisos: list[str]
) -> list[tuple[Fonte | None, Fonte | None]]:
    em_outra = pls_em_outra_numeracao(invoices, pls)  # não diz qual invoice: só entra na soma
    cobertas = {p: [i for i in invoices if _pl_da_invoice(p.doc, i.doc)] for p in pls}
    de_varias = [p for p in pls if len(cobertas[p]) > 1 or p in em_outra]  # um PL para várias invoices: só na soma
    na_soma = {i for p in de_varias for i in cobertas[p]} | (set(invoices) if em_outra else set())
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
    avisos.extend(_aviso_da_soma(pl, cobertas[pl], pl in em_outra) for pl in de_varias)

    for inv, pl in grupos:
        if inv and pl:
            pl.invoice_par = inv.doc
        elif inv and pls and inv not in na_soma:
            avisos.append(f"{nome_doc(inv)} sem packing list correspondente.")
        elif pl and invoices and pl not in de_varias:
            avisos.append(f"{nome_doc(pl)} sem invoice correspondente.")
    return grupos


def pls_em_outra_numeracao(invoices: list[Fonte], pls: list[Fonte]) -> list[Fonte]:
    """PLs que só citam números fora das invoices, um por invoice (2+), e pesam o mesmo que todas elas juntas."""
    nossos = [i.doc.numero for i in invoices if i.doc.numero]
    candidatos = [p for p in pls if p.doc.invoices_referenciadas and not _cita_alguma(p.doc, nossos)]
    estranhos = {numero_normalizado(n): n for p in candidatos for n in p.doc.invoices_referenciadas}
    if len(estranhos) < 2 or len(estranhos) != len(invoices) or _parece_digitacao(list(estranhos.values()), nossos):
        return []
    peso_pls, peso_invoices = _peso_bruto(candidatos), _peso_bruto(invoices)
    if peso_pls is None or peso_invoices is None or not pesos_iguais(peso_pls, peso_invoices):
        return []
    return candidatos


def _cita_alguma(pl: DocumentoExtraido, numeros: list[str]) -> bool:
    citados = [numero_normalizado(n) for n in pl.invoices_referenciadas]
    return any(mesmo_numero(numero_normalizado(x), c) for x in numeros for c in citados)


def _parece_digitacao(estranhos: list[str], nossos: list[str]) -> bool:
    """Algum número estranho é um dos nossos digitado errado, não outra numeração."""
    return any(numeros_quase_iguais(numero_sem_serie(n), numero_sem_serie(x)) for n in estranhos for x in nossos)


def _peso_bruto(fontes: list[Fonte]) -> float | None:
    """Soma do peso bruto total; None se algum documento não traz."""
    pesos = [para_kg(f.doc.peso_bruto_total) if f.doc.peso_bruto_total else None for f in fontes]
    return None if any(p is None for p in pesos) else sum(pesos)


def _aviso_da_soma(pl: Fonte, cobertas: list[Fonte], em_outra: bool) -> str:
    if em_outra:
        citados = ", ".join(pl.doc.invoices_referenciadas)
        return (f"{nome_doc(pl)} cita {citados}, outra numeração das invoices (um número para cada, mesmo peso "
                "da soma): Nº da invoice não conferido nele; comparado só na soma.")
    return f"{nome_doc(pl)} cobre as invoices {', '.join(i.doc.numero for i in cobertas)}: comparado só na soma."


def _pl_da_invoice(pl: DocumentoExtraido, inv: DocumentoExtraido) -> bool:
    numero = numero_normalizado(inv.numero)
    if not numero:
        return False
    citados = {numero_normalizado(n) for n in pl.invoices_referenciadas}
    if numero == numero_normalizado(pl.numero) or any(mesmo_numero(numero, c) for c in citados):
        return True
    return bool(pl.numero) and numero_sem_serie(inv.numero) == numero_sem_serie(pl.numero)
