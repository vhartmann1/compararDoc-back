"""Validação do tipo de arquivo no envio (sem banco nem rede)."""

import io

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.routes.analises import ASSINATURA_OLE, _validar_tipo
from app.tipos_de_arquivo import MEDIA_XLS


def envio(nome: str, conteudo: bytes, content_type: str) -> UploadFile:
    return UploadFile(io.BytesIO(conteudo), filename=nome, headers=Headers({"content-type": content_type}))


@pytest.mark.parametrize("content_type", [MEDIA_XLS, "application/octet-stream"])
def test_xls_aceito(content_type):
    assert _validar_tipo(envio("fatura.xls", ASSINATURA_OLE + b"\x00" * 8, content_type)) == (MEDIA_XLS, ".xls")


def test_xls_renomeado_recusado():
    with pytest.raises(HTTPException, match="não é um .xls válido"):
        _validar_tipo(envio("fatura.xls", b"%PDF-1.7", MEDIA_XLS))


def test_doc_antigo_continua_recusado():
    with pytest.raises(HTTPException, match="Formato antigo"):
        _validar_tipo(envio("carta.doc", b"x", "application/msword"))
