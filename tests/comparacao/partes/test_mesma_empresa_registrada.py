"""Mesma empresa com CNPJ estrito: com CNPJ dos dois lados, só os dígitos decidem."""

from app.services.comparacao.partes.mesma_empresa import mesma_empresa_registrada


def test_cnpj_dos_dois_lados_decide_mesmo_com_o_nome_igual():
    assert not mesma_empresa_registrada(("Lumen Comercial Ltda", "11.222.333/0001-44"),
                                        ("Lumen Comercial Ltda", "55666777000188"))
    assert mesma_empresa_registrada(("Lumen Comercial Ltda", "11.222.333/0001-44"),
                                    ("Outro Nome Qualquer", "11222333000144"))


def test_sem_cnpj_num_lado_o_nome_tem_de_ser_da_mesma_empresa():
    assert mesma_empresa_registrada(("Lumen Comercial Ltda", None), ("LUMEN COMERCIAL LTDA.", "11222333000144"))
    assert not mesma_empresa_registrada(("Lumen Comercial Ltda", None), ("Lumen Distribuidora de Tecidos", None))
    assert not mesma_empresa_registrada(("Lumen Comercial Ltda", ""), ("Brisa Têxtil SA", None))
