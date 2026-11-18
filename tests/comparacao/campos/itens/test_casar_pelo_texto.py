"""Casamento de itens sem código pelo texto: o melhor par dos dois lados, sem depender da ordem."""

from app.services.comparacao.campos.itens.casar_pelo_texto import casar_pelo_texto
from app.services.comparacao.campos.itens.tipos import ItemAgrupado
from tests.comparacao.apoio import doc, item, mensagens, rodar


def _item(descricao, quantidade=None):
    total = None if quantidade is None else ("UN", float(quantidade))
    return ItemAgrupado(None, descricao, None, total, None, "UN", [], [], "a0", 1)


def _casar(linhas, itens, pela_quantidade=True):
    return casar_pelo_texto([[x] for x in linhas], itens, list(range(len(linhas))), list(range(len(itens))),
                            pela_quantidade)


def _nomes(linhas, itens, resultado):
    return sorted((linhas[l].descricao, itens[i].descricao) for l, i in resultado.pares)


INVOICE = [_item('Gongo 14" Nuvem', 8), _item('Gongo 15" Nuvem', 6), _item('Sino 6" Nuvem', 10)]
PL = [_item("Nuvem serie - 15'' Gongo", 6), _item("Nuvem serie - 6'' Sino", 10),
      _item("Nuvem serie - 14'' Gongo", 8), _item("Parafuso sextavado", 3)]


def test_casa_pelo_texto_e_a_medida_sem_depender_da_ordem():
    esperado = [('Gongo 14" Nuvem', "Nuvem serie - 14'' Gongo"), ('Gongo 15" Nuvem', "Nuvem serie - 15'' Gongo"),
                ('Sino 6" Nuvem', "Nuvem serie - 6'' Sino")]
    assert _nomes(INVOICE, PL, _casar(INVOICE, PL)) == esperado
    assert _nomes(INVOICE[::-1], PL[::-1], _casar(INVOICE[::-1], PL[::-1])) == esperado


def test_item_identico_casa_antes_do_parecido():
    linhas = [_item("Bucha base peca 3", 5), _item("Bucha base anel peca 6", 4)]
    itens = [_item("Bucha base anel peca 6", 4), _item("Bucha base peca 3", 5)]
    assert _nomes(linhas, itens, _casar(linhas, itens)) == [("Bucha base anel peca 6",) * 2, ("Bucha base peca 3",) * 2]


def test_contradicao_nao_casa():
    assert _casar([_item("Fonte 12V 150W", 1)], [_item("Fonte 12V 120W", 1)]).pares == []


def test_descricao_que_serve_a_varias_linhas_e_generica():
    resultado = _casar([_item("Cabo USB tipo C", 5), _item("Cabo USB micro", 4)], [_item("Cabo USB")], False)
    assert resultado.pares == [] and resultado.genericos == {0}


def test_empate_com_a_mesma_quantidade_so_casa_quando_a_quantidade_desempata():
    linhas = [_item("Parafuso zincado", 5), _item("Parafuso zincado", 5)]
    itens = [_item("Parafuso zincado M", 5), _item("Parafuso zincado M", 5)]
    assert len(_casar(linhas, itens).pares) == 2
    assert _casar(linhas, itens, False).pares == []


def _rodar(invoice, pl):
    return rodar([doc("invoice", numero="1", itens=invoice)], [doc("packing_list", refs=["1"], itens=pl)])


def test_ordem_das_linhas_e_dos_arquivos_nao_muda_o_resultado():
    invoice = [item("Q-14", 'Gongo 14" Nuvem', 8, "PCS"), item("Q-15", 'Gongo 15" Nuvem', 6, "PCS"),
               item("Q-6", 'Sino 6" Nuvem NOT POLISHED', 10, "PCS")]
    pl = [item(None, "Nuvem serie - 15'' Gongo", 6, "PCS"), item(None, "Nuvem serie - 6'' Sino POLISHED", 10, "PCS"),
          item(None, "Nuvem serie - 14'' Gongo", 7, "PCS")]
    base = sorted(mensagens(_rodar(invoice, pl), "item"))
    assert len(base) == 2  # a quantidade do 14" e a negação do sino, que casa por ser o último par que sobrou
    assert sorted(mensagens(_rodar(invoice[::-1], pl[::-1]), "item")) == base
    trocados = rodar([doc("packing_list", refs=["1"], itens=pl)], [doc("invoice", numero="1", itens=invoice)])
    assert sorted(mensagens(trocados, "item")) == base
