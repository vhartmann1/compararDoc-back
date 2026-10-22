"""Adquirente/notify do conhecimento × adquirente da invoice: CNPJ e endereço."""

from tests.comparacao.apoio import campo, doc, rodar
from tests.comparacao.cenarios import CAPITAL

ENDERECO = "Rua das Palmeiras 410, Sala 3, Bairro Jardim, Cidade Alta - SC"
CLIENTE = ("Vela Azul Comercio de Pecas Ltda", "22.333.444/0001-55", ENDERECO)


def _rodar(adquirente=None, notify=None, subtipo="BL"):
    return rodar(
        [doc("invoice", numero="1", consignatario=CAPITAL, adquirente=CLIENTE),
         doc("packing_list", numero="1", consignatario=CAPITAL, adquirente=CLIENTE)],
        [doc("conhecimento", subtipo=subtipo, consignatario=CAPITAL, adquirente=adquirente, notify=notify)],
    )


def _do_adquirente(r):
    novas = [d for d in r.divergencias if d.campo == "adquirente"]
    assert all(d.comparacao_id == "unica" for d in novas)
    return [d.mensagem for d in novas]


def test_cnpj_do_adquirente_diferente_no_bl_e_erro():
    r = _rodar(adquirente=("Vela Azul Comercio de Pecas Eireli", "22.333.484/0001-55", ENDERECO))
    mensagens = _do_adquirente(r)
    assert len(mensagens) == 1 and "CNPJ" in mensagens[0] and "22.333.484/0001-55" in mensagens[0]


def test_mesmo_cnpj_com_outro_endereco_no_notify_do_awb_e_erro():
    outro = "Avenida Beira Mar 9, Terreo, Bairro Praia, Cidade Baixa - SC"
    r = _rodar(notify=("Vela Azul Comercio de Pecas Ltda.", "22333444000155", outro), subtipo="AWB")
    mensagens = _do_adquirente(r)
    assert len(mensagens) == 1 and "Endereço" in mensagens[0] and "Avenida Beira Mar" in mensagens[0]


def test_mesmo_cnpj_e_mesmo_endereco_passa():
    r = _rodar(notify=("VELA AZUL COMERCIO DE PECAS LTDA", "22.333.444/0001-55", ENDERECO.upper()))
    assert _do_adquirente(r) == []


def test_notify_capital_ou_de_outra_empresa_nao_compara_cnpj():
    assert _do_adquirente(_rodar(notify=CAPITAL)) == []
    r = _rodar(notify=("Gaivota Logistica Integrada Ltda", "55.666.777/0001-88", "Rua Um 1, Centro, Vila Nova"))
    assert _do_adquirente(r) == []


def test_sem_cnpj_ou_endereco_num_dos_lados_nao_compara():
    assert _do_adquirente(_rodar(adquirente=("Vela Azul Comercio de Pecas Ltda", None, None))) == []


def test_mesma_rua_e_numero_escritos_de_outro_jeito_passa():
    invoice = "ROD. BR-101, 950 - SALA 2 - MODULO 3, CP: 0, Cidade Alta, SC"
    bl = "RODOVIA BR-101 950-MODULO 3,SALA 2-BAIRRO NOVO, CIDADE ALTA-SC, BRASIL"
    cliente = (CLIENTE[0], CLIENTE[1], invoice)
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL, adquirente=cliente)],
              [doc("conhecimento", subtipo="CRT", consignatario=CAPITAL, adquirente=(CLIENTE[0], CLIENTE[1], bl))])
    assert _do_adquirente(r) == []


def test_rua_de_nome_parecido_com_o_mesmo_numero_e_erro():
    r = _rodar(adquirente=(CLIENTE[0], CLIENTE[1], "RUA DAS PALMARES, 410 JARDIM, CIDADE ALTA SC 88000-100 BR"))
    assert len(_do_adquirente(r)) == 1


def test_linha_do_adquirente_na_comparacao():
    assert campo(_rodar(adquirente=CLIENTE).comparacoes[0], "adquirente").status == "OK"
    errado = _rodar(adquirente=(CLIENTE[0], "22.333.484/0001-55", ENDERECO)).comparacoes[0]
    linha = campo(errado, "adquirente")
    assert linha.status == "DIVERGENTE" and "22.333.484/0001-55" in linha.valores["conhecimento"].exibicao
    assert "22.333.444/0001-55" in linha.valores["invoice"].exibicao


def test_endereco_do_adquirente_exige_mesmo_numero_e_aceita_outra_sala():
    def com(endereco):
        return _do_adquirente(_rodar(adquirente=(CLIENTE[0], CLIENTE[1], endereco)))
    assert com("Rua das Palmeiras 410, Sala 9, Bairro Jardim, Cidade Alta - SC") == []
    assert len(com("Rua das Palmeiras 412, Sala 3, Bairro Jardim, Cidade Alta - SC")) == 1


def test_rua_contida_em_outra_nao_basta():
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL, adquirente=CLIENTE)],
              [doc("conhecimento", subtipo="BL", consignatario=CAPITAL,
                   adquirente=(CLIENTE[0], CLIENTE[1], "Rua Nova das Palmeiras, 410 - Bairro Leste"))])
    assert len(_do_adquirente(r)) == 1  # 'PALMEIRAS' está contida em 'NOVA PALMEIRAS', mas não é a mesma rua


def test_rua_com_nome_a_mais_e_outra_rua():
    cliente = (CLIENTE[0], CLIENTE[1], "Rua Ipe 100, Cidade Alta")
    r = rodar([doc("invoice", numero="1", consignatario=CAPITAL, adquirente=cliente)],
              [doc("conhecimento", subtipo="BL", consignatario=CAPITAL,
                   adquirente=(CLIENTE[0], CLIENTE[1], "R. Ipe Roxo, 100 - Cidade Alta"))])
    assert len(_do_adquirente(r)) == 1


def test_linha_mostra_o_notify_quando_o_erro_e_dele():
    r = _rodar(adquirente=CLIENTE, notify=(CLIENTE[0], "22.333.999/0001-55", ENDERECO))
    linha = campo(r.comparacoes[0], "adquirente")
    assert linha.status == "DIVERGENTE" and "22.333.999/0001-55" in linha.valores["conhecimento"].exibicao


def _par(invoice, bl):
    """Invoice e BL só com o adquirente: (endereço, cidade) de cada lado."""
    return _do_adquirente(rodar([doc("invoice", numero="1", consignatario=CAPITAL, adquirente=(*CLIENTE[:2], *invoice))],
                                [doc("conhecimento", subtipo="BL", consignatario=CAPITAL,
                                     adquirente=(*CLIENTE[:2], *bl))]))


def test_rua_com_nome_a_mais_no_mesmo_numero_e_outra_rua():
    assert len(_par(("Rua Joao 100", None), ("Rua Joao Pessoa 100", None))) == 1
    assert len(_par(("Rua Nova Palmeiras 410", None), ("Rua Palmeiras Nova 410", None))) == 1
    assert _par(("R. Joao Pessoa, 100", None), ("Rua Joao Pessoa 100 - Sala 4", None)) == []


def test_cidade_diferente_no_campo_ou_no_texto_e_erro():
    assert len(_par(("Rua Ipe 100", "Cidade Alta"), ("Rua Ipe 100", "Vila Baixa"))) == 1
    assert len(_par(("Rua Ipe 100", "Cidade Alta"), ("Rua Ipe 100, Centro, Vila Baixa - SC", None))) == 1
    assert len(_par(("Rua Ipe 100, Cidade Alta/SC", None), ("Rua Ipe 100, Vila Baixa - SC, Brasil", None))) == 1


def test_mesma_cidade_no_campo_e_no_texto_passa():
    assert _par(("Rua Ipe 100", "Cidade Alta"), ("Rua Ipe 100, Centro, Cidade Alta - SC", None)) == []
    assert _par(("Rua Ipe 100, Sala 2", "Cidade Alta"), ("Rua Ipe 100, Sala 7", None)) == []


def test_numero_no_nome_da_rua_e_sem_numero_nao_acusam():
    igual = "Rua 7 de Setembro, 644, Sala 2, Cidade Alta - SC"
    assert _par((igual, None), (igual, None)) == []
    assert _par(("Rua 7 de Setembro, 644", None), ("R. Sete de Setembro 644", None)) == []
    assert _par(("Rua das Flores s/n", None), ("Rua das Flores s/n", None)) == []
    assert _par(("Rua das Flores s/n", None), ("Rua das Flores 12", None)) == []
    assert len(_par(("Rua 7 de Setembro, 644", None), ("Rua 7 de Setembro, 646", None))) == 1
    assert len(_par(("Rua 25 de Marco 10", None), ("Rua 24 de Marco 10", None))) == 1


def test_cep_no_meio_do_endereco_nao_vira_numero_da_casa():
    com_cep = "Rua das Palmeiras 410, 89010-000 Cidade Alta, SC, Brasil"
    assert _par((com_cep, None), ("Rua das Palmeiras 410 - Cidade Alta - SC", None)) == []
    assert len(_par((com_cep, None), ("Rua das Palmeiras 412, 89.010-000 Cidade Alta, SC", None))) == 1
