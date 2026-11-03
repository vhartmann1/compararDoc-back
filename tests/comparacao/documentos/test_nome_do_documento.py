"""Como um documento sem número aparece nas mensagens: pela invoice do par ou pelo nome curto do arquivo."""

from app.services.comparacao.documentos.identificacao_do_documento import nome_curto_do_arquivo, nome_doc
from app.services.comparacao.tipos import Fonte
from tests.comparacao.apoio import arquivo, doc, enviar

ARQUIVO_LONGO = "PASTA - 777A Versao final dos documentos COMPLETO packing list.pdf"


def _pl_sem_numero(nome, invoice=None):
    pl = Fonte(arquivo("a1", nome), doc("packing_list", 100, 110), (1, 0))
    pl.invoice_par = invoice
    return pl


def test_pl_sem_numero_pareado_aparece_pela_invoice():
    assert nome_doc(_pl_sem_numero(ARQUIVO_LONGO, doc("invoice", numero="777A"))) == "Packing List da invoice 777A"


def test_pl_sem_numero_sem_par_aparece_pelo_arquivo_curto():
    assert nome_doc(_pl_sem_numero(ARQUIVO_LONGO)) == "Packing List (777A Versao final dos documentos…)"
    assert nome_doc(_pl_sem_numero("PL.pdf")) == "Packing List (PL.pdf)"


def test_nome_curto_tira_so_o_prefixo_de_pasta_em_maiusculas():
    assert nome_curto_do_arquivo("PASTA - lista.pdf") == "lista.pdf"
    assert nome_curto_do_arquivo("Lista - parte 2.pdf") == "Lista - parte 2.pdf"


def test_mensagem_interna_do_pl_pareado_cita_a_invoice():
    r = enviar(("inv.pdf", "application/pdf", [doc("invoice", 100, 110, numero="777A")]),
               (ARQUIVO_LONGO, "application/pdf",
                [doc("packing_list", 100, 110, refs=["777A"], internas=[("caixas não fecham", "1 a 9 × 10")])]))
    assert any(d.mensagem.startswith("Packing List da invoice 777A: ") for d in r.divergencias)
