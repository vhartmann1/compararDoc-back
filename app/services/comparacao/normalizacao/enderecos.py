"""Mesmo endereço entre documentos: por texto parecido (exportador) ou por rua e número (cliente)."""

import difflib
import re

from app.schemas import Parte
from app.services.comparacao.normalizacao.paises import PAISES, SIGLAS_PAISES
from app.services.comparacao.normalizacao.texto import sem_acento, so_letras_numeros

SIMILARIDADE_MINIMA_ENDERECO = 0.80  # por texto parecido

# Por rua e número. Tipo de logradouro e marca de número: não distinguem uma rua da outra.
TIPOS_DE_LOGRADOURO = {"R", "RUA", "AV", "AVENIDA", "ROD", "RODOVIA", "ESTRADA", "ESTR", "AL", "ALAMEDA", "TRAVESSA",
                       "TV", "N", "NO", "NR", "NUMERO", "DE", "DA", "DO", "DAS", "DOS", "E"}
CONECTIVOS = {"N", "NO", "NR", "NUMERO", "DE", "DA", "DO", "DAS", "DOS", "E"}
# Partes do prédio que podem vir entre a rua e o número ('R X Sala 901 902 Andar 9 333').
PARTES_DO_PREDIO = {"SALA", "SALAS", "SL", "ANDAR", "AN", "CONJ", "CONJUNTO", "LOJA", "BLOCO", "BOX", "APTO", "AP",
                    "ED", "EDIFICIO"}
# Título na frente do nome da rua, que um documento escreve e outro não ('R. Doutor X' = 'R. X').
TITULOS = {"DOUTOR", "DR", "CORONEL", "CEL", "PROFESSOR", "PROF", "ENGENHEIRO", "ENG", "GOVERNADOR", "GOV",
           "PRESIDENTE", "PRES", "GENERAL", "GAL", "MAJOR", "CAPITAO", "MARECHAL", "SENADOR", "DEPUTADO", "PREFEITO"}
UNIDADES = ("", "UM", "DOIS", "TRES", "QUATRO", "CINCO", "SEIS", "SETE", "OITO", "NOVE", "DEZ", "ONZE", "DOZE",
            "TREZE", "QUATORZE", "QUINZE", "DEZESSEIS", "DEZESSETE", "DEZOITO", "DEZENOVE")
DEZENAS = {20: "VINTE", 30: "TRINTA"}
# a cidade antes da UF no fim do texto: 'Bairro X, Cidade Alta - SC 88000-100 BR' -> 'Cidade Alta'
CEP = re.compile(r"\b\d{2}\.?\d{3}-?\d{3}\b")
PEDACO = re.compile(r"[A-Z0-9]+|[,;.\-–/]")  # palavras e a pontuação que separa os trechos do endereço
MARCAS_DE_NUMERO = {"N", "NO", "NR", "NUMERO"}
CIDADE_ANTES_DA_UF = re.compile(r"([A-Za-z .]+?)\s*[-,/]?\s*\b[A-Z]{2}\b[\s,\-0-9.]*(?i:BRASIL|BRAZIL|BR)?[\s.,]*$")


def normalizar_endereco(endereco: str) -> str:
    return so_letras_numeros(endereco.replace(".", ""))


def palavras_do_endereco(endereco: str) -> set[str]:
    """Palavras do endereço, com o país pela sigla ('THE NETHERLANDS' e 'NL' viram 'NL')."""
    return set(_palavras_em_ordem(endereco)) - {"THE"}


def _palavras_em_ordem(endereco: str) -> list[str]:
    texto = f" {normalizar_endereco(endereco)} "
    for nome in sorted(PAISES, key=len, reverse=True):
        texto = texto.replace(f" {nome} ", f" {PAISES[nome]} ")
    return texto.split()


def _pais_no_fim(endereco: str) -> set[str]:
    """Sigla do país na última palavra que não é CEP: 'MONTEVIDEO URUGUAY 11000' -> {'UY'}; no meio não conta."""
    palavras = [p for p in _palavras_em_ordem(endereco) if not re.fullmatch(r"\d{4,}", p)]
    return {palavras[-1]} if palavras and palavras[-1] in SIGLAS_PAISES else set()


def enderecos_equivalentes(a: str, b: str) -> bool:
    """Texto parecido na mesma ordem, as mesmas palavras em outra ordem, ou um é o outro com mais detalhe."""
    na, nb = normalizar_endereco(a), normalizar_endereco(b)
    if difflib.SequenceMatcher(None, na, nb).ratio() >= SIMILARIDADE_MINIMA_ENDERECO:
        return True
    pa, pb = palavras_do_endereco(a), palavras_do_endereco(b)
    pa, pb = _sem_abreviacoes(pa, pb), _sem_abreviacoes(pb, pa)
    if pa | pb and len(pa & pb) / len(pa | pb) >= SIMILARIDADE_MINIMA_ENDERECO:
        return True
    return _contido_com_mais_detalhe(pa - _pais_no_fim(a), pb) or _contido_com_mais_detalhe(pb - _pais_no_fim(b), pa)


def _sem_abreviacoes(palavras: set[str], outras: set[str]) -> set[str]:
    """'ON' vira 'ONTARIO' se o outro endereço traz 'ONTARIO': sigla de estado/província é o começo do nome."""
    def completa(p: str) -> str:
        if p in outras or not p.isalpha() or len(p) < 2:
            return p
        return next((o for o in sorted(outras) if o.startswith(p) and o.isalpha()), p)
    return {completa(p) for p in palavras}


def _contido_com_mais_detalhe(curto: set[str], longo: set[str]) -> bool:
    """'NO 88 LIANHUA ROAD SHANGHAI 201100' ⊂ '2F NO 88 LIANHUA ROAD MINHANG DISTRICT SHANGHAI', fora o CEP."""
    essencial = {p for p in curto if not re.fullmatch(r"\d{5,}", p)}
    return len(essencial) >= 3 and any(ch.isdigit() for p in essencial for ch in p) and essencial <= longo


def normalizar_cidade(cidade: str) -> str:
    """'Gyeonggi-do' -> 'GYEONGGIDO'; 'Bogotá, D.C.' -> 'BOGOTADC'."""
    return re.sub(r"[^A-Z0-9]", "", sem_acento(cidade).upper())


def _cidades_compativeis(cidade_a: str, endereco_a: str, cidade_b: str, endereco_b: str) -> bool:
    """Mesma cidade, uma contida na outra, ou a cidade de um aparece no endereço do outro."""
    ca, cb = normalizar_cidade(cidade_a), normalizar_cidade(cidade_b)
    if not ca or not cb or ca in cb or cb in ca:
        return True
    return ca in normalizar_cidade(endereco_b) or cb in normalizar_cidade(endereco_a)


def enderecos_de_texto_parecido(a: tuple[str, str | None], b: tuple[str, str | None]) -> bool:
    """(endereço, cidade): cidades diferentes => divergem, mesmo com texto parecido; senão similaridade."""
    (texto_a, cidade_a), (texto_b, cidade_b) = a, b
    if cidade_a and cidade_b and not _cidades_compativeis(cidade_a, texto_a, cidade_b, texto_b):
        return False
    return enderecos_equivalentes(texto_a, texto_b)


def mesma_rua_e_numero(a: Parte, b: Parte) -> bool:
    """Mesma cidade e texto igual ou mesma rua e número; sem rua ou número reconhecível, não acusa."""
    if not _mesma_cidade_da_parte(a, b):
        return False
    if normalizar_endereco(a.endereco or "") == normalizar_endereco(b.endereco or ""):
        return True
    la, lb = _logradouro(a.endereco or ""), _logradouro(b.endereco or "")
    if la is None or lb is None or la == lb:
        return True
    return _traz_logradouro(a.endereco or "", lb) or _traz_logradouro(b.endereco or "", la)


def _traz_logradouro(endereco: str, logradouro: tuple[str, str]) -> bool:
    """O endereço tem a rua e, logo depois ou depois da sala/andar, o número ('Sala 9 Rua X 77', 'R X Sala 9 77')."""
    palavras = [p for p, _ in _palavras_e_pausas(endereco)]
    rua, numero = logradouro
    for inicio in (i for i in range(len(palavras)) if _comeco_de_rua(palavras, i)):
        fim = _fim_da_rua(palavras, inicio, rua)
        resto = [p.lstrip("0") for p in palavras[fim:]] if fim is not None else []
        if resto and (resto[0] == numero or (palavras[fim] in PARTES_DO_PREDIO and numero in resto)):
            return True
    return False


def _comeco_de_rua(palavras: list[str], i: int) -> bool:
    """Palavra que abre o nome da rua: no começo ou logo depois do tipo ('Rua', 'Av.') ou do título."""
    if palavras[i] in TIPOS_DE_LOGRADOURO or palavras[i] in TITULOS:
        return False
    anterior = next((p for p in reversed(palavras[:i]) if p not in CONECTIVOS), None)
    return anterior is None or anterior in TITULOS or anterior in TIPOS_DE_LOGRADOURO


def _mesma_cidade_da_parte(a: Parte, b: Parte) -> bool:
    """Sem cidade num dos lados passa; com as duas, iguais ou a de um escrita no endereço do outro."""
    ca, cb = _cidade(a), _cidade(b)
    if not ca or not cb:
        return True
    return ca == cb or ca in normalizar_cidade(b.endereco or "") or cb in normalizar_cidade(a.endereco or "")


def _cidade(p: Parte) -> str | None:
    """A cidade do campo; sem ela, a que vem antes da UF no fim do texto do endereço."""
    if p.cidade and p.cidade.strip():
        return normalizar_cidade(p.cidade)
    achado = CIDADE_ANTES_DA_UF.search(sem_acento(p.endereco or ""))
    return normalizar_cidade(achado.group(1)) if achado and achado.group(1).strip() else None


def _logradouro(endereco: str) -> tuple[str, str] | None:
    """'R. 7 de Setembro, 644 - Sala 5' -> ('SETESETEMBRO', '644'); None sem rua ou número."""
    palavras = _palavras_e_pausas(endereco)
    n = next((i for i in range(len(palavras)) if _numero_da_casa(palavras, i)), None)
    if n is None:
        return None
    rua = [w for p, _ in palavras[:n] for w in _por_extenso(p).split() if w not in TIPOS_DE_LOGRADOURO]
    while len(rua) > 1 and rua[0] in TITULOS:
        rua.pop(0)
    return ("".join(rua), palavras[n][0].lstrip("0")) if rua else None  # junto: 'PEDROFERREIRA' é a mesma rua


def _fim_da_rua(palavras: list[str], inicio: int, rua: str) -> int | None:
    """Posição logo depois da rua, se as palavras a partir de `inicio` formam exatamente `rua`."""
    juntas = ""
    for j in range(inicio, len(palavras)):
        juntas += "".join(w for w in _por_extenso(palavras[j]).split() if w not in TIPOS_DE_LOGRADOURO)
        if juntas == rua:
            return j + 1
        if not rua.startswith(juntas):
            return None
    return None


def _palavras_e_pausas(endereco: str) -> list[tuple[str, bool]]:
    """Cada palavra e se vem uma pontuação logo depois dela ('333, 9 ANDAR': 333 fecha o trecho)."""
    pedacos = PEDACO.findall(sem_acento(CEP.sub(" ", endereco)).upper())
    return [(p, i + 1 < len(pedacos) and not pedacos[i + 1].isalnum()) for i, p in enumerate(pedacos) if p.isalnum()]


def _depois_de_pausa(palavras: list[tuple[str, bool]], i: int) -> bool:
    """Número depois de vírgula ou de 'Nº': é o da casa, mesmo seguido de outro ('333, 9 andar')."""
    return i > 0 and (palavras[i - 1][1] or palavras[i - 1][0] in MARCAS_DE_NUMERO)


def _numero_da_casa(palavras: list[tuple[str, bool]], i: int) -> bool:
    """Número depois do nome da rua que não é parte dele ('7 de Setembro', 'BR 101 950'); pontuação fecha o trecho."""
    palavra, pausa = palavras[i]
    if not palavra.isdigit() or not any(p not in TIPOS_DE_LOGRADOURO for p, _ in palavras[:i]):
        return False
    seguinte = palavras[i + 1][0] if i + 1 < len(palavras) else ""
    return pausa or _depois_de_pausa(palavras, i) or not (seguinte.isdigit() or seguinte in {"DE", "DO", "DA"})


def _por_extenso(palavra: str) -> str:
    """'7' -> 'SETE', '25' -> 'VINTE E CINCO' (até 31); o resto fica como está."""
    if not palavra.isdigit() or not 0 < int(palavra) < 32:
        return palavra
    n = int(palavra)
    if n < 20:
        return UNIDADES[n]
    return " E ".join(filter(None, (DEZENAS[n // 10 * 10], UNIDADES[n % 10])))
