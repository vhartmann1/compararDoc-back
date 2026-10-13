"""Nome, número e referência de um documento, para as mensagens e para a tela."""

from app.schemas import DocumentoRef
from app.services.comparacao.constantes import NOME_TIPO
from app.services.comparacao.normalizacao import normalizar_numero_documento
from app.services.comparacao.tipos import Fonte


def nome_doc(f: Fonte) -> str:
    """'Invoice L30518777', 'AWB 123-4567 8901', 'Packing List'."""
    if f.doc.tipo == "conhecimento":
        nome = f.doc.subtipo or "Conhecimento"
    else:
        nome = NOME_TIPO[f.doc.tipo]
    return f"{nome} {f.doc.numero}" if f.doc.numero else nome


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
