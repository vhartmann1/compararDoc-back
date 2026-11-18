"""Contradição entre duas descrições: as duas dizem a mesma coisa com valor diferente."""

import pytest

from app.services.comparacao.campos.itens.contradicao_na_descricao import Contradicao, contradicao


@pytest.mark.parametrize(
    ("a", "b", "esperado"),
    [
        ("FONTE 12V 150W", "FONTE 12V 120W", Contradicao("150 W", "120 W")),
        ("CABO 1,5 MM", "CABO 2.5MM", Contradicao("1,5 MM", "2,5 MM")),
        ("PLACA ANODIZED", "PLACA NOT ANODIZED", Contradicao("ANODIZED", "NOT ANODIZED")),
        ("CORREIA WITH GREASE", "CORREIA WITHOUT GREASE", Contradicao("GREASE", "WITHOUT GREASE")),
        ("BARRA SEM COSTURA", "BARRA COM COSTURA", Contradicao("SEM COSTURA", "COSTURA")),
        ("BOBINA GRADE 430", "BOBINA GRADE 304", Contradicao("GRADE 430", "GRADE 304")),
        ('PRATO 14"', "PRATO 15''", Contradicao('14"', '15"')),
        ("SENSOR TS100", "SENSOR TS200", Contradicao("TS100", "TS200", um_caractere=True)),
    ],
)
def test_contradicoes(a, b, esperado):
    assert contradicao(a, b) == esperado
    assert contradicao(b, a) == Contradicao(esperado.de_b, esperado.de_a, esperado.um_caractere)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("FONTE 12V 150 W", "FONTE 150W"),  # medida que só um lado traz
        ("FONTE 24 V 200 W", "FONTE 200 W"),  # o número da medida não é atributo da palavra antes dele
        ("CABO 1,5 MM", "CABO 1.5MM"),
        ('PRATO 14"', "PRATO 14 INCH"),
        ("NON WOVEN FABRIC", "NONWOVEN FABRIC"),
        ("PLACA NOT ANODIZED", "PLACA NOT ANODIZED 3MM"),
        ("BOBINA GRADE 430 GRADE 304", "BOBINA GRADE 304 GRADE 430"),
        ("BOMBA MODELO 100 220V", "BOMBA 220V MODELO 100"),
        ("SENSOR V750", "SENSOR 750"),  # só a letra de série na frente
    ],
)
def test_sem_contradicao(a, b):
    assert contradicao(a, b) is None
