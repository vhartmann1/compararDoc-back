"""Pedaços que se repetem nas mensagens: o que pedir, o que conferir e a divergência interna de um documento."""

from dataclasses import dataclass

from app.schemas import CategoriaDivergencia, Divergencia, NomeCampo
from app.services.comparacao.documentos.identificacao_do_documento import nome_doc, ref_documento
from app.services.comparacao.tipos import Fonte, prefixo_da_origem


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


@dataclass(frozen=True)
class Diferenca:
    """O que difere e, se houver, o que fazer ('pedir correção')."""

    detalhe: str
    acao: str | None = None

    def texto(self) -> str:
        return f"{self.detalhe}; {self.acao}." if self.acao else self.detalhe


def pedido(detalhe: str, o_que: str) -> Diferenca:
    """'a soma não bate', 'correção' -> a diferença com a ação 'pedir correção'."""
    return Diferenca(detalhe, f"pedir {o_que}")


def pedir(mensagem: str, o_que: str) -> str:
    """'a soma não bate', 'correção' -> 'a soma não bate; pedir correção.'"""
    return pedido(mensagem, o_que).texto()


def confira(mensagem: str, como: str | None = None) -> str:
    """'unidades diferentes', 'manualmente' -> 'unidades diferentes; confira manualmente.'"""
    return Diferenca(mensagem, f"confira {como}" if como else "confira").texto()


def _mensagem(inicio: str, rotulo: str | None, diferenca: Diferenca) -> str:
    """A única montagem da mensagem a partir das partes."""
    return inicio + (f"{rotulo}: " if rotulo else "") + diferenca.texto()


def divergencia(
    categoria: CategoriaDivergencia, comparacao_id: str | None, campo: NomeCampo | None, origem: str | None,
    rotulo: str | None, diferenca: Diferenca, **resto,
) -> Divergencia:
    """Divergência entre documentos: 'Origem — Rótulo: detalhe; ação.'"""
    return Divergencia(categoria=categoria, comparacao_id=comparacao_id, campo=campo,
                       mensagem=_mensagem(prefixo_da_origem(origem), rotulo, diferenca), origem=origem, rotulo=rotulo,
                       detalhe=diferenca.detalhe, acao=diferenca.acao, **resto)


def divergencia_do_documento(
    f: Fonte, diferenca: Diferenca, categoria: CategoriaDivergencia = "interna", campo: NomeCampo | None = None,
    **resto,
) -> Divergencia:
    """Problema de um documento: 'Documento: detalhe; ação.'"""
    origem = nome_doc(f)
    return Divergencia(categoria=categoria, comparacao_id=None, campo=campo,
                       mensagem=_mensagem(f"{origem}: ", None, diferenca), origem=origem, detalhe=diferenca.detalhe,
                       acao=diferenca.acao, documento=ref_documento(f), **resto)


def divergencia_interna(
    f: Fonte, diferenca: Diferenca, evidencia: str | None = None, pagina: int | None = None
) -> Divergencia:
    """Contradição dentro do próprio documento, com o nome dele na frente da mensagem."""
    return divergencia_do_documento(f, diferenca, evidencia=evidencia, pagina=pagina)


def divergencia_do_modelo(f: Fonte, texto: str, evidencia: str | None, pagina: int | None) -> Divergencia:
    """Contradição escrita pela leitura: o texto vem pronto, só a origem é parte separada."""
    origem = nome_doc(f)
    return Divergencia(categoria="interna", comparacao_id=None, campo=None,
                       mensagem=_mensagem(f"{origem}: ", None, Diferenca(texto)), origem=origem,
                       documento=ref_documento(f), evidencia=evidencia, pagina=pagina)
