from app.schemas import OutraDespesa, ValorMonetario
from tests.comparacao.apoio import doc, item, mensagens, rodar


def _invoice(total, *valores):
    linhas = [item(f"C-{n}", f"CADEIRA MODELO {n}", 10, "PCS", valor=v) for n, v in enumerate(valores)]
    d = doc("invoice", numero="INV-7", itens=linhas)
    return d.model_copy(update={"valor_total": ValorMonetario(valor=total, moeda="USD", texto_original=str(total),
                                                              pagina=1)})


def _pl(volumes_total, linhas, liquido=None, bruto=None):
    return doc("packing_list", numero="PL-3", volumes=volumes_total, liquido=liquido, bruto=bruto, itens=linhas)


def test_digital_soma_dos_valores_dois_centavos_abaixo_do_total_e_divergencia():
    r = rodar([_invoice(1500.02, 1000.00, 500.00)], escaneado=False)
    assert mensagens(r, "interna") == [
        "Invoice INV-7: a soma das linhas (USD 1.500,00) não bate com o total (USD 1.500,02); pedir correção."
    ]


def test_escaneado_soma_dos_volumes_e_so_aviso():
    linhas = [item("C-1", "MESA", volumes=(30, "CTN")), item("C-2", "BANCO", volumes=(10, "CTNS"))]
    r = rodar([_pl((42, "CARTONS"), linhas)], escaneado=True)
    assert not mensagens(r, "interna")
    assert ("Packing List PL-3 (a0.pdf, escaneado): a soma dos volumes das linhas (40 CARTONS) não bate com o total "
            "(42 CARTONS); conferir na imagem, pode ser leitura do scan.") in r.avisos


def test_sem_saber_se_e_scan_tambem_e_so_aviso():
    r = rodar([_invoice(1500.02, 1000.00, 500.00)])
    assert not mensagens(r, "interna")
    assert any("conferir na imagem" in a for a in r.avisos)


def test_somas_que_fecham_nao_acusam():
    linhas = [item("C-1", "MESA", liquido=10.004, bruto=11.004, volumes=(3, "CTN")),
              item("C-2", "BANCO", liquido=5.004, bruto=6.004, volumes=(2, "CTN"))]
    r = rodar([_invoice(1500.00, 1000.00, 500.00), _pl((5, "CTN"), linhas, liquido=15.0, bruto=17.0)],
              escaneado=False)
    assert not mensagens(r, "interna")


def test_linha_sem_valor_nao_confere_a_soma():
    linhas = [item("C-1", "MESA", volumes=(3, "CTN")), item("C-2", "BANCO")]
    r = rodar([_pl((9, "CTN"), linhas)], escaneado=False)
    assert not mensagens(r, "interna")


def test_quantidade_soma_so_as_linhas_da_unidade_do_total():
    linhas = [item("C-1", "MESA", 4, "PCS", valor=1.0), item("C-2", "BANCO", 6, "PIECES", valor=1.0),
              item("C-3", "TECIDO", 25, "M", valor=1.0)]
    d = doc("invoice", numero="INV-8", quantidade=(10, "PCS"), itens=linhas)
    assert not mensagens(rodar([d], escaneado=False), "interna")
    d = doc("invoice", numero="INV-8", quantidade=(12, "PCS"), itens=linhas)
    assert mensagens(rodar([d], escaneado=False), "interna") == [
        "Invoice INV-8: a soma das quantidades das linhas (10 PCS) não bate com o total (12 PCS); pedir correção."
    ]


def test_peso_dentro_do_arredondamento_por_linha_passa_e_fora_acusa():
    linhas = [item("C-1", "MESA", liquido=10.01), item("C-2", "BANCO", liquido=5.01)]
    assert not mensagens(rodar([_pl(None, linhas, liquido=15.0)], escaneado=False), "interna")
    assert mensagens(rodar([_pl(None, linhas, liquido=14.9)], escaneado=False), "interna") == [
        "Packing List PL-3: a soma dos pesos líquidos das linhas (15,02 kg) não bate com o total (14,90 kg); "
        "pedir correção."
    ]


def test_peso_bruto_menor_que_o_liquido_na_linha_e_no_total():
    linhas = [item("C-1", "MESA", liquido=22.5, bruto=21.5)]
    r = rodar([_pl(None, linhas, liquido=22.5, bruto=21.5)], escaneado=False)
    assert mensagens(r, "interna") == [
        "Packing List PL-3: o peso bruto do total (21,50 kg) é menor que o líquido (22,50 kg); pedir correção.",
        "Packing List PL-3: o peso bruto da linha C-1 (21,50 kg) é menor que o líquido (22,50 kg); pedir correção.",
    ]


def test_ordem_das_linhas_nao_muda_o_resultado():
    a = rodar([_invoice(0.3, 0.1, 0.2)], escaneado=False)
    b = rodar([_invoice(0.3, 0.2, 0.1)], escaneado=False)
    assert mensagens(a, "interna") == mensagens(b, "interna") == []


def test_total_com_frete_informado_somado_fecha():
    d = _invoice(1530.00, 1000.00, 500.00)
    frete = ValorMonetario(valor=30.0, moeda="USD", texto_original="30.00", pagina=1)
    assert not mensagens(rodar([d.model_copy(update={"valor_frete": frete})], escaneado=False), "interna")


def test_frete_que_nao_explica_a_diferenca_continua_acusando():
    d = _invoice(1531.00, 1000.00, 500.00)
    frete = ValorMonetario(valor=30.0, moeda="USD", texto_original="30.00", pagina=1)
    assert len(mensagens(rodar([d.model_copy(update={"valor_frete": frete})], escaneado=False), "interna")) == 1


def _com_despesas(d, *valores):
    despesas = [OutraDespesa(descricao=f"TAXA {n}", valor=v, texto_original=str(v), pagina=1)
                for n, v in enumerate(valores)]
    return d.model_copy(update={"outras_despesas": despesas})


def test_outras_despesas_e_descontos_entram_na_soma():
    d = _com_despesas(_invoice(1530.00, 1000.00, 500.00), 50.0, -20.0)
    assert not mensagens(rodar([d], escaneado=False), "interna")


def test_despesa_que_nao_explica_a_diferenca_continua_acusando():
    d = _com_despesas(_invoice(1530.00, 1000.00, 500.00), 25.0)
    assert len(mensagens(rodar([d], escaneado=False), "interna")) == 1
