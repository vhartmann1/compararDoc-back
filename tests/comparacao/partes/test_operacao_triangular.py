"""Operação triangular (shipper de outra empresa) e mesma empresa com o nome escrito de outro jeito."""

from app.services.comparacao.mensagens import trecho
from app.services.comparacao.partes.mesma_empresa import relacao_entre_nomes
from tests.comparacao.apoio import campo, doc, rodar

CAMPOS_DO_EXPORTADOR = ("exportador", "endereco_exportador", "pais_exportador")
TROCAS_DE_VIZINHAS = (("Kron GmbH", "Korn GmbH"), ("Ravel SA", "Rvael SA"), ("Lito Ltd", "Ltio Ltd"),
                      ("Avo Ltd", "Aov Ltd"), ("Brixon GmbH", "Birxno GmbH"))
DIGITADOS_SEM_ENDERECO = (("KRON GmbH", "K0RN GmbH"), ("Kron GmbH", "Konr GmbH"),
                          ("Kron GmbH", "Korm GmbH"), ("Ravel SA", "Rvaei SA"), ("Lito Ltd", "Ltia Ltd"),
                          ("Brixon GmbH", "Bricsom GmbH"))


def _bl(**kw):
    return doc("conhecimento", None, 110, subtipo="BL", numero="BL1", **kw)


def _par(exportador, endereco="Ringstrasse 5, Sudstadt", pais="AUSTRIA", **kw):
    comum = dict(exportador=exportador, endereco_exportador=endereco, pais_exportador=pais, **kw)
    return [doc("invoice", 100, 110, numero="A1", **comum), doc("packing_list", 100, 110, refs=["A1"], **comum)]


def _status(r, comparacao=0):
    return [campo(r.comparacoes[comparacao], c).status for c in CAMPOS_DO_EXPORTADOR]


def _do_exportador(r):
    return [d for d in r.divergencias if d.campo in CAMPOS_DO_EXPORTADOR]


def test_forma_juridica_e_termos_genericos_nao_distinguem_a_empresa():
    assert relacao_entre_nomes("AGRICOLA SERRA VERDE", "SERRA VERDE S.r.l. Società Agricola") == "mesma"
    assert relacao_entre_nomes("PT. LUMEN JAYA", "Lumen Jaya") == "mesma"


def test_sem_palavra_distintiva_em_comum_e_outra_empresa():
    assert relacao_entre_nomes("Comercial Sul GmbH", "Fabrica Norte Ltd") == "outra"


def test_palavra_distintiva_em_comum_com_outras_diferentes_fica_incerta():
    assert relacao_entre_nomes("Pinhal Moveis Ltda", "Pinhal Tintas e Vernizes Ltda") == "incerta"


def test_palavra_quase_igual_por_digitacao_fica_incerta_e_nunca_outra():
    assert relacao_entre_nomes("Brixon GmbH", "Brixom GmbH") == "incerta"
    assert relacao_entre_nomes("Comercial Sul GmbH", "Comercail Sol GmbH") == "incerta"


def test_uma_letra_errada_em_nome_curto_ou_duas_em_nome_longo_fica_incerta():
    assert relacao_entre_nomes("Kron GmbH", "Krom GmbH") == "incerta"
    assert relacao_entre_nomes("Avo Ltd", "Ava Ltd") == "incerta"
    assert relacao_entre_nomes("Brixon GmbH", "Brikom GmbH") == "incerta"
    assert relacao_entre_nomes("Alfa GmbH", "Beta GmbH") == "outra"


def test_letras_vizinhas_trocadas_contam_como_um_erro_so():
    for a, b in TROCAS_DE_VIZINHAS:
        assert relacao_entre_nomes(a, b) == "incerta", (a, b)


def _shipper_digitado_errado(invoice, bl, endereco_bl, ordem):
    arquivos = [_par(invoice), [_bl(exportador=bl, endereco_exportador=endereco_bl)]]
    return rodar(*(arquivos if ordem else arquivos[::-1]))


def test_shipper_digitado_errado_diverge_com_ou_sem_endereco_nas_duas_ordens():
    digitados = (("Kron GmbH", "Krom GmbH"), ("Avo Ltd", "Ava Ltd"), ("Brixon GmbH", "Brikom GmbH"))
    for invoice, bl in digitados + TROCAS_DE_VIZINHAS:
        for endereco_bl in (None, "Postfach 12, Sudstadt"):
            for ordem in (True, False):
                r = _shipper_digitado_errado(invoice, bl, endereco_bl, ordem)
                assert campo(r.comparacoes[0], "exportador").status == "DIVERGENTE", (invoice, endereco_bl, ordem)
                if endereco_bl:
                    assert campo(r.comparacoes[0], "endereco_exportador").status == "DIVERGENTE"
                assert not any("triangular" in a for a in r.avisos)


def test_forma_juridica_colada_e_digito_no_lugar_de_letra_nao_distinguem():
    assert relacao_entre_nomes("Kron GmbH", "KronGmbH") == "mesma"
    assert relacao_entre_nomes("KRON GmbH", "K0RN GmbH") == "incerta"
    assert relacao_entre_nomes("Lito Ltd", "L1TO Ltd") == "mesma"


def test_bl_sem_endereco_do_shipper_nunca_presume_triangular():
    for invoice, bl in DIGITADOS_SEM_ENDERECO + (("Alfa GmbH", "Beta GmbH"),):
        for ordem in (True, False):
            r = _shipper_digitado_errado(invoice, bl, None, ordem)
            assert campo(r.comparacoes[0], "exportador").status == "DIVERGENTE", (invoice, bl, ordem)
            assert not any("triangular" in a for a in r.avisos), (invoice, bl, ordem)


def test_forma_juridica_colada_no_nome_do_shipper_confere():
    for ordem in (True, False):
        r = _shipper_digitado_errado("Kron GmbH", "KronGmbH", None, ordem)
        assert campo(r.comparacoes[0], "exportador").status == "OK"
        assert not any("triangular" in a for a in r.avisos)


def test_nome_realmente_diferente_continua_triangular_nas_duas_ordens():
    for ordem in (True, False):
        r = _shipper_digitado_errado("Alfa GmbH", "Beta GmbH", "Postfach 12, Sudstadt", ordem)
        assert not _do_exportador(r)
        assert any("Shipper do BL (Beta GmbH)" in a and "triangular" in a for a in r.avisos)


def test_artigo_e_import_export_distinguem_e_a_ordem_das_palavras_conta():
    assert relacao_entre_nomes("Sol Import Ltda", "Sol Export Ltda") == "incerta"
    assert relacao_entre_nomes("Del Monte Foods", "Monte Foods") == "incerta"
    assert relacao_entre_nomes("Verde Serra Ltda", "Serra Verde Ltda") == "incerta"
    assert relacao_entre_nomes("AZIENDA AGRICOLA LA QUERCIA", "LA QUERCIA S.r.l. Società Agricola") == "mesma"


def test_shipper_de_outra_empresa_vira_aviso_de_triangular():
    r = rodar(_par("Comercial Sul GmbH"),
              [_bl(exportador="Fabrica Norte Ltd", endereco_exportador="12 Industrial Rd, Northtown",
                   pais_exportador="CANADA")])
    assert not _do_exportador(r)
    assert _status(r) == ["OK"] * 3
    assert any("Shipper do BL (Fabrica Norte Ltd) é outra empresa que o exportador" in a
               and "(Comercial Sul GmbH)" in a and "triangular" in a for a in r.avisos)


def test_triangular_nao_esconde_divergencia_entre_invoice_e_packing_list():
    r = rodar([doc("invoice", 100, 110, numero="A1", exportador="Comercial Sul GmbH"),
               doc("packing_list", 100, 110, refs=["A1"], exportador="Outra Casa Ltda")],
              [_bl(exportador="Fabrica Norte Ltd", endereco_exportador="12 Industrial Rd, Northtown")])
    assert [d.mensagem for d in _do_exportador(r)] == [
        "Exportador: Invoice Comercial Sul GmbH × Packing List Outra Casa Ltda"]


def test_mesma_empresa_com_nome_escrito_diferente_confere_o_nome():
    r = rodar(_par("SERRA VERDE S.r.l. Società Agricola"),
              [_bl(exportador="AGRICOLA SERRA VERDE", endereco_exportador="RINGSTRASSE 5, SUDSTADT",
                   pais_exportador="AUSTRIA")])
    assert _status(r) == ["OK"] * 3
    assert not any("triangular" in a for a in r.avisos)


def test_mesma_empresa_com_endereco_diferente_e_erro():
    r = rodar(_par("SERRA VERDE S.r.l."),
              [_bl(exportador="AGRICOLA SERRA VERDE", endereco_exportador="Via dei Pini 40, Collina",
                   pais_exportador="AUSTRIA")])
    assert _status(r) == ["OK", "DIVERGENTE", "OK"]
    assert not any("triangular" in a for a in r.avisos)


def test_shipper_com_erro_de_digitacao_continua_divergindo():
    r = rodar(_par("Brixon GmbH", pais="AUSTRIA"),
              [_bl(exportador="Brixom GmbH", endereco_exportador="Hauptplatz 9, Nordstadt", pais_exportador="GERMANY")])
    assert _status(r) == ["DIVERGENTE"] * 3
    assert not any("triangular" in a for a in r.avisos)


def test_shipper_com_letras_trocadas_continua_divergindo():
    r = rodar(_par("Comercial Sul GmbH"), [_bl(exportador="Comercail Sol GmbH")])
    assert campo(r.comparacoes[0], "exportador").status == "DIVERGENTE"
    assert not any("triangular" in a for a in r.avisos)


def test_shipper_com_outro_nome_no_mesmo_endereco_nao_e_triangular():
    r = rodar(_par("Comercial Sul GmbH"),
              [_bl(exportador="Fabrica Norte Ltd", endereco_exportador="RINGSTRASSE 5, SUDSTADT")])
    assert campo(r.comparacoes[0], "exportador").status == "DIVERGENTE"
    assert not any("triangular" in a for a in r.avisos)


def test_triangular_sem_nada_para_comparar_fica_insuficiente_sem_aviso_repetido():
    r = rodar([doc("invoice", 100, 110, numero="A1", exportador="Comercial Sul GmbH",
                   endereco_exportador="Ringstrasse 5, Sudstadt")],
              [_bl(exportador="Fabrica Norte Ltd", endereco_exportador="12 Industrial Rd, Northtown")])
    assert campo(r.comparacoes[0], "exportador").status == "INSUFICIENTE"
    assert not any("Exportador informado só em" in a for a in r.avisos)


def test_aviso_triangular_usa_o_documento_quando_falta_o_nome_do_exportador():
    r = rodar([doc("invoice", 100, 110, numero="A1", exportador="  ", fabricante=("Comercial Sul GmbH",)),
               doc("packing_list", 100, 110, refs=["A1"], exportador="Comercial Sul GmbH")],
              [_bl(exportador="Fabrica Norte Ltd", endereco_exportador="12 Industrial Rd, Northtown")])
    aviso = next(a for a in r.avisos if "triangular" in a)
    assert "()" not in aviso and "(Comercial Sul GmbH)" in aviso


def test_nome_parecido_sem_ser_igual_continua_divergindo():
    r = rodar(_par("Pinhal Tintas e Vernizes Ltda"), [_bl(exportador="Pinhal Moveis Ltda")])
    assert campo(r.comparacoes[0], "exportador").status == "DIVERGENTE"
    assert not any("triangular" in a for a in r.avisos)


def _consolidado(ordem):
    pares = {
        "A1": _par("Sol Nascente Trading Co", endereco="Rua Um 1, Portoalto", pais="CHINA"),
        "B2": _par("Montanha Azul Fabrica Ltd", endereco="Rua Dois 2, Serrania", pais="CHINA"),
    }
    for numero, (inv, pl) in pares.items():
        inv.numero, pl.invoices_referenciadas = numero, [numero]
    bl = _bl(exportador="SOL NASCENTE TRADING CO", endereco_exportador="Avenida Tres 3, Portoalto",
             pais_exportador="CHINA")
    return rodar(*[pares[n] for n in ordem], [bl])


def test_shipper_de_uma_das_invoices_compara_so_com_ela_e_avisa_a_outra():
    for ordem in (("A1", "B2"), ("B2", "A1")):
        r = _consolidado(ordem)
        assert len(r.avisos) == len(set(r.avisos))
        mensagens = [d.mensagem for d in _do_exportador(r)]
        assert len(mensagens) == 1
        assert mensagens == ["Consolidado — Endereço do exportador (SOL NASCENTE TRADING): "
                             "BL 'Avenida Tres 3, Portoalto' × Invoice A1 'Rua Um 1, Portoalto'; pedir correção."]
        assert any("(Montanha Azul Fabrica Ltd)" in a and "triangular" in a for a in r.avisos)



def _com_fornecedor_incerto(ordem, endereco_do_bl="Avenida Tres 3, Portoalto"):
    """Shipper da invoice A1; B2 tem palavra genérica em comum com ele (incerta) e C3 é outra empresa."""
    pares = {"A1": _par("Sol Nascente Tech Co", endereco="Rua Um 1, Portoalto", pais="CHINA"),
             "B2": _par("Montanha Azul Tech Ltd", endereco="Rua Dois 2, Serrania", pais="CHINA"),
             "C3": _par("Rio Claro Fabrica Ltd", endereco="Rua Quatro 4, Vale", pais="CHINA")}
    for numero, (inv, pl) in pares.items():
        inv.numero, pl.invoices_referenciadas = numero, [numero]
    bl = _bl(exportador="SOL NASCENTE TECH CO", endereco_exportador=endereco_do_bl, pais_exportador="CHINA")
    return rodar(*[pares[n] for n in ordem], [bl])


def _enderecos(r):
    return [d.mensagem for d in r.divergencias if d.campo == "endereco_exportador"]


def test_endereco_do_shipper_so_contra_o_documento_da_mesma_empresa():
    for ordem in (("A1", "B2", "C3"), ("C3", "B2", "A1")):
        assert _enderecos(_com_fornecedor_incerto(ordem)) == [
            "Consolidado — Endereço do exportador (SOL NASCENTE TECH): "
            "BL 'Avenida Tres 3, Portoalto' × Invoice A1 'Rua Um 1, Portoalto'; pedir correção."]


def test_endereco_igual_ao_da_mesma_empresa_continua_apontando_o_fornecedor_incerto():
    r = _com_fornecedor_incerto(("A1", "B2", "C3"), endereco_do_bl="Rua Um 1, Portoalto")
    assert _enderecos(r) == [
        "Consolidado — Endereço do exportador (SOL NASCENTE TECH): "
        "BL 'Rua Um 1, Portoalto' × Invoice B2 'Rua Dois 2, Serrania'; pedir correção."]


def test_trecho_corta_depois_de_onde_os_enderecos_diferem():
    longo = "Bloco 7, Parque Industrial Lagoa Seca, Avenida Central 400, Distrito Norte"
    assert trecho(longo, "Bloco 7, Parque Industrial Lagoa Seca, Avenida Central 401") == "Bloco 7, Parque Industrial Lagoa Seca, Avenida Central 400, Distrito…"
    assert trecho(longo, "Sala 2") == "Bloco 7, Parque Industrial Lagoa Seca…"
