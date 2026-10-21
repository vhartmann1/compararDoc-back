"""Se duas razões sociais são da mesma empresa, de outra ou se não dá para dizer."""

import re
from typing import Literal

from app.schemas import Parte
from app.services.comparacao.normalizacao import nomes_equivalentes, normalizar_cnpj, sem_acento

Relacao = Literal["mesma", "outra", "incerta"]

# Só forma jurídica e termos que não distinguem uma empresa da outra; artigos e IMPORT/EXPORT distinguem.
TERMOS_GENERICOS = {
    "LTD", "LTDA", "CO", "SAS", "SA", "INC", "LIMITED", "EIRELI", "ME", "EPP", "CORP", "LLC", "GMBH", "SRL",
    "SPA", "SRLS", "SNC", "AG", "KG", "BV", "NV", "PTE", "PT", "TBK", "ULC", "PLC", "LLP", "LP", "OY", "AB", "AS",
    "APS", "SARL", "SL", "SLU", "CV", "SCCM", "COOP", "COOPERATIVA", "SDAD", "SOCIEDAD", "SOCIEDADE", "SOCIETA",
    "UNIPERSONALE", "LIMITADA", "CORPORATION", "INCORPORATED", "COMPANY", "COMPANHIA", "COMPANIA", "CIA", "KK",
    "AZIENDA", "AGRICOLA", "BRANCH",
}

# Formas jurídicas que aparecem coladas no nome; só as que não terminam palavras comuns (CIA, SAS, SPA ficam fora).
FORMAS_COLAVEIS = ("LIMITED", "LTDA", "GMBH", "SARL", "LTD", "LLC", "INC", "SRL")

# Letras trocadas que ainda podem ser erro de digitação: 1 em palavra de até 5 letras, 2 a partir de 6.
TAMANHO_PALAVRA_LONGA = 6


def palavras_distintivas(nome: str) -> tuple[str, ...]:
    """Palavras do nome, na ordem, sem forma jurídica: 'LA SERRA VERDE S.r.l.' -> ('LA', 'SERRA', 'VERDE')."""
    texto = re.sub(r"[^A-Z0-9 ]", " ", sem_acento(nome).upper().replace(".", ""))
    palavras = (_sem_forma_juridica_colada(_digitos_como_letras(p)) for p in texto.split())
    return tuple(p for p in palavras if p not in TERMOS_GENERICOS)


def _digitos_como_letras(palavra: str) -> str:
    """'K0RN' -> 'KORN': 0 e 1 no meio de uma palavra quase só de letras são O e I lidos errado."""
    letras = sum(c.isalpha() for c in palavra)
    if letras < 2 or len(palavra) - letras > 1:
        return palavra
    return palavra.replace("0", "O").replace("1", "I")


def _sem_forma_juridica_colada(palavra: str) -> str:
    """'KRONGMBH' -> 'KRON': forma jurídica de 3+ letras colada no fim, sobrando 3+ letras."""
    for termo in FORMAS_COLAVEIS:
        if palavra.endswith(termo) and len(palavra) - len(termo) >= 3:
            return palavra[: -len(termo)]
    return palavra


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
    return abs(len(x) - len(y)) <= limite and _distancia_de_edicao(x, y) <= limite


def _distancia_de_edicao(x: str, y: str) -> int:
    """Damerau-Levenshtein restrita: inserção, remoção, troca e vizinhas invertidas custam 1 cada."""
    duas_atras: list[int] = []
    anterior = list(range(len(y) + 1))
    for i, cx in enumerate(x, start=1):
        atual = [i]
        for j, cy in enumerate(y, start=1):
            custo = min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + (cx != cy))
            if i > 1 and j > 1 and cx == y[j - 2] and x[i - 2] == cy:
                custo = min(custo, duas_atras[j - 2] + 1)
            atual.append(custo)
        duas_atras, anterior = anterior, atual
    return anterior[-1]


def relacao_entre_partes(a: Parte, b: Parte) -> Relacao:
    """O mesmo CNPJ/Tax ID decide; senão, o nome."""
    ca, cb = normalizar_cnpj(a.cnpj), normalizar_cnpj(b.cnpj)
    if ca and ca == cb:
        return "mesma"
    return relacao_entre_nomes(a.nome, b.nome)
