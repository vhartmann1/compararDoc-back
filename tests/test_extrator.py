"""Cálculo de custo com cache de prompt (sem chamar a API)."""

from types import SimpleNamespace

import pytest

from app.services.extrator import _uso


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
