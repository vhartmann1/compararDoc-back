"""Pedaços que se repetem nas mensagens: o que pedir, o que conferir e a divergência interna de um documento."""

from app.schemas import Divergencia
from app.services.comparacao.documentos.identificacao_do_documento import nome_doc, ref_documento
from app.services.comparacao.tipos import Fonte


ARTIGOS = (("Packing Lists", "os"), ("Packing List", "o"), ("Invoices", "as"), ("Invoice", "a"), ("Proforma", "a"))


def _com_artigo(nome: str) -> tuple[str, str]:
    """'Invoices' -> ('as', 'invoices'); conhecimento ('BL', 'AWB 1') fica como está, com 'o'."""
    for tipo, artigo in ARTIGOS:
        if nome.startswith(tipo):
            return artigo, tipo.lower() + nome[len(tipo):]
    return "o", nome


def sujeito(nomes: list[str]) -> tuple[str, bool]:
    """(['Invoice', 'Packing List']) -> ('a invoice e o packing list', True): o texto e se o verbo vai no plural."""
    com_artigo = [_com_artigo(n) for n in nomes]
    plural = len(nomes) > 1 or com_artigo[0][0] in ("os", "as")
    return " e ".join(f"{a} {n}" for a, n in com_artigo), plural


def nos_documentos(nomes: list[str]) -> str:
    """(['Invoices', 'BL']) -> 'nas invoices e no BL'."""
    return " e ".join(f"n{a} {n}" for a, n in map(_com_artigo, nomes))


def maiuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


TAMANHO_DO_TRECHO = 45


def trecho(texto: str, outro: str) -> str:
    """Começo do texto até um pouco depois de onde ele difere do outro, com reticências se cortou."""
    inicio_igual = next((n for n, (a, b) in enumerate(zip(texto.upper(), outro.upper())) if a != b), len(outro))
    limite = max(TAMANHO_DO_TRECHO, inicio_igual + 15)
    if len(texto) <= limite:
        return texto
    corte = texto[:limite + 1].rsplit(" ", 1)[0] if " " in texto[:limite + 1] else texto[:limite]
    return corte.rstrip(" ,;-") + "…"


def pedir(mensagem: str, o_que: str) -> str:
    """'a soma não bate', 'correção' -> 'a soma não bate; pedir correção.'"""
    return f"{mensagem}; pedir {o_que}."


def confira(mensagem: str, como: str | None = None) -> str:
    """'unidades diferentes', 'manualmente' -> 'unidades diferentes; confira manualmente.'"""
    return f"{mensagem}; confira {como}." if como else f"{mensagem}; confira."


def divergencia_interna(
    f: Fonte, mensagem: str, evidencia: str | None = None, pagina: int | None = None
) -> Divergencia:
    """Contradição dentro do próprio documento, com o nome dele na frente da mensagem."""
    return Divergencia(categoria="interna", comparacao_id=None, campo=None, mensagem=f"{nome_doc(f)}: {mensagem}",
                       documento=ref_documento(f), evidencia=evidencia, pagina=pagina)
