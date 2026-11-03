"""Portos: documentos comerciais conferem com a descarga ou a entrega do conhecimento; grafias e aeroportos."""

from tests.comparacao.apoio import campo, doc, rodar


def _destino(invoice, pl, descarga, entrega):
    return _rodar_destino(invoice, pl, descarga, entrega)[0]


def _rodar_destino(invoice, pl, descarga, entrega):
    r = rodar(
        [doc("invoice", 100, 110, numero="A1", destino=invoice), doc("packing_list", 100, 110, refs=["A1"], destino=pl)],
        [doc("conhecimento", 100, 110, subtipo="BL", numero="BL1", refs=["A1"], destino=descarga, entrega=entrega)],
    )
    return campo(r.comparacoes[0], "porto_destino").status, [a for a in r.avisos if "os dois aparecem" in a]


def test_invoice_com_a_entrega_e_pl_com_a_descarga_conferem():
    status, avisos = _rodar_destino("Azulmar", "Verdemar", "Verdemar", "Azulmar")
    assert status == "OK"
    assert avisos == ["Porto de destino: A invoice diz AZULMAR e o packing list diz VERDEMAR; "
                      "os dois aparecem no BL: VERDEMAR (entrega: AZULMAR)."]
    assert _destino("Verdemar", "Azulmar", "Verdemar", "Azulmar") == "OK"


def test_invoice_e_pl_com_o_mesmo_porto_nao_avisam():
    status, avisos = _rodar_destino("Azulmar", "Azulmar", "Verdemar", "Azulmar")
    assert status == "OK" and not avisos


def test_documento_com_porto_fora_da_descarga_e_da_entrega_diverge():
    assert _destino("Rubromar", "Verdemar", "Verdemar", "Azulmar") == "DIVERGENTE"
    assert _destino("Rubromar", "Rubromar", "Verdemar", "Azulmar") == "DIVERGENTE"


def test_sem_conhecimento_invoice_e_pl_com_portos_diferentes_divergem():
    r = rodar([doc("invoice", numero="A1", destino="Azulmar"), doc("packing_list", refs=["A1"], destino="Verdemar")])
    assert campo(r.comparacoes[0], "porto_destino").status == "DIVERGENTE"


def _origem(comercial, conhecimento, subtipo="BL"):
    r = rodar(
        [doc("invoice", numero="A1", origem=comercial), doc("packing_list", refs=["A1"], origem=comercial)],
        [doc("conhecimento", subtipo=subtipo, numero="C1", refs=["A1"], origem=conhecimento)],
    )
    return campo(r.comparacoes[0], "porto_origem").status


def test_nome_do_porto_com_espacos_a_mais_confere():
    assert _origem("HOCHIMINH, VIETNAM", "HO CHI MINH") == "OK"


def test_aeroporto_de_suvarnabhumi_confere_com_bangkok():
    assert _origem("BANGKOK", "SUVARNABHUMI", "AWB") == "OK"


def test_porto_diferente_continua_divergindo():
    assert _origem("HO CHI MINH", "HAIPHONG") == "DIVERGENTE"
    assert _origem("BANGKOK", "LAEM CHABANG") == "DIVERGENTE"


def test_porto_com_nome_de_pais_continua_sendo_porto():
    assert _origem("SINGAPORE", "SINGAPORE") == "OK"
    assert _origem("SINGAPORE", "PORT KLANG") == "DIVERGENTE"


def test_fob_em_porto_com_nome_de_pais_e_conferido():
    r = rodar(
        [doc("invoice", numero="A1", origem="PORT KLANG", incoterm=("FOB", "SINGAPORE")),
         doc("packing_list", refs=["A1"], origem="PORT KLANG")],
        [doc("conhecimento", subtipo="BL", numero="C1", refs=["A1"], origem="PORT KLANG")],
    )
    assert any("SINGAPORE" in d.mensagem and "embarque" in d.mensagem for d in r.divergencias)
