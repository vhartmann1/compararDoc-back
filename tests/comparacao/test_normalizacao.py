import pytest

from app.schemas import Medida
from app.services.comparacao.normalizacao import (
    embalagem,
    enderecos_compativeis,
    formatar_cnpj,
    formatar_contagem,
    formatar_kg,
    formatar_ncm,
    nomes_equivalentes,
    normalizar_ncm,
    normalizar_nome_empresa,
    normalizar_numero_documento,
    normalizar_po,
    normalizar_porto,
    para_kg,
    referencias_iguais,
    so_digitos,
    unidade_quantidade,
)


def medida(valor, unidade):
    return Medida(valor=valor, unidade=unidade, texto_original=f"{valor} {unidade}", pagina=1)


@pytest.mark.parametrize(
    ("valor", "unidade", "esperado"),
    [
        (21200, "KG", 21200.0),
        (46737, "LB", 21199.547),
        (21.2, "MT", 21200.0),
        (21.2, "TON", 21200.0),
        (500, "G", 0.5),
    ],
)
def test_para_kg(valor, unidade, esperado):
    assert para_kg(medida(valor, unidade)) == pytest.approx(esperado, abs=0.001)


def test_unidade_desconhecida_nao_converte():
    assert para_kg(medida(10, "OUTRA")) is None


def test_ncm():
    assert so_digitos("HS CODE 3901.10") == "390110"
    assert normalizar_ncm("3901.10.10") == "39011010"
    assert normalizar_ncm("39.04.10.20.00") == "39041020"  # código nacional de 10 dígitos
    assert normalizar_ncm("NCM NO6402.19.00") == "64021900"


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("PAIRS", "PRS"), ("pares", "PAIR"), ("TON", "MT"), ("PCS", "UNITS"), ("BAGS", "bolsas"),
        ("BOTELLAS", "BOTTLES"), ("BT", "garrafas"), ("CAJAS", "CASES"), ("CTNS", "CAR"), ("CARTONS", "caixas"),
        ("Pallet(s)", "PALETES"), ("MTS", "TON"),
    ],
)
def test_unidades_quantidade_equivalentes(a, b):
    assert unidade_quantidade(a) == unidade_quantidade(b)


def test_unidade_quantidade_conversao():
    assert unidade_quantidade("TO") == ("KG", 1000.0)
    assert unidade_quantidade("PAIRS")[0] != unidade_quantidade("PCS")[0]
    assert unidade_quantidade("ROLLS") == ("ROLLS", 1.0)
    assert unidade_quantidade("CASES")[0] != unidade_quantidade("PALLETS")[0] != unidade_quantidade("BOTTLES")[0]


def test_embalagem_so_reconhece_as_especificas():
    assert embalagem("CTNS") == "CAIXAS"
    assert embalagem("Pallets") == "PALETES"
    assert embalagem("PACKAGES") is None
    assert embalagem("BOTTLES") is None


def test_numero_documento_e_po():
    assert normalizar_numero_documento("0077032707") == "77032707"
    assert normalizar_numero_documento("0070023077") == normalizar_numero_documento("70023077")
    assert normalizar_numero_documento("ktr-273938/03") == "KTR27393803"
    assert normalizar_po("246731-01") == "24673101"
    assert normalizar_po(" hbpx 41357 ") == "HBPX41357"
    assert normalizar_po("PO 15 March") == normalizar_po("15 March") == "15MARCH"
    assert normalizar_po("P.O. No. 778-1") == normalizar_po("PO#7781") == normalizar_po("Purchase Order: 778-1") == "7781"
    assert normalizar_po("POLY-778") == "POLY778"  # "PO" que faz parte do número fica


def test_nome_empresa():
    assert normalizar_nome_empresa("Capital Trade Importação e Exportação Ltda.") == "CAPITAL TRADE"
    assert normalizar_nome_empresa("SERRANA POLÍMEROS S.A.S.") == "SERRANA POLIMEROS"
    assert nomes_equivalentes("Aurora Silk Co.", "AURORA SILK CO.")
    assert nomes_equivalentes("CAPITAL TRADE IMPORTACAO EEXPORTACAO LTDA", "Capital Trade Importação e Exportação Ltda.")
    assert nomes_equivalentes("Delta Fast-Run Footwear Ltd.", "DELTA FAST RUN FOOTWEAR LIMITED")
    assert not nomes_equivalentes("Orion Pacific Trading Co., Ltd.", "Delta Fast-Run Footwear Ltd.")
    assert not nomes_equivalentes("Capital Trade", "Plastnorte Distribuidora de Resinas")


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("NAVEGANTES - SC BRASIL", "NAVEGANTES"),
        ("Navegantes, Brazil", "NAVEGANTES"),
        ("Port of Navegantes", "NAVEGANTES"),
        ("Itapoá - SC", "ITAPOA"),
        ("BEIJIN AIRPORT", "BEIJIN"),
        ("Shekou (China)", "SHENZHEN"),
        ("TIANJIN XINGANG", "TIANJIN"),
        ("Aeroporto de Viracopos", "CAMPINAS"),
        ("CARTAGENA - COLOMBIA", "CARTAGENA"),
        ("PORT KELANG, MALAYSIA", "KLANG"),
    ],
)
def test_porto(texto, esperado):
    assert normalizar_porto(texto) == esperado


def test_formatacao_br():
    assert formatar_kg(21250) == "21.250,00 kg"
    assert formatar_kg(0.5) == "0,50 kg"
    assert formatar_ncm("39011010") == "3901.10.10"
    assert formatar_ncm("390110") == "3901.10"
    assert formatar_contagem(53, "CTN") == "53 CTN"
    assert formatar_contagem(1500, "PCS") == "1.500 PCS"
    assert formatar_contagem(24.5, "TON") == "24,5 TON"
    assert formatar_cnpj("12345678000190") == "12.345.678/0001-90"


# v3 ------------------------------------------------------------------------

from app.services.comparacao.normalizacao import (  # noqa: E402
    descricoes_equivalentes,
    enderecos_equivalentes,
    palavras_do_endereco,
    normalizar_incoterm,
    normalizar_lote,
    normalizar_moeda,
    normalizar_pais,
    normalizar_validade,
)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [("Exp 11/2025", "11/2025"), ("Exp 03/29", "03/2029"), ("Exp 09/28 N", "09/2028"), ("20/02/2026", "02/2026"),
     ("2026-02-20", "02/2026"), ("EXP 01/2029", "01/2029")],
)
def test_normalizar_validade(texto, esperado):
    assert normalizar_validade(texto) == esperado


def test_pais_moeda_incoterm_lote():
    assert normalizar_pais("South Korea") == normalizar_pais("KR") == normalizar_pais("REPUBLIC OF KOREA") == "KR"
    assert normalizar_pais("P.R. China") == normalizar_pais("CHINA") == "CN"
    assert normalizar_pais("The Netherlands") == normalizar_pais("NL") == normalizar_pais("Holanda") == "NL"
    assert normalizar_pais("Belgium") == normalizar_pais("Bélgica") == "BE"
    assert normalizar_moeda("€") == normalizar_moeda("euros") == "EUR"
    assert normalizar_moeda("US$") == "USD"
    assert normalizar_incoterm("Fob") == "FOB"
    assert normalizar_incoterm("CFR-ITAPOA") == "CFR"
    assert normalizar_lote("#LT2031C14-E") == normalizar_lote("LT2031 C14E")


def test_descricao_e_endereco():
    assert descricoes_equivalentes("POLIREX YK 455", "POLIREX YK 455 / 25 kg SA PVC RESIN")
    assert not descricoes_equivalentes("POLIRMX HD 475 / 25 kg SA", "POLIREX YK 455")
    assert enderecos_equivalentes("Calle 10 #20-30, Bogotá", "CALLE 10 20-30 BOGOTA")
    assert not enderecos_equivalentes("Room 804, Hangzhou, Zhejiang", "Rua das Flores 100, Itajaí")


def test_endereco_em_outra_ordem_e_com_o_pais_abreviado_e_o_mesmo():
    assert enderecos_equivalentes("Kanaalweg 12, 4811 AB Breda, The Netherlands", "Kanaalweg 12, Breda, 4811 AB, NL")
    assert enderecos_equivalentes("Via Roma 5, 20121 Milano, Italy", "VIA ROMA 5 MILANO 20121 ITALIA")
    assert not enderecos_equivalentes("Kanaalweg 12, 4811 AB Breda, NL", "Havenstraat 3, 4811 AB Breda, NL")
    assert palavras_do_endereco("Kanaalweg 12, The Netherlands") == {"KANAALWEG", "12", "NL"}


@pytest.mark.parametrize(
    ("a", "b", "esperado"),
    [
        (("Pudong New District, Shanghai, 200120, China", "Shanghai"),
         ("Pudong New District, Gyeonggi-do, South Korea", "GYEONGGI-DO"), False),
        (("Calle 10 #20-30, Bogotá D.C., Colombia", "BOGOTÁ, D.C."), ("CALLE 10 #20-30 BOGOTA COLOMBIA", "Bogota"), True),
        (("1 Jungang-ro, Hwaseong-si, Gyeonggi-do", "HWASEONG-SI"), ("1 Jungang-ro, Hwaseong-si, Gyeonggi-do", "GYEONGGI-DO"), True),
        (("Rua A, 10 - Seoul", None), ("RUA A 10, SEOUL", "SEOUL"), True),
        (("Rua A, 10 - Seoul", None), ("Av. Paulista 1000, São Paulo", None), False),
    ],
)
def test_enderecos_compativeis(a, b, esperado):
    assert enderecos_compativeis(a, b) is esperado


@pytest.mark.parametrize(
    ("a", "b", "esperado"),
    [
        ("POLIREX ZK 455", "Polirex ZK-455", True),
        ("POLIREX ZK 455", "POLIREX YK 455", False),
        ("ZK 455", "POLIREX ZK 455", True),
        ("Trail-Max 10", "TRAIL MAX 10", True),
        ("Trail-Max 10", "Trail-Max 100", False),
        ("Wind-Ride 500", "Wind-Ride 50O", False),
    ],
)
def test_referencias_iguais(a, b, esperado):
    assert referencias_iguais(a, b) is esperado


def test_numero_sem_serie():
    from app.services.comparacao.normalizacao import numero_sem_serie

    assert numero_sem_serie("FT A26/000123") == numero_sem_serie("GR A26/000123") == "A26000123"
    assert numero_sem_serie("SU26081EA") == "SU26081EA"


def test_endereco_com_mais_detalhe_de_um_lado_e_o_mesmo():
    assert enderecos_equivalentes("2F No 88 Lianhua Road Minhang District Shanghai", "No 88 Lianhua Road Shanghai 201100 China")
    assert not enderecos_equivalentes("Shanghai, China", "No 88 Lianhua Road Shanghai")


def test_registro_chines_com_letras_nao_vira_cnpj():
    assert formatar_cnpj("91110000MA0123B45X") == "91110000MA0123B45X"  # 14 dígitos com as letras tiradas
    assert formatar_cnpj("07872326000158") == "07.872.326/0001-58"


def test_endereco_com_sigla_da_provincia_e_o_nome_completo_confere():
    assert enderecos_equivalentes("12 Maple Road, Lakeview, ON K1A 0B1, Canada", "12 MAPLE ROAD, LAKEVIEW ONTARIO, CANADA K1A 0B1")
