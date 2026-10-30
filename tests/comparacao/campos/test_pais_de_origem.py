"""País de origem: lista com outro separador e código ISO conferem; país a mais ou trocado diverge."""

from app.services.comparacao.normalizacao.enderecos import enderecos_equivalentes
from tests.comparacao.apoio import campo, doc, rodar


def _origem(invoice, pl):
    r = rodar([doc("invoice", numero="A1", pais_origem=invoice), doc("packing_list", refs=["A1"], pais_origem=pl)])
    return campo(r.comparacoes[0], "pais_origem").status


def test_lista_de_paises_com_hifen_confere_com_barra():
    assert _origem("CHINA / THAILAND / JAPAN", "CHINA - TAILANDIA - JAPAN") == "OK"


def test_codigo_iso_confere_com_o_nome_do_pais():
    assert _origem("AUSTRIA", "AT") == "OK"
    assert _origem("SWITZERLAND", "CH") == "OK"


def test_pais_a_mais_ou_trocado_diverge():
    assert _origem("CHINA / THAILAND", "CHINA - THAILAND - VIETNAM") == "DIVERGENTE"
    assert _origem("AUSTRIA", "AU") == "DIVERGENTE"
    assert _origem("AUSTRIA", "GERMANY") == "DIVERGENTE"


def test_codigo_de_pais_no_meio_do_endereco_continua_contando():
    pares = (("UNIT 5 BLOCK CA 88 RIVER ROAD", "UNIT 5 BLOCK CB 88 RIVER ROAD DISTRICT 9 CITY"),
             ("88 SE RIVER ROAD", "88 RIVER ROAD WEST"),
             ("88 RIVER ROAD SE 12", "88 RIVER ROAD 12 NORTH BUILDING"))
    for a, b in pares:
        assert not enderecos_equivalentes(a, b), (a, b)


def test_pais_no_fim_do_endereco_pode_faltar_do_outro_lado():
    assert enderecos_equivalentes("KM 9 AVENIDA AZUL PREDIO 12 VILAREJO URUGUAY", "AVENIDA AZUL KM 9 PREDIO 12 VILAREJO")
