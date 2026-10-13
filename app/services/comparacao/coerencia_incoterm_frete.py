"""Coerência: incoterm × frete do conhecimento e × portos."""

from app.schemas import Divergencia
from app.services.comparacao.colunas_da_comparacao import listar_pares
from app.services.comparacao.constantes import INCOTERMS_CD, INCOTERMS_EF
from app.services.comparacao.identificacao_do_documento import nome_doc, ref_documento
from app.services.comparacao.normalizacao import normalizar_incoterm, normalizar_porto
from app.services.comparacao.tipos import Fonte


def _frete_normalizado(texto: str) -> str | None:
    t = " ".join(texto.upper().replace(".", " ").split())
    if "PREPAID" in t or t in {"PP", "P P"}:
        return "PREPAID"
    if "COLLECT" in t or t in {"CC", "COLL", "C C"}:
        return "COLLECT"
    return None


def divergencias_de_coerencia(grupos: list[tuple[Fonte | None, Fonte | None]], conhecimentos: list[Fonte]) -> list[Divergencia]:
    divergencias: list[Divergencia] = []
    varios = len(grupos) > 1
    for comparacao_id, prefixo, inv, pl in listar_pares(grupos):
        fonte = next((f for f in (inv, pl) if f and f.doc.incoterm and normalizar_incoterm(f.doc.incoterm.codigo)), None)
        if fonte is None:
            continue
        id_conhecimento = "consolidado" if varios else comparacao_id
        for comp_id, mensagem in _coerencia_incoterm(fonte, [f for f in (inv, pl) if f], conhecimentos):
            divergencias.append(
                Divergencia(
                    categoria="coerencia",
                    comparacao_id=id_conhecimento if comp_id == "conhecimento" else comparacao_id,
                    campo="incoterm",
                    mensagem=(prefixo if comp_id == "par" else "") + mensagem,
                    documento=ref_documento(fonte),
                    evidencia=fonte.doc.incoterm.texto_original,
                    pagina=fonte.doc.incoterm.pagina,
                )
            )
    return divergencias


def _coerencia_incoterm(fonte: Fonte, par: list[Fonte], conhecimentos: list[Fonte]) -> list[tuple[str, str]]:
    """Lista de ('par' | 'conhecimento', mensagem)."""
    inc = fonte.doc.incoterm
    sigla = normalizar_incoterm(inc.codigo)
    local = normalizar_porto(inc.local) if inc.local else ""
    exibicao = f"{sigla} {local}".strip()
    nome = nome_doc(fonte)
    resultado: list[tuple[str, str]] = []

    if sigla in INCOTERMS_EF or sigla in INCOTERMS_CD:
        esperado = "COLLECT" if sigla in INCOTERMS_EF else "PREPAID"
        quem = "comprador" if sigla in INCOTERMS_EF else "vendedor"
        for c in conhecimentos:
            frete = _frete_normalizado(c.doc.frete.valor) if c.doc.frete else None
            if frete and frete != esperado:
                resultado.append((
                    "conhecimento",
                    f"{nome_doc(c)} com frete {frete}, mas o incoterm da {nome} é {sigla} "
                    f"(frete por conta do {quem}; esperado {esperado})",
                ))

    if local and sigla in INCOTERMS_EF:
        destinos = {
            normalizar_porto(f.doc.porto_destino.valor) for f in par + conhecimentos if f.doc.porto_destino
        }
        if local in destinos:
            resultado.append((
                "par",
                f"Incoterm {exibicao} ({nome}): {sigla} indica local de embarque/origem, mas {local} é o destino",
            ))
    if local and sigla in INCOTERMS_CD:
        for c in conhecimentos:
            destino = normalizar_porto(c.doc.porto_destino.valor) if c.doc.porto_destino else ""
            if destino and destino != local:
                resultado.append((
                    "conhecimento",
                    f"Incoterm {exibicao} ({nome}) × porto de descarga do {nome_doc(c)} {destino}",
                ))
    return resultado
