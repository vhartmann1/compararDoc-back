"""Documentos que não entram na comparação: de outro tipo, conhecimento de saída, proforma e resumo de invoices."""

import re
from dataclasses import dataclass

from app.schemas import ArquivoEntrada, DocumentoExtraido, ExtracaoArquivo
from app.services.comparacao.constantes import TIPOS
from app.services.comparacao.documentos.identificacao_do_documento import e_proforma, nome_doc
from app.services.comparacao.normalizacao.numeros_de_documento import numero_sem_serie
from app.services.comparacao.normalizacao.portos import porto_brasileiro
from app.services.comparacao.particao import particionar
from app.services.comparacao.tipos import Fonte


@dataclass
class Separacao:
    ficam: list[Fonte]
    saem: list[Fonte]
    avisos: list[str]


def aviso_de_outro_tipo(arquivo: ArquivoEntrada, extracao: ExtracaoArquivo) -> str | None:
    """Arquivo em que nada é invoice, packing list nem conhecimento."""
    if not extracao.documentos or any(d.tipo in TIPOS for d in extracao.documentos):
        return None
    lidos = ", ".join(dict.fromkeys(d.subtipo or "documento de outro tipo" for d in extracao.documentos))
    return f"{arquivo.nome} não entrou na comparação: não é invoice, packing list nem conhecimento ({lidos})."


def sem_conhecimentos_de_saida(conhecimentos: list[Fonte]) -> Separacao:
    """Sai do Brasil para o exterior e há outro que chega ao Brasil: é de exportação ou devolução, não o da importação."""
    if not any(_chega_ao_brasil(f.doc) for f in conhecimentos):
        return Separacao(conhecimentos, [], [])
    saida, ficam = particionar(conhecimentos, lambda f: _sai_do_brasil(f.doc))
    avisos = [
        f"{nome_doc(f)} ({_onde(f)}) não entrou na comparação: é de exportação ou devolução "
        f"({f.doc.porto_origem.valor} → {f.doc.porto_destino.valor})."
        for f in saida
    ]
    return Separacao(ficam, saida, avisos)


def _chega_ao_brasil(doc: DocumentoExtraido) -> bool:
    origem, destino = doc.porto_origem, doc.porto_destino
    return bool(origem and destino) and porto_brasileiro(destino.valor) and not porto_brasileiro(origem.valor)


def _sai_do_brasil(doc: DocumentoExtraido) -> bool:
    origem, destino = doc.porto_origem, doc.porto_destino
    return bool(origem and destino) and porto_brasileiro(origem.valor) and not porto_brasileiro(destino.valor)


def separar_proformas(invoices: list[Fonte]) -> Separacao:
    """Proforma (lida como tal, ex. uma aba do Excel) sai quando há invoice comercial: é o pedido, não o embarque."""
    proformas, comerciais = particionar(invoices, lambda f: e_proforma(f.doc))
    if not comerciais:
        return Separacao(invoices, [], [])
    avisos = [f"{nome_doc(f)} ({_onde(f)}) não entrou na comparação: há invoice comercial." for f in proformas]
    return Separacao(comerciais, proformas, avisos)


def separar_resumos(invoices: list[Fonte]) -> Separacao:
    """Invoice cujo número junta o de duas ou mais outras do processo ('A1, A2') é o resumo delas: sai da soma."""
    numeros = {numero_sem_serie(f.doc.numero) for f in invoices if f.doc.numero}
    resumos, ficam = particionar(invoices, lambda f: _junta_outras(f.doc.numero, numeros))
    avisos = [
        f"Invoice {f.doc.numero} ({_onde(f)}) não entrou na comparação: é o resumo das outras invoices." for f in resumos
    ]
    return Separacao(ficam, resumos, avisos)


SEPARADOR_DE_NUMEROS = re.compile(r"(?i)\s*[,;/&+]\s*|\s+E\s+|\s+AND\s+")


def _junta_outras(numero: str | None, numeros: set[str]) -> bool:
    return bool(numero) and len(_partes(numero) & numeros) >= 2


def _partes(numero: str) -> set[str]:
    return {numero_sem_serie(p) for p in SEPARADOR_DE_NUMEROS.split(numero) if p.strip()}


def _onde(f: Fonte) -> str:
    paginas = ", ".join(str(p) for p in f.doc.paginas)
    return f"{f.arquivo.nome}, pág. {paginas}" if paginas else f.arquivo.nome
