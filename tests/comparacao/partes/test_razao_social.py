"""Os dois normalizadores de razão social: o nome inteiro e as palavras que distinguem."""

from app.services.comparacao.partes.razao_social import (
    nomes_equivalentes,
    normalizar_nome_empresa,
    palavras_distintivas,
)


def test_nome_empresa():
    assert normalizar_nome_empresa("Capital Trade Importação e Exportação Ltda.") == "CAPITAL TRADE"
    assert normalizar_nome_empresa("SERRANA POLÍMEROS S.A.S.") == "SERRANA POLIMEROS"
    assert nomes_equivalentes("Aurora Silk Co.", "AURORA SILK CO.")
    assert nomes_equivalentes("CAPITAL TRADE IMPORTACAO EEXPORTACAO LTDA", "Capital Trade Importação e Exportação Ltda.")
    assert nomes_equivalentes("Delta Fast-Run Footwear Ltd.", "DELTA FAST RUN FOOTWEAR LIMITED")
    assert not nomes_equivalentes("Orion Pacific Trading Co., Ltd.", "Delta Fast-Run Footwear Ltd.")
    assert not nomes_equivalentes("Capital Trade", "Plastnorte Distribuidora de Resinas")


def test_palavra_a_palavra_mantem_artigos_e_ramo():
    assert normalizar_nome_empresa("The Lumen Importação Ltda") == "LUMEN"
    assert palavras_distintivas("The Lumen Importação Ltda") == ("THE", "LUMEN", "IMPORTACAO")
    assert palavras_distintivas("Serra K0rn GmbH") == palavras_distintivas("SERRA KORNGMBH") == ("SERRA", "KORN")
