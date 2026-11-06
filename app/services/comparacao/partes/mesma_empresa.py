"""Se duas razões sociais são da mesma empresa, de outra ou se não dá para dizer."""

from typing import Literal

from app.schemas import Parte
from app.services.comparacao.normalizacao.codigos import normalizar_cnpj
from app.services.comparacao.normalizacao.texto import distancia_de_edicao
from app.services.comparacao.partes.razao_social import nomes_equivalentes, palavras_distintivas

Relacao = Literal["mesma", "outra", "incerta"]
Registro = tuple[str, str | None]  # (razão social, CNPJ/Tax ID)

# Letras trocadas que ainda podem ser erro de digitação: 1 em palavra de até 5 letras, 2 a partir de 6.
TAMANHO_PALAVRA_LONGA = 6


def relacao_entre_nomes(a: str, b: str) -> Relacao:
    """Mesma: nome equivalente ou as mesmas palavras na mesma ordem; outra: nenhuma palavra igual ou quase igual."""
    if nomes_equivalentes(a, b):
        return "mesma"
    pa, pb = palavras_distintivas(a), palavras_distintivas(b)
    if not pa or not pb:
        return "incerta"
    if pa == pb:
        return "mesma"
    return "incerta" if any(_quase_iguais(x, y) for x in pa for y in pb) else "outra"


def _quase_iguais(x: str, y: str) -> bool:
    limite = 2 if max(len(x), len(y)) >= TAMANHO_PALAVRA_LONGA else 1
    return abs(len(x) - len(y)) <= limite and distancia_de_edicao(x, y) <= limite


def mesmo_grupo(a: str, b: str) -> bool:
    """Uma palavra distintiva igual e, dos dois lados, alguma sem par quase igual: empresas do grupo, não digitação."""
    pa, pb = palavras_distintivas(a), palavras_distintivas(b)
    return bool(set(pa) & set(pb)) and _alguma_sem_par(pa, pb) and _alguma_sem_par(pb, pa)


def _alguma_sem_par(xs: tuple[str, ...], ys: tuple[str, ...]) -> bool:
    return any(not any(_quase_iguais(x, y) for y in ys) for x in xs)


def relacao_entre_partes(a: Parte, b: Parte) -> Relacao:
    """O mesmo CNPJ/Tax ID decide; senão, o nome."""
    ca, cb = normalizar_cnpj(a.cnpj), normalizar_cnpj(b.cnpj)
    if ca and ca == cb:
        return "mesma"
    return relacao_entre_nomes(a.nome, b.nome)


def registro(parte: Parte) -> Registro:
    return parte.nome, parte.cnpj


def mesma_empresa_registrada(a: Registro, b: Registro) -> bool:
    """CNPJ estrito: os dois com CNPJ/Tax ID => os dígitos decidem; senão, o nome tem de ser da mesma empresa."""
    ca, cb = normalizar_cnpj(a[1]), normalizar_cnpj(b[1])
    return ca == cb if ca and cb else relacao_entre_nomes(a[0], b[0]) == "mesma"
