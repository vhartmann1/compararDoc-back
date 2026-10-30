"""Nome, número e referência de um documento, para as mensagens e para a tela."""

import re

from app.schemas import DocumentoExtraido, DocumentoRef
from app.services.comparacao.constantes import NOME_TIPO
from app.services.comparacao.normalizacao.numeros_de_documento import normalizar_numero_documento
from app.services.comparacao.tipos import Fonte

PROFORMA = re.compile(r"(?i)pro[\s_-]?forma")


def e_proforma(doc: DocumentoExtraido) -> bool:
    """Invoice que a leitura marcou como proforma (subtipo), ex. a aba 'Proforma Invoice' de um Excel."""
    return doc.tipo == "invoice" and bool(PROFORMA.search(doc.subtipo or ""))


def nome_doc(f: Fonte) -> str:
    """'Invoice L30518777', 'Proforma PI-9', 'AWB 123-4567 8901'; sem número, pelo arquivo: 'Packing List (PL.pdf)'."""
    nome = nome_do_tipo(f)
    return f"{nome} {f.doc.numero}" if f.doc.numero else f"{nome} ({f.arquivo.nome})"


def nome_doc_escaneado(f: Fonte) -> str:
    """'Invoice 7 (INV.pdf, escaneado)'; sem número: 'Packing List (PL.pdf, escaneado)'."""
    nome = " ".join(filter(None, (nome_do_tipo(f), f.doc.numero)))
    return f"{nome} ({f.arquivo.nome}, escaneado)"


def nome_do_tipo(f: Fonte) -> str:
    if f.doc.tipo == "conhecimento":
        return f.doc.subtipo or "Conhecimento"
    return "Proforma" if e_proforma(f.doc) else NOME_TIPO[f.doc.tipo]


def numero_normalizado(numero: str | None) -> str:
    return normalizar_numero_documento(numero) if numero else ""


def ref_documento(f: Fonte) -> DocumentoRef:
    return DocumentoRef(
        tipo=f.doc.tipo,
        subtipo=f.doc.subtipo,
        arquivo_id=f.arquivo.id,
        arquivo_nome=f.arquivo.nome,
        paginas=f.doc.paginas,
        numero=f.doc.numero,
        versao=f.doc.versao,
    )
