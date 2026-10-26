"""Endereço do consignatário: a mesma empresa em endereços diferentes entre os documentos vira aviso."""

from tests.comparacao.apoio import campo, doc, rodar

CNPJ = "11.222.333/0001-44"
ANTIGO = "Av. Almirante Tamandare, 1200 - Sala 5, Centro, Vila Serena - SC 88000-100"
NOVO = "Rua Doutor Jose Bonifacio, 77.Sala 301, Centro, Vila Serena - SC 88000-200"
NOVO_SEM_TITULO = "R Jose Bonifacio 77 Sala 900 Vila Serena SC 88000-200 BRAZIL"


def _rodar(end_invoice, end_pl, end_bl=None, cnpj_pl=CNPJ, nome_pl="Mar Azul Comercio Ltda"):
    return rodar(
        [doc("invoice", 90, 100, numero="F1", consignatario=("Mar Azul Comercio Ltda", CNPJ, end_invoice)),
         doc("packing_list", 90, 100, numero="F1", consignatario=(nome_pl, cnpj_pl, end_pl))],
        [doc("conhecimento", 90, 100, subtipo="BL",
             consignatario=("MAR AZUL COMERCIO LTDA", CNPJ, end_bl or end_pl))],
    )


def _do_endereco(r):
    return [a for a in r.avisos if a.startswith("Endereço do consignatário")]


def test_mesmo_cnpj_com_outra_rua_e_aviso_e_nao_divergencia():
    r = _rodar(ANTIGO, NOVO)
    assert _do_endereco(r) == [f"Endereço do consignatário diferente entre os documentos: Invoice {ANTIGO} × "
                               f"Packing List/BL {NOVO} (confira se é endereço antigo)"]
    assert campo(r.comparacoes[0], "consignatario").status == "OK"
    assert not any("Endereço do consignatário" in d.mensagem for d in r.divergencias)


def test_titulo_na_rua_numero_colado_e_sala_diferente_passam():
    assert _do_endereco(_rodar(NOVO, NOVO_SEM_TITULO, end_bl=NOVO)) == []


def test_outro_numero_na_mesma_rua_avisa():
    assert len(_do_endereco(_rodar(NOVO, NOVO.replace("77", "79"), end_bl=NOVO))) == 1


def test_outra_empresa_nao_confere_endereco():
    r = _rodar(ANTIGO, NOVO, end_bl=ANTIGO, cnpj_pl="99.888.777/0001-66", nome_pl="Serra Verde Industria Ltda")
    assert _do_endereco(r) == []


def test_resultado_nao_depende_da_ordem_dos_documentos():
    a = rodar([doc("invoice", numero="F1", consignatario=("Mar Azul Ltda", CNPJ, ANTIGO))],
              [doc("conhecimento", subtipo="BL", consignatario=("Mar Azul Ltda", CNPJ, NOVO))])
    b = rodar([doc("conhecimento", subtipo="BL", consignatario=("Mar Azul Ltda", CNPJ, NOVO))],
              [doc("invoice", numero="F1", consignatario=("Mar Azul Ltda", CNPJ, ANTIGO))])
    assert _do_endereco(a) == _do_endereco(b) and len(_do_endereco(a)) == 1


def test_andar_depois_do_numero_e_abreviacoes_coladas_passam():
    variantes = ["R.DR.JOSE BONIFACIO, 77 - CENTRO, VILA SERENA SC, 88000-200",
                 "RUA DR.JOSE BONIFACIO 77-9 ANDAR -CENTRO VILA SERENA-SC-CEP88000.200",
                 "R DOUTOR JOSEBONIFACIO,77, 9 ANDAR CENTRO VILA SERENA SC",
                 "JOSE BONIFACIO, N 77 -9 ANDAR - VILA SERENA/ SC"]
    for variante in variantes:
        assert _do_endereco(_rodar(NOVO, variante, end_bl=NOVO)) == [], variante


def test_sala_antes_do_numero_ou_antes_da_rua_passa():
    variantes = ["SALA 301 A 303 RUA DOUTOR JOSE BONIFACIO 77 VILA SERENA - SC 88000-200",
                 "R DOUTOR JOSE BONIFACIO SALA 301 302 E 303 AN 77 CENTRO 88000200 VILA SERENA SC"]
    for variante in variantes:
        assert _do_endereco(_rodar(NOVO, variante, end_bl=NOVO)) == [], variante


def test_sala_antes_de_outro_numero_avisa():
    variante = "R DOUTOR JOSE BONIFACIO SALA 301 302 E 303 AN 79 CENTRO 88000200 VILA SERENA SC"
    assert len(_do_endereco(_rodar(NOVO, variante, end_bl=NOVO))) == 1


def test_rua_que_contem_a_outra_continua_outra_rua():
    r = _rodar("Rua das Palmeiras, 77, Vila Serena - SC", "Rua Nova das Palmeiras, 77, Vila Serena - SC")
    assert len(_do_endereco(r)) == 1
