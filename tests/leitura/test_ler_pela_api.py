"""Cálculo de custo com cache de prompt (sem chamar a API)."""

from types import SimpleNamespace

import pytest

from app.services.leitura.ler_pela_api import _uso


def resposta(modelo, entrada, gravados, lidos, saida):
    usage = SimpleNamespace(
        input_tokens=entrada, cache_creation_input_tokens=gravados, cache_read_input_tokens=lidos, output_tokens=saida
    )
    return SimpleNamespace(model=modelo, usage=usage)


def test_custo_sem_cache():
    _, _, custo = _uso(resposta("claude-opus-5-5", 1_000_000, 0, 0, 0))
    assert custo == pytest.approx(4.0)


def test_custo_gravacao_e_leitura_do_cache_opus():
    entrada, saida, custo = _uso(resposta("claude-opus-5-5", 0, 1_000_000, 1_000_000, 1_000_000))
    assert entrada == 2_000_000 and saida == 1_000_000
    assert custo == pytest.approx(4.0 * 1.25 + 0.20 + 20.0)


def test_custo_leitura_do_cache_sonnet():
    _, _, custo = _uso(resposta("claude-sonnet-5-5", 0, 0, 1_000_000, 0))
    assert custo == pytest.approx(0.20)


class _StreamFalso:
    def __init__(self, final):
        self.final = final

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get_final_message(self):
        return self.final


def test_leitura_usa_streaming_com_limite_de_saida_alto():
    from app.services.leitura import ler_pela_api

    chamadas = []
    final = SimpleNamespace(stop_reason="end_turn")

    def stream(**parametros):
        chamadas.append(parametros)
        return _StreamFalso(final)

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))
    arquivo = SimpleNamespace(nome="INV.xlsx")
    assert ler_pela_api._chamar(client, arquivo, [{"type": "text", "text": "x"}]) is final
    assert chamadas[0]["max_tokens"] == ler_pela_api.MAX_TOKENS > 16000
