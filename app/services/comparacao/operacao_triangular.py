"""Operação triangular: shipper do conhecimento de outra empresa que o exportador da invoice/PL."""

from dataclasses import dataclass

from app.schemas import NomeCampo, Parte
from app.services.comparacao.identificacao_do_documento import nome_doc
from app.services.comparacao.mesma_empresa import relacao_entre_partes
from app.services.comparacao.normalizacao import enderecos_compativeis
from app.services.comparacao.regras_por_campo.exportador_consignatario import fabricante_alternativo
from app.services.comparacao.tipos import Col, Fonte

CAMPOS_DO_EXPORTADOR: set[NomeCampo] = {"exportador", "endereco_exportador", "pais_exportador"}

DE_QUEM = {"invoice": ("da invoice", "das invoices"), "packing_list": ("do packing list", "dos packing lists")}


@dataclass
class Triangulacao:
    conhecimento: Col
    shipper: Parte
    outras: list[Fonte]  # invoice/PL de outra empresa: só aviso
    proprias: list[Fonte]  # invoice/PL da mesma empresa (ou incerta): comparadas com o conhecimento


def triangulacoes(colunas: list[Col]) -> list[Triangulacao]:
    """Conhecimentos cujo shipper é outra empresa que o exportador de alguma invoice/PL da comparação."""
    referencias = [f for col in colunas if not col.chave.startswith("conhecimento") for f in col.fontes]
    resultado = []
    for col in colunas:
        shipper = col.fontes[0].doc.exportador if col.chave.startswith("conhecimento") else None
        if shipper is None or not shipper.nome.strip():
            continue
        proprias, outras = separar_por_empresa(shipper, referencias)
        if outras:
            resultado.append(Triangulacao(col, shipper, outras, proprias))
    return resultado


def separar_por_empresa(shipper: Parte, fontes: list[Fonte]) -> tuple[list[Fonte], list[Fonte]]:
    """(da mesma empresa do shipper ou incertas, de outra empresa)."""
    proprias: list[Fonte] = []
    outras: list[Fonte] = []
    for f in fontes:
        (outras if _de_outra_empresa(shipper, f) else proprias).append(f)
    return proprias, outras


def _partes_do_exportador(f: Fonte) -> list[Parte]:
    return [p for p in (f.doc.exportador, fabricante_alternativo(f)) if p and p.nome.strip()]


def _de_outra_empresa(shipper: Parte, f: Fonte) -> bool:
    """Outra empresa só com o endereço do shipper no conhecimento, diferente do exportador e do fabricante."""
    partes = _partes_do_exportador(f)
    if not partes or not _tem_endereco(shipper):
        return False
    return all(relacao_entre_partes(shipper, p) == "outra" and not _mesmo_endereco(shipper, p) for p in partes)


def _tem_endereco(parte: Parte) -> bool:
    return bool(parte.endereco and parte.endereco.strip())


def _mesmo_endereco(a: Parte, b: Parte) -> bool:
    if not (_tem_endereco(a) and _tem_endereco(b)):
        return False
    return enderecos_compativeis((a.endereco.strip(), a.cidade), (b.endereco.strip(), b.cidade))


def aviso_triangular(prefixo: str, t: Triangulacao) -> str:
    exportadores = " / ".join(dict.fromkeys(_nome_do_exportador(f) for f in t.outras))
    return (f"{prefixo}Shipper do {t.conhecimento.nome_curto} ({t.shipper.nome.strip()}) é outra empresa que o "
            f"exportador {_de_quem(t.outras)} ({exportadores}): operação triangular, não é divergência.")


def _nome_do_exportador(f: Fonte) -> str:
    """O exportador; sem nome, o fabricante; sem nenhum dos dois, o próprio documento."""
    partes = _partes_do_exportador(f)
    return partes[0].nome.strip() if partes else nome_doc(f)


def _de_quem(fontes: list[Fonte]) -> str:
    tipos = dict.fromkeys(f.doc.tipo for f in fontes)
    return " e ".join(DE_QUEM[t][sum(f.doc.tipo == t for f in fontes) > 1] for t in tipos)


def coluna_das_proprias(t: Triangulacao) -> Col:
    """As invoices/PLs da mesma empresa do shipper, como coluna (só dado: rótulo e fontes)."""
    curto = "/".join(dict.fromkeys(nome_doc(f) for f in t.proprias))
    return Col(f"proprias_{t.conhecimento.chave}", curto, curto, t.proprias, soma=len(t.proprias) > 1)
