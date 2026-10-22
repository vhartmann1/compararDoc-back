"""Empresa do cabeçalho: lida como dado, sem virar inconsistência interna."""

import json
from pathlib import Path
from types import SimpleNamespace

from app.schemas import ArquivoEntrada
from app.services.leitura import ler_pelo_claude_code
from app.services.leitura.formato_da_resposta import SISTEMA
from app.services.leitura.prompts import PROMPT_SISTEMA

DOCUMENTO = {
    "tipo": "invoice", "subtipo": None, "paginas": [1], "numero": "INV-001", "invoices_referenciadas": [], "po": None,
    "incoterm": None, "frete": None, "moeda": None, "pais_origem": None, "versao": "original", "exportador": None,
    "consignatario": None, "porto_origem": None, "porto_destino": None, "peso_liquido_total": None,
    "peso_bruto_total": None, "volumes_total": None, "quantidade_total": None, "ncms": [], "itens": [],
    "inconsistencias_internas": [], "emitente_assinatura": "Harbor Light Trading Ltd.",
    "empresa_cabecalho": "Kestrel Valve Works",
}


def _cli_devolve(monkeypatch, extracao: dict) -> None:
    resultado = {"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(extracao), "usage": {}}
    saida = SimpleNamespace(stdout=json.dumps(resultado), stderr="", returncode=0)
    monkeypatch.setattr(ler_pelo_claude_code.subprocess, "run", lambda *a, **k: saida)


def test_le_a_empresa_do_cabecalho_ao_lado_de_quem_assina(monkeypatch, tmp_path: Path):
    caminho = tmp_path / "invoice.pdf"
    caminho.write_bytes(b"%PDF-1.4 teste")
    arquivo = ArquivoEntrada(id="a1", nome="invoice.pdf", caminho=caminho, media_type="application/pdf")
    _cli_devolve(monkeypatch, {"documentos": [DOCUMENTO]})

    extracoes, _ = ler_pelo_claude_code.extrair_arquivos([arquivo])

    doc = extracoes["a1"].documentos[0]
    assert (doc.empresa_cabecalho, doc.emitente_assinatura) == ("Kestrel Valve Works", "Harbor Light Trading Ltd.")


def test_resposta_sem_o_campo_fica_sem_empresa_do_cabecalho(monkeypatch, tmp_path: Path):
    caminho = tmp_path / "pl.pdf"
    caminho.write_bytes(b"%PDF-1.4 teste")
    arquivo = ArquivoEntrada(id="a1", nome="pl.pdf", caminho=caminho, media_type="application/pdf")
    _cli_devolve(monkeypatch, {"documentos": [{k: v for k, v in DOCUMENTO.items() if k != "empresa_cabecalho"}]})

    extracoes, _ = ler_pelo_claude_code.extrair_arquivos([arquivo])

    assert extracoes["a1"].documentos[0].empresa_cabecalho is None


def test_prompt_pede_o_campo_e_nao_acusa_cabecalho_diferente_de_quem_assina():
    assert '"empresa_cabecalho"' in SISTEMA
    secao = PROMPT_SISTEMA.split("## 3. Inconsistências internas")[1]
    procuramos, nao_entra = secao.split("Não entra")
    assert "assina" not in procuramos
    assert "`empresa_cabecalho`" in nao_entra
