"""Endereços e cidades compatíveis entre documentos."""

import difflib
import re

from app.services.comparacao.normalizacao.paises import PAISES, SIGLAS_PAISES
from app.services.comparacao.normalizacao.texto import sem_acento, so_letras_numeros

SIMILARIDADE_MINIMA_ENDERECO = 0.80


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


def cidades_compativeis(cidade_a: str, endereco_a: str, cidade_b: str, endereco_b: str) -> bool:
    """Mesma cidade, uma contida na outra, ou a cidade de um aparece no endereço do outro."""
    ca, cb = normalizar_cidade(cidade_a), normalizar_cidade(cidade_b)
    if not ca or not cb or ca in cb or cb in ca:
        return True
    return ca in normalizar_cidade(endereco_b) or cb in normalizar_cidade(endereco_a)


def enderecos_compativeis(a: tuple[str, str | None], b: tuple[str, str | None]) -> bool:
    """(endereço, cidade): cidades diferentes => divergem, mesmo com texto parecido; senão similaridade."""
    (texto_a, cidade_a), (texto_b, cidade_b) = a, b
    if cidade_a and cidade_b and not cidades_compativeis(cidade_a, texto_a, cidade_b, texto_b):
        return False
    return enderecos_equivalentes(texto_a, texto_b)
