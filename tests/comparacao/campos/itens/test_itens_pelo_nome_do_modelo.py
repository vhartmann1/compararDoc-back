from tests.comparacao.apoio import doc, item, rodar

INVOICE = [
    item("ZX Storm", "ZX Storm - Caixas de petecas com 24 tubos e com 3 petecas em cada tubo", 100, "CAIXAS"),
    item("ZX Storm", "ZX Storm - Caixas de petecas com 18 tubos e com 4 petecas em cada tubo", 50, "CAIXAS"),
    item("ZX Coral", "ZX Coral - Caixas de petecas com 24 tubos e com 3 petecas em cada tubo", 20, "CAIXAS"),
    item("ZX Turbo", "ZX Turbo - Caixas de petecas com 24 tubos e com 3 petecas em cada tubo", 10, "CAIXAS"),
]
PL = [
    item("QW 100", "ZX Storm-4pack", 300, "DZ", referencia="ZX Storm-4pack"),
    item(None, "ZX Coral-Stage1", 120, "DZ", referencia="ZX Coral-Stage1"),
    item("QW 100", "ZX Storm-3pack", 600, "DZ", referencia="ZX Storm-3pack"),
    item(None, "ZX Pro Turbo-3pack", 60, "DZ", referencia="ZX Pro Turbo-3pack"),
]


def _rodar(itens_invoice, itens_pl):
    return rodar([doc("invoice", numero="7", itens=itens_invoice), doc("packing_list", numero="7", itens=itens_pl)])


def _itens(r):
    return sorted(d.mensagem for d in r.divergencias if d.categoria == "item")


def test_nome_do_modelo_casa_com_a_variante_e_avisa_a_unidade():
    r = _rodar(INVOICE, PL)
    [sobra] = _itens(r)  # o nome não começa o outro: é o par que sobrou, com a descrição apontada
    assert sobra.startswith("Item ZX Turbo: descrição Invoice ZX Turbo") and "ZX Pro Turbo-3pack" in sobra
    assert any("quantidade em unidades diferentes (Invoice CAIXAS × Packing List DZ)" in a for a in r.avisos)


def test_ordem_das_linhas_nao_muda_o_resultado():
    assert _itens(_rodar(INVOICE[::-1], PL[::-1])) == _itens(_rodar(INVOICE, PL))


def test_mesma_unidade_nao_casa_pelo_nome():
    pl = [item(None, x.descricao, 10, "CAIXAS", referencia=x.referencia) for x in PL[1:3]]
    r = _rodar(INVOICE[1:3], pl)
    assert len(_itens(r)) == 4


def test_variante_que_nao_desempata_continua_de_um_lado_so():
    invoice = [item("ZX Storm", "ZX Storm - caixa azul", 100, "CAIXAS"),
               item("ZX Storm", "ZX Storm - caixa verde", 50, "CAIXAS")]
    r = _rodar(invoice, [PL[0], PL[2]])
    assert len(_itens(r)) == 4
