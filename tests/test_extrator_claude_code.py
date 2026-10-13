import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.schemas import ArquivoEntrada
from app.services import extrator_claude_code
from app.services.extrator import ErroExtracao

EXTRACAO = {"documentos": []}


@pytest.fixture
def arquivo(tmp_path: Path) -> ArquivoEntrada:
    caminho = tmp_path / "invoice.pdf"
    caminho.write_bytes(b"%PDF-1.4 teste")
    return ArquivoEntrada(id="a1", nome="invoice.pdf", caminho=caminho, media_type="application/pdf")


def cli(monkeypatch, *eventos, erro=None):
    chamadas = []

    def run(comando, **kwargs):
        chamadas.append((comando, kwargs))
        if erro:
            raise erro
        return SimpleNamespace(stdout="\n".join(json.dumps(e) for e in eventos), stderr="", returncode=0)

    monkeypatch.setattr(extrator_claude_code.subprocess, "run", run)
    return chamadas


def resultado(texto, **extra):
    uso = {"input_tokens": 2, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 30, "output_tokens": 50}
    return {"type": "result", "subtype": "success", "is_error": False, "result": texto, "usage": uso, **extra}


def test_le_o_resultado_e_soma_os_tokens_sem_custo(monkeypatch, arquivo):
    chamadas = cli(monkeypatch, {"type": "system", "subtype": "init"}, resultado(json.dumps(EXTRACAO)))

    extracoes, uso = extrator_claude_code.extrair_arquivos([arquivo])

    assert extracoes["a1"].documentos == []
    assert (uso.input_tokens, uso.output_tokens, uso.custo_usd_estimado) == (132, 50, 0.0)
    assert uso.modelo.endswith("(Claude Code)")
    comando, kwargs = chamadas[0]
    assert comando[comando.index("--tools") + 1] == ""
    mensagem = json.loads(kwargs["input"])
    assert [b["type"] for b in mensagem["message"]["content"]] == ["document", "text"]


def test_json_invalido_refaz_uma_vez_e_depois_falha(monkeypatch, arquivo):
    chamadas = cli(monkeypatch, resultado("não é json"))

    with pytest.raises(ErroExtracao, match="formato inválido"):
        extrator_claude_code.extrair_arquivos([arquivo])
    assert len(chamadas) == 2


def test_erro_devolvido_pela_cli(monkeypatch, arquivo):
    cli(monkeypatch, resultado("Limite de uso atingido", is_error=True))

    with pytest.raises(ErroExtracao, match="Limite de uso atingido"):
        extrator_claude_code.extrair_arquivos([arquivo])


def test_cli_sem_resultado(monkeypatch, arquivo):
    cli(monkeypatch, {"type": "system", "subtype": "init"})

    with pytest.raises(ErroExtracao, match="não devolveu resultado"):
        extrator_claude_code.extrair_arquivos([arquivo])


@pytest.mark.parametrize(
    ("erro", "mensagem"),
    [
        (FileNotFoundError(), "não encontrada"),
        (subprocess.TimeoutExpired(cmd="claude", timeout=1), "demorou demais"),
    ],
)
def test_cli_ausente_ou_lenta(monkeypatch, arquivo, erro, mensagem):
    cli(monkeypatch, erro=erro)

    with pytest.raises(ErroExtracao, match=mensagem):
        extrator_claude_code.extrair_arquivos([arquivo])
