"""Coerência: incoterm × frete do conhecimento e × portos."""

from app.schemas import Divergencia
from app.services.comparacao.constantes import INCOTERMS_CD, INCOTERMS_EF
from app.services.comparacao.documentos.colunas_da_comparacao import listar_pares
from app.services.comparacao.documentos.identificacao_do_documento import nome_doc, ref_documento
from app.services.comparacao.mensagens import Diferenca, divergencia
from app.services.comparacao.normalizacao.codigos import normalizar_incoterm
from app.services.comparacao.normalizacao.portos import nome_do_porto, normalizar_porto, so_o_pais
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
    for comparacao_id, origem, inv, pl in listar_pares(grupos):
        fonte = next((f for f in (inv, pl) if f and f.doc.incoterm and normalizar_incoterm(f.doc.incoterm.codigo)), None)
        if fonte is None:
            continue
        id_conhecimento = "consolidado" if varios else comparacao_id
        for comp_id, mensagem in _coerencia_incoterm(fonte, [f for f in (inv, pl) if f], conhecimentos):
            divergencias.append(divergencia(
                "coerencia", id_conhecimento if comp_id == "conhecimento" else comparacao_id, "incoterm",
                origem if comp_id == "par" else None, None, Diferenca(mensagem), documento=ref_documento(fonte),
                evidencia=fonte.doc.incoterm.texto_original, pagina=fonte.doc.incoterm.pagina,
            ))
    return divergencias


def _coerencia_incoterm(fonte: Fonte, par: list[Fonte], conhecimentos: list[Fonte]) -> list[tuple[str, str]]:
    """Lista de ('par' | 'conhecimento', mensagem)."""
    inc = fonte.doc.incoterm
    sigla = normalizar_incoterm(inc.codigo)
    local = normalizar_porto(inc.local) if inc.local else ""
    local_exibido = nome_do_porto(inc.local) if inc.local else ""
    exibicao = f"{sigla} {local_exibido}".strip()
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

    destinos = {normalizar_porto(f.doc.porto_destino.valor) for f in par + conhecimentos if f.doc.porto_destino}
    if local and sigla in INCOTERMS_EF:
        if local in destinos:
            resultado.append((
                "par",
                f"Incoterm {exibicao} ({nome}): {sigla} indica local de embarque/origem, mas {local_exibido} é o destino",
            ))
    # "FOB INDONESIA" nomeia país, não porto: não dá para conferir
    if local and sigla in INCOTERMS_PORTO_DE_EMBARQUE and not so_o_pais(inc.local):
        origens = {f.doc.porto_origem.valor for f in par + conhecimentos if f.doc.porto_origem}
        origens |= {c.doc.local_recebimento.valor for c in conhecimentos if c.doc.local_recebimento}
        if origens and local not in {normalizar_porto(o) for o in origens} and local not in destinos:
            resultado.append((
                "par",
                f"Incoterm {exibicao} ({nome}) × porto de embarque {' / '.join(sorted(nome_do_porto(o) for o in origens))}",
            ))
    if local and sigla in INCOTERMS_CD:
        for c in conhecimentos:
            destino = c.doc.porto_destino.valor if c.doc.porto_destino else ""
            entrega = c.doc.local_entrega.valor if c.doc.local_entrega else ""
            if destino and local not in {normalizar_porto(destino), normalizar_porto(entrega) if entrega else ""}:
                resultado.append((
                    "conhecimento",
                    f"Incoterm {exibicao} ({nome}) × porto de descarga do {nome_doc(c)} {nome_do_porto(destino)}",
                ))
    return resultado


# FOB e FAS nomeiam o porto de embarque; EXW e FCA costumam nomear fábrica ou armazém e não entram
INCOTERMS_PORTO_DE_EMBARQUE = {"FOB", "FAS"}
