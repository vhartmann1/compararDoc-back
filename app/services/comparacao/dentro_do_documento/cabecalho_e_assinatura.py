"""Empresa do cabeçalho × quem assina × vendedor × fabricante da invoice/PL: o arranjo que os quatro formam."""

from dataclasses import dataclass

from app.schemas import Divergencia
from app.services.comparacao.documentos.identificacao_do_documento import nome_doc
from app.services.comparacao.mensagens import Diferenca, divergencia_interna
from app.services.comparacao.partes.mesma_empresa import relacao_entre_nomes
from app.services.comparacao.tipos import Fonte


@dataclass(frozen=True)
class Empresas:
    """Os quatro nomes que o documento traz."""

    cabecalho: str
    assinatura: str
    vendedor: str
    fabricante: str


def empresas_do_documento(f: Fonte) -> Empresas | None:
    """Só invoice/PL com os quatro nomes; no conhecimento o cabeçalho é do transportador ou agente."""
    if f.doc.tipo == "conhecimento":
        return None
    d = f.doc
    nomes = (_nome(d.empresa_cabecalho), _nome(d.emitente_assinatura), _nome(d.exportador and d.exportador.nome),
             _fabricante_declarado(f))
    return Empresas(*nomes) if all(nomes) else None


def triangular(e: Empresas) -> bool:
    """Cabeçalho do fabricante declarado, e quem assina é o vendedor, outra empresa."""
    return _mesma(e.cabecalho, e.fabricante) and _mesma(e.assinatura, e.vendedor) and _outra(e.vendedor, e.fabricante)


def terceira_no_cabecalho(e: Empresas) -> bool:
    return _outra(e.cabecalho, e.vendedor, e.fabricante)


def terceira_assinando(e: Empresas) -> bool:
    return _outra(e.assinatura, e.vendedor, e.cabecalho)


def divergencias_do_cabecalho(f: Fonte) -> list[Divergencia]:
    e = empresas_do_documento(f)
    if e is None:
        return []
    mensagens = []
    if terceira_no_cabecalho(e):
        mensagens.append(f"cabeçalho de {e.cabecalho}, que não é o vendedor ({e.vendedor}) "
                         f"nem o fabricante declarado ({e.fabricante})")
    if terceira_assinando(e):
        mensagens.append(f"assinado por {e.assinatura}, que não é o vendedor ({e.vendedor}) "
                         f"nem a empresa do cabeçalho ({e.cabecalho})")
    return [_interna(f, e, m) for m in mensagens]


def avisos_do_cabecalho(fontes: list[Fonte]) -> list[str]:
    return [
        f"{nome_doc(f)}: cabeçalho do fabricante declarado ({e.cabecalho}) e quem vende e assina é "
        f"{e.assinatura}: operação triangular, confira se é esperado."
        for f in fontes
        if (e := empresas_do_documento(f)) and triangular(e)
    ]


def _interna(f: Fonte, e: Empresas, mensagem: str) -> Divergencia:
    evidencia = f"Cabeçalho: {e.cabecalho} × Assinatura: {e.assinatura} × Vendedor: {e.vendedor}"
    pagina = f.doc.exportador.pagina if f.doc.exportador else None
    return divergencia_interna(f, Diferenca(mensagem), evidencia, pagina)


def _fabricante_declarado(f: Fonte) -> str | None:
    """O fabricante declarado no próprio documento: a conferência é interna."""
    return _nome(f.doc.fabricante and f.doc.fabricante.nome)


def _nome(texto: str | None) -> str | None:
    return texto.strip() if texto and texto.strip() else None


def _mesma(a: str, b: str) -> bool:
    return relacao_entre_nomes(a, b) == "mesma"


def _outra(nome: str, *outros: str) -> bool:
    return all(relacao_entre_nomes(nome, o) == "outra" for o in outros)
