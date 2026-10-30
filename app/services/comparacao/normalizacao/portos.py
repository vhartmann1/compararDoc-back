"""Nome do porto ou aeroporto para comparar: terminal, cidade, estado e país."""

import re
from functools import cache

from app.services.comparacao.normalizacao.paises import SIGLAS_PAISES, normalizar_pais
from app.services.comparacao.normalizacao.texto import sem_acento

PALAVRAS_PORTO = {"PORT", "PORTO", "PUERTO", "AIRPORT", "AEROPORTO", "AEROPUERTO", "OF", "DE", "DO", "DA"}


# Sufixos de UF/país depois do nome da cidade, ex.: "NAVEGANTES SC BRASIL"
SUFIXOS_LOCAL = {
    "BRASIL", "BRAZIL", "BR", "CHINA", "CN", "PRC", "COLOMBIA", "CO", "USA", "US", "INDIA", "IN",
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
    "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


# Terminal ou nome alternativo -> porto (o BL costuma citar o terminal; a invoice, a cidade)
PORTOS_EQUIVALENTES = {
    **dict.fromkeys(["XINGANG", "TIANJIN XINGANG", "XINGANG TIANJIN", "TIANJINXINGANG"], "TIANJIN"),
    **dict.fromkeys(["YANTIAN", "SHEKOU", "CHIWAN", "DA CHAN BAY"], "SHENZHEN"),
    **dict.fromkeys(["NANSHA", "HUANGPU"], "GUANGZHOU"),
    **dict.fromkeys(["YANGSHAN", "WAIGAOQIAO", "SHANGAI"], "SHANGHAI"),
    **dict.fromkeys(["BEILUN", "NINGBO ZHOUSHAN"], "NINGBO"),
    **dict.fromkeys(["TANJUNG PRIOK"], "JAKARTA"),
    **dict.fromkeys(["KELANG"], "KLANG"),  # Port Klang, Malásia
    **dict.fromkeys(["BARRA RIO"], "ITAJAI"),
    **dict.fromkeys(["GUARULHOS", "GRU"], "SAO PAULO"),  # aeroporto internacional de São Paulo
    **dict.fromkeys(["VIRACOPOS", "VCP"], "CAMPINAS"),  # aeroporto internacional de Campinas
    **dict.fromkeys(["SUVARNABHUMI", "BKK"], "BANGKOK"),  # aeroporto internacional de Bangkok
    **dict.fromkeys(["SINGAPURA"], "SINGAPORE"),
}


# Portos e aeroportos de entrada por UF: destino escrito como estado aceita qualquer um deles
PORTOS_POR_UF = {
    "SC": {"ITAJAI", "NAVEGANTES", "ITAPOA", "SAO FRANCISCO DO SUL", "IMBITUBA", "FLORIANOPOLIS", "JOINVILLE"},
    "PR": {"PARANAGUA", "ANTONINA", "CURITIBA"},
    "SP": {"SANTOS", "SAO PAULO", "CAMPINAS", "VIRACOPOS", "SAO SEBASTIAO"},
    "RJ": {"RIO DE JANEIRO", "ITAGUAI", "SEPETIBA"},
    "RS": {"RIO GRANDE", "PORTO ALEGRE"},
    "ES": {"VITORIA"},
    "MG": {"BELO HORIZONTE", "CONFINS"},
    "BA": {"SALVADOR"},
    "PE": {"SUAPE", "RECIFE"},
    "CE": {"PECEM", "FORTALEZA"},
    "AM": {"MANAUS"},
}


# São Paulo e Rio de Janeiro ficam só pela UF: o nome é também o da cidade (aeroporto, porto)
NOMES_DOS_ESTADOS = {
    "SANTA CATARINA": "SC", "PARANA": "PR", "RIO GRANDE DO SUL": "RS", "ESPIRITO SANTO": "ES",
    "MINAS GERAIS": "MG", "BAHIA": "BA", "PERNAMBUCO": "PE", "CEARA": "CE", "AMAZONAS": "AM",
}


@cache
def _estados() -> dict[str, str]:
    """Nome do estado (como `nome_do_porto` o deixa: 'RIO GRANDE SUL') ou UF -> UF."""
    return {nome_do_porto(n): uf for n, uf in NOMES_DOS_ESTADOS.items()} | {uf: uf for uf in PORTOS_POR_UF}


def porto_brasileiro(nome: str) -> bool:
    """'Itapoá - SC, Brazil' -> True; 'SHANGHAI' -> False: porto ou aeroporto de entrada conhecido no Brasil."""
    if nome_do_porto(nome) in _estados():
        return True
    porto = normalizar_porto(nome)
    return any(porto in {_sem_espacos(p) for p in portos} for portos in PORTOS_POR_UF.values())


def uf_do_porto(chave: str) -> str | None:
    """Chave de `normalizar_porto` ('ITAJAI', 'SANTACATARINA', 'SC') -> 'SC'; porto fora da lista -> None."""
    estados = {_sem_espacos(n): uf for n, uf in _estados().items()}
    portos = {normalizar_porto(p): uf for uf, nomes in PORTOS_POR_UF.items() for p in nomes}
    return estados.get(chave) or portos.get(chave)


def portos_do_estado(nome: str) -> set[str]:
    """'Santa Catarina - Brazil' -> {'SANTA CATARINA', 'ITAJAI', ...}; nome que não é estado -> vazio."""
    uf = _estados().get(nome_do_porto(nome))
    return {_sem_espacos(p) for p in (nome_do_porto(nome), *PORTOS_POR_UF[uf])} if uf else set()


# Cidades-Estado: o nome do país é também o do porto
PORTOS_COM_NOME_DE_PAIS = {"SINGAPORE", "HONGKONG"}


def so_o_pais(nome: str) -> bool:
    """'To: Brazil' nomeia o país, não o porto; 'SINGAPORE' é país e porto."""
    return normalizar_pais(nome) in SIGLAS_PAISES and normalizar_porto(nome) not in PORTOS_COM_NOME_DE_PAIS


def normalizar_porto(nome: str) -> str:
    """Nome do porto para comparar, sem espaços: 'XINGANG' -> 'TIANJIN'; 'HO CHI MINH' -> 'HOCHIMINH'."""
    porto = nome_do_porto(nome)
    return _sem_espacos(PORTOS_EQUIVALENTES.get(porto, porto))


def _sem_espacos(nome: str) -> str:
    return nome.replace(" ", "")


def nome_do_porto(nome: str) -> str:
    """Nome do porto como o documento escreve, sem rótulo e sem país: 'Port of Navegantes - SC, Brazil' -> 'NAVEGANTES'."""
    texto = sem_acento(nome).upper()
    texto = re.sub(r"\(.*?\)", " ", texto)  # 'SHEKOU (CHINA)'
    texto = re.split(r",|/| - ", texto)[0]  # 'NAVEGANTES, SC' / 'NAVEGANTES - SC'
    palavras = [p for p in re.sub(r"[^A-Z0-9 ]", " ", texto).split() if p not in PALAVRAS_PORTO]
    while len(palavras) > 1 and palavras[-1] in SUFIXOS_LOCAL:
        palavras.pop()
    return " ".join(palavras)
