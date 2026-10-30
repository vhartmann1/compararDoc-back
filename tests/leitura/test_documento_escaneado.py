"""Marcação determinística de documento escaneado (sem chamar a API)."""

from pathlib import Path

from PIL import Image

from app.schemas import ArquivoEntrada
from app.tipos_de_arquivo import MEDIA_PDF, MEDIA_XLSX
from app.services.leitura.documento_escaneado import escaneado

TEXTO = "COMMERCIAL INVOICE No. 1234 Kestrel Valve Works Total USD 9,000.00"


def entrada(caminho: Path, media_type: str) -> ArquivoEntrada:
    return ArquivoEntrada(id="x", nome=caminho.name, caminho=caminho, media_type=media_type)


def pdf_com_texto(caminho: Path, paginas: list[str], modo: int = 0) -> Path:
    """PDF mínimo escrito à mão: uma página por texto (texto vazio = página sem camada de texto)."""
    objetos = ["<< /Type /Catalog /Pages 2 0 R >>", ""]
    filhos = []
    for texto in paginas:
        conteudo = f"BT {modo} Tr /F1 12 Tf 72 720 Td ({texto}) Tj ET".encode() if texto else b""
        n = len(objetos) + 1
        objetos.append(f"<< /Length {len(conteudo)} >>\nstream\n{conteudo.decode()}\nendstream")
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {n} 0 R "
            f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>"
        )
        filhos.append(f"{n + 1} 0 R")
    objetos[1] = f"<< /Type /Pages /Kids [{' '.join(filhos)}] /Count {len(filhos)} >>"
    saida, posicoes = b"%PDF-1.4\n", []
    for i, obj in enumerate(objetos, 1):
        posicoes.append(len(saida))
        saida += f"{i} 0 obj\n{obj}\nendobj\n".encode()
    xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    saida += "".join(f"{p:010d} 00000 n \n" for p in posicoes).encode()
    saida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    caminho.write_bytes(saida)
    return caminho


def test_pdf_com_texto_nao_e_escaneado(tmp_path):
    assert escaneado(entrada(pdf_com_texto(tmp_path / "a.pdf", [TEXTO, TEXTO]), MEDIA_PDF)) is False


def test_pdf_so_imagem_e_escaneado(tmp_path):
    caminho = tmp_path / "scan.pdf"
    Image.new("RGB", (600, 800), "white").save(caminho, "PDF")
    assert escaneado(entrada(caminho, MEDIA_PDF)) is True


def test_pdf_com_texto_so_numa_minoria_de_paginas_e_escaneado(tmp_path):
    caminho = pdf_com_texto(tmp_path / "b.pdf", [TEXTO, "", "Page 2"])
    assert escaneado(entrada(caminho, MEDIA_PDF)) is True


def test_pdf_com_ocr_invisivel_e_escaneado(tmp_path):
    caminho = pdf_com_texto(tmp_path / "ocr.pdf", [TEXTO, TEXTO], modo=3)
    assert escaneado(entrada(caminho, MEDIA_PDF)) is True


def test_jpg_e_escaneado(tmp_path):
    caminho = tmp_path / "foto.jpg"
    Image.new("RGB", (100, 100), "white").save(caminho, "JPEG")
    assert escaneado(entrada(caminho, "image/jpeg")) is True


def test_planilha_nao_e_escaneada(tmp_path):
    assert escaneado(entrada(tmp_path / "pl.xlsx", MEDIA_XLSX)) is False


def test_pdf_corrompido_fica_sem_resposta(tmp_path):
    caminho = tmp_path / "ruim.pdf"
    caminho.write_bytes(b"isto nao e um pdf")
    assert escaneado(entrada(caminho, MEDIA_PDF)) is None
