"""Outras despesas da invoice: campo no schema da resposta, default vazio e desconto negativo."""

from app.schemas import DocumentoExtraido, ExtracaoArquivo
from app.services.leitura.formato_da_resposta import SISTEMA

INVOICE = {
    "tipo": "invoice", "subtipo": None, "paginas": [1], "numero": "INV-001", "invoices_referenciadas": [], "po": None,
    "incoterm": None, "frete": None, "moeda": {"valor": "USD", "pagina": 1}, "pais_origem": None,
    "emitente_assinatura": None, "versao": "original", "exportador": None, "consignatario": None,
    "porto_origem": None, "porto_destino": None, "peso_liquido_total": None, "peso_bruto_total": None,
    "volumes_total": None, "quantidade_total": None, "ncms": [], "itens": [], "inconsistencias_internas": [],
}


def test_schema_da_resposta_pede_outras_despesas():
    assert "outras_despesas" in DocumentoExtraido.model_json_schema()["properties"]
    assert "outras_despesas" in SISTEMA


def test_sem_outras_despesas_fica_lista_vazia():
    assert DocumentoExtraido.model_validate(INVOICE).outras_despesas == []


def test_despesa_positiva_e_desconto_negativo():
    despesas = [
        {"descricao": "Pallets", "valor": 90.0, "texto_original": "USD 90.00", "pagina": 1},
        {"descricao": "Discount", "valor": -200.0, "texto_original": "USD 200.00", "pagina": 1},
    ]
    extracao = ExtracaoArquivo.model_validate({"documentos": [INVOICE | {"outras_despesas": despesas}]})
    assert [d.valor for d in extracao.documentos[0].outras_despesas] == [90.0, -200.0]
