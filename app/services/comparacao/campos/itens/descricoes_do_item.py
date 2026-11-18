"""Descrições do mesmo item em dois documentos: iguais, escritas de outro jeito, outra mercadoria ou contradição."""

from dataclasses import dataclass
from typing import Literal

from app.services.comparacao.campos.itens.contradicao_na_descricao import Contradicao, contradicao
from app.services.comparacao.campos.itens.fichas_da_descricao import em_comum, fichas, quase_iguais
from app.services.comparacao.campos.itens.tipos import ItemAgrupado
from app.services.comparacao.normalizacao.item import normalizar_codigo_item, normalizar_lote, normalizar_referencia
from app.services.comparacao.normalizacao.texto import distancia_de_edicao

Classe = Literal["igual", "escrita_diferente", "outra_mercadoria", "contradicao"]
GRAVIDADE: dict[Classe, int] = {"igual": 0, "escrita_diferente": 1, "outra_mercadoria": 2, "contradicao": 3}
# Menos da metade da descrição mais curta na outra: os documentos não descrevem a mesma mercadoria
COBERTURA_MINIMA = 0.5


@dataclass(frozen=True)
class Veredito:
    classe: Classe
    contradicao: Contradicao | None = None  # na contradição, o que cada lado diz

    @property
    def diverge(self) -> bool:
        return self.classe in ("outra_mercadoria", "contradicao")

    def invertido(self) -> "Veredito":
        c = self.contradicao
        return Veredito(self.classe, c and Contradicao(c.de_b, c.de_a, c.um_caractere))


IGUAL = Veredito("igual")


def comparar_descricoes(a: ItemAgrupado, b: ItemAgrupado) -> Veredito:
    """O pior caso entre as linhas dos dois itens; com o mesmo código ou lote, só a contradição diverge."""
    modelos = _modelos_quase_iguais(a, b)
    if modelos:
        return Veredito("contradicao", modelos)
    ta, tb = textos_do_item(a), textos_do_item(b)
    de_a = [_com_a_mais_parecida(x, tb) for x in ta]
    de_b = [_com_a_mais_parecida(y, ta).invertido() for y in tb]
    pior = max(de_a + de_b, key=lambda v: GRAVIDADE[v.classe])
    if pior.classe != "contradicao" and (_mesmo_codigo(a, b) or _mesmo_lote(a, b)):
        return IGUAL
    return pior


def textos_do_item(x: ItemAgrupado) -> tuple[str, ...]:
    """A descrição de cada linha do item, com a referência lida quando ela não está na descrição."""
    ref = x.referencia or ""
    fora = bool(ref) and normalizar_referencia(ref) not in normalizar_referencia(x.descricao)
    return tuple(f"{d} {ref}" if fora else d for d in x.descricoes or (x.descricao,))


def _com_a_mais_parecida(texto: str, outros: tuple[str, ...]) -> Veredito:
    """Uma linha vale pela linha do outro documento com que mais se parece."""
    return min((entre_textos(texto, outro) for outro in outros), key=lambda v: GRAVIDADE[v.classe])


def entre_textos(a: str, b: str) -> Veredito:
    """Contradição; pouco em comum; cada um diz algo que o outro não diz; ou um só diz mais que o outro."""
    achada = contradicao(a, b)
    if achada:
        return Veredito("contradicao", achada)
    comum = em_comum(a, b)
    if not comum.algo_distintivo:
        return Veredito("outra_mercadoria")
    if not (comum.so_a and comum.so_b):
        return IGUAL
    mesmo_produto = comum.codigo_em_comum or comum.cobertura >= COBERTURA_MINIMA
    return Veredito("escrita_diferente" if mesmo_produto else "outra_mercadoria")


def _modelos_quase_iguais(a: ItemAgrupado, b: ItemAgrupado) -> Contradicao | None:
    """O modelo lido nos dois documentos com um caractere de diferença numa parte: 'ZK 455' × 'YK 455'."""
    if not (a.referencia and b.referencia):
        return None
    fa, fb = fichas(a.referencia), fichas(b.referencia)
    so_a, so_b = [f for f in fa if f not in fb], [f for f in fb if f not in fa]
    inteiros = quase_iguais(normalizar_referencia(a.referencia), normalizar_referencia(b.referencia))  # 'BX-7' × 'BX-9'
    if inteiros or any(_uma_letra_trocada(x, y) or quase_iguais(x, y) for x in so_a for y in so_b):
        return Contradicao(a.referencia.strip(), b.referencia.strip(), um_caractere=True)
    return None


def _uma_letra_trocada(x: str, y: str) -> bool:
    """Sigla de duas letras com uma trocada ('ZK' × 'YK'): no modelo é outro produto, não erro de digitação."""
    return len(x) == len(y) == 2 and distancia_de_edicao(x, y) == 1


def _mesmo_codigo(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    return bool(a.codigo and b.codigo and normalizar_codigo_item(a.codigo) == normalizar_codigo_item(b.codigo))


def _mesmo_lote(a: ItemAgrupado, b: ItemAgrupado) -> bool:
    return bool({normalizar_lote(l) for l in a.lotes} & {normalizar_lote(l) for l in b.lotes})
