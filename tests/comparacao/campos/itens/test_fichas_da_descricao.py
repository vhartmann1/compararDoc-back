"""Fichas de uma descrição numa notação só e o que duas descrições têm em comum."""

from app.services.comparacao.campos.itens.fichas_da_descricao import (
    colar,
    em_comum,
    fichas,
    mesma_palavra,
    partes,
    polegadas,
    quase_iguais,
)


def test_fichas_numa_notacao_so():
    assert fichas('Sino 06" Q-40 0.700x1100.000 5pack') == ["SINO", "6", "Q", "40", "0.7", "1100", "5", "PACK"]
    assert fichas("Valvula .700 MM x 1100 MM") == ["VALVULA", "0.7", "1100", "MM"]
    assert fichas("Lote 12345678901") == ["LOTE", "12345678901"]  # número comprido é código, fica como está


def test_partes_separam_letras_de_numeros():
    assert partes("Bomba V750") == ["BOMBA", "V", "750"]


def test_polegadas_em_qualquer_marca():
    assert polegadas("Prato 14'' 15\" 16 inch 17 INCHES") == {14.0, 15.0, 16.0, 17.0}


def test_colar_o_que_o_outro_escreve_junto():
    assert colar(["SINO", "HI", "HAT"], {"SINO", "HIHAT"}) == {"SINO", "HIHAT"}
    assert colar(["99", "7"], {"99.7"}) == {"99.7"}  # vírgula decimal de um lado, ponto do outro


def test_mesma_palavra_so_em_palavra_de_quatro_letras_ou_mais():
    assert mesma_palavra("KITS", "KIT") and mesma_palavra("TAMBORINE", "TAMBOURINE")
    assert not mesma_palavra("RED", "BED") and not mesma_palavra("K40", "K41")


def test_quase_iguais_em_identificador_mas_nunca_so_a_letra_de_serie():
    assert quase_iguais("TS100", "TS200") and quase_iguais("735", "7358") and quase_iguais("K4", "K40")
    assert not quase_iguais("V750", "750") and not quase_iguais("2480N", "2480")
    assert not quase_iguais("12", "13")  # curto demais para dizer que é o mesmo identificador


def test_em_comum_aceita_a_sigla_da_serie_na_frente():
    comum = em_comum("Roda guia - Modelo: 550", "Roda guia RX550")
    assert comum.so_b == frozenset() and comum.codigo_em_comum and comum.cobertura == 1.0


def test_codigo_curto_nao_esta_dentro_do_comprido():
    comum = em_comum("Sensor TS1", "Sensor TS100-01")
    assert "TS1" in comum.so_a and "TS100" in comum.so_b


def test_so_palavras_de_ligacao_em_comum_nao_distinguem():
    assert not em_comum("the and for", "the and for cable").algo_distintivo
    assert em_comum("cable usb", "cable hdmi").algo_distintivo
