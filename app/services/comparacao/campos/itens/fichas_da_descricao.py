"""Palavras, números e códigos de uma descrição numa notação só, e o que duas descrições têm em comum."""

import re
from dataclasses import dataclass

from app.services.comparacao.normalizacao.texto import distancia_de_edicao, sem_acento

POLEGADAS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\"|''|’’|”|″|INCH(?:ES)?\b)")
ENTRE_NUMEROS = re.compile(r"(?<=\d)\s*(?:MM)?\s*[X×*]\s*(?=[\d.])")  # o 'x' de '0.600x900' e de '.600 MM x 900'
FICHA = re.compile(r"\d+\.\d+|(?<![A-Z0-9])\.\d+|[A-Z0-9]+")  # '.800' é decimal; o '.2' de 'NO.2' não é
PARTE = re.compile(r"\d*\.\d+|\d+|[A-Z]+")
NUMERO_COM_UNIDADE = re.compile(r"(\d+)([A-Z]+)")
SERIE = re.compile(r"(?<![A-Z0-9])([A-Z]{1,2})(\d+)(?![A-Z0-9])")
# Palavras de ligação: estar nas duas descrições não diz que o produto é o mesmo
GENERICAS = {"THE", "AND", "FOR", "WITH", "FROM", "EACH", "DOS", "DAS", "COM", "PARA", "POR", "SEM", "QUE", "UMA",
             "CADA", "DEL", "LOS", "LAS", "CON", "PER", "DES", "LES", "UND", "MIT"}


def _numero(ficha: str) -> str:
    """'0.800' -> '0.8', '06' -> '6'; código comprido só de dígitos fica como está."""
    if re.fullmatch(r"\d*\.\d+", ficha):
        return f"{float(ficha):g}"
    return str(int(ficha)) if ficha.isdigit() and len(ficha) <= 9 else ficha


def _texto(descricao: str) -> str:
    """Maiúsculas sem acento, sem a marca de polegadas e sem o 'x' das dimensões."""
    return ENTRE_NUMEROS.sub(" ", POLEGADAS.sub(r" \1 ", sem_acento(descricao).upper()))


def fichas(descricao: str) -> list[str]:
    """'Gong 06" K-30 0.600x900.000 6pack' -> GONG, 6, K, 30, 0.6, 900, 6, PACK: palavra, número ou código inteiro."""
    return [_numero(p) for f in FICHA.findall(_texto(descricao)) for p in _numero_e_unidade(f)]


def _numero_e_unidade(ficha: str) -> list[str]:
    """'6PACK' -> 6, PACK: o número colado à unidade se separa; o código que começa por letra ('X450') fica inteiro."""
    achado = NUMERO_COM_UNIDADE.fullmatch(ficha)
    return list(achado.groups()) if achado else [ficha]


def partes(descricao: str) -> list[str]:
    """Como as fichas, com letras e números separados: 'X450' -> X, 450; '4PACK' -> 4, PACK."""
    return [_numero(p) for f in FICHA.findall(_texto(descricao)) for p in PARTE.findall(f)]


def polegadas(descricao: str) -> set[float]:
    return {float(n) for n in POLEGADAS.findall(sem_acento(descricao).upper())}


def tem_numero(ficha: str) -> bool:
    return any(c.isdigit() for c in ficha)


def colar(minhas: list[str], do_outro: set[str]) -> set[str]:
    """Duas seguidas que o outro lado escreve juntas viram uma: 'HI HAT' × 'HIHAT', '3190 N' × '3190N'."""
    coladas, i = [], 0
    while i < len(minhas):
        junta = _junta_que_o_outro_escreve(minhas[i: i + 2], minhas, do_outro)
        coladas.append(junta or minhas[i])
        i += 2 if junta else 1
    return set(coladas)


def _junta_que_o_outro_escreve(par: list[str], minhas: list[str], do_outro: set[str]) -> str | None:
    if len(par) < 2:
        return None
    juntas = ["".join(par)]
    if par[0].isdigit() and par[1].isdigit():
        juntas.append(_numero(".".join(par)))  # vírgula decimal de um lado, ponto do outro
    return next((j for j in juntas if j in do_outro and j not in minhas), None)


def mesma_palavra(x: str, y: str) -> bool:
    """Erro de digitação ou plural numa palavra: 'CRAS' × 'CRASH', 'KIT' × 'KITS'; em número ou código não vale."""
    return x.isalpha() and y.isalpha() and max(len(x), len(y)) >= 4 and distancia_de_edicao(x, y) == 1


def quase_iguais(x: str, y: str) -> bool:
    """Um caractere de diferença entre identificadores: 'TS100' × 'TS200', '615' × '6158'; nunca só a letra de série."""
    curto, longo = sorted((x, y), key=len)
    if len(longo) < 3 or distancia_de_edicao(x, y) != 1:
        return False
    if len(longo) > len(curto):  # 'X450' × '450', '3190N' × '3190': a letra na ponta é série, não outro modelo
        sobra = longo[0] if longo.endswith(curto) else longo[-1] if longo.startswith(curto) else ""
        return not sobra.isalpha()
    return True


@dataclass(frozen=True)
class EmComum:
    """As partes que duas descrições têm em comum e as que só uma traz."""

    comum: frozenset[str]
    so_a: frozenset[str]
    so_b: frozenset[str]

    @property
    def algo_distintivo(self) -> bool:
        """Algo em comum que diz qual é o produto: número, código de 2+ caracteres ou palavra que não é de ligação."""
        return any((tem_numero(p) and len(p) >= 2) or (p.isalpha() and len(p) >= 3 and p not in GENERICAS)
                   for p in self.comum)

    @property
    def codigo_em_comum(self) -> bool:
        """Os dois trazem o mesmo código de letras e números ('K1', 'QX77'): é o mesmo modelo."""
        return any(tem_numero(p) and not p[0].isdigit() for p in self.comum)

    @property
    def cobertura(self) -> float:
        """Quanto da descrição mais curta está na outra, de 0 a 1."""
        menor = min(len(self.comum) + len(self.so_a), len(self.comum) + len(self.so_b))
        return len(self.comum) / menor if menor else 0.0


def em_comum(a: str, b: str) -> EmComum:
    """Compara as fichas inteiras: 'TS1' não está em 'TS100-01'; só a letra de série na frente não muda o modelo."""
    comum, so_a, so_b = _comparar(fichas(a), fichas(b))
    for x in sorted(so_a):
        y = next((y for y in sorted(so_b) if _so_a_letra_de_serie(x, y)), None)
        if y:
            comum, so_a, so_b = comum | {x, y}, so_a - {x}, so_b - {y}
    return EmComum(frozenset(comum), frozenset(so_a), frozenset(so_b))


def partes_em_comum(a: str, b: str) -> EmComum:
    """Como `em_comum`, com letras e números separados: serve para medir o quanto dois textos se parecem."""
    return EmComum(*map(frozenset, _comparar(partes(a), partes(b))))


def _comparar(fa: list[str], fb: list[str]) -> tuple[set[str], set[str], set[str]]:
    """(em comum, só de a, só de b), aceitando escrita junta e erro de digitação numa palavra."""
    ca, cb = colar(fa, set(fb)), colar(fb, set(fa))
    comum, so_a, so_b = ca & cb, ca - cb, cb - ca
    for x in sorted(so_a):
        y = next((y for y in sorted(so_b) if mesma_palavra(x, y)), None)
        if y:
            comum, so_a, so_b = comum | {x}, so_a - {x}, so_b - {y}
    return comum, so_a, so_b


def _so_a_letra_de_serie(x: str, y: str) -> bool:
    """'X450' × '450', 'ZK310' × '310': uma ou duas letras na frente do mesmo número, de 3 dígitos ou mais."""
    com_letras, numero = (x, y) if y.isdigit() else (y, x)
    achado = SERIE.fullmatch(com_letras)
    return bool(achado) and numero.isdigit() and len(numero) >= 3 and _numero(achado.group(2)) == numero
