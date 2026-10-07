# compararDocs — backend

Contexto e como rodar: `README.md`.

## Conferir

```bash
uv run pytest -q
```

## Regras

- O modelo só extrai; a comparação é código Python determinístico, com teste.
- `app/schemas.py` é a fonte da verdade dos tipos. Mudou tipo da API, muda `src/types/api.ts` no frontend.
- Não mudar a assinatura de `pipeline.processar`.
- Exemplos do prompt (`prompts.py` e descrições em `schemas.py`) são inventados: nunca usar dados dos casos de teste.
- Mudou prompt ou schema da extração, o acerto precisa ser medido de novo.
- Servidor com um processo só (a leitura roda em segundo plano dentro dele).
- Coluna nova no banco entra em `_adicionar_colunas_novas()` (`app/db.py`).

## Custo e dados

- Chamada real à API gasta crédito: só com pedido explícito. Para desenvolver, `EXTRATOR_MODO=mock`.
- `.env`, `data/` e `storage/` nunca vão para o git.
- Dado de documento real (empresa, produto, nº de documento, endereço) não entra em código, teste, comentário ou log: usar dado inventado. O que só serve nesta máquina fica em `avaliacao/` e `tests/test_casos_reais.py`, fora do git.

## Convenções

- Nomes e mensagens em português; mensagens de erro prontas para o usuário, sem stack trace.
- Código simples: funções pequenas, sem abstração especulativa.
- Dependências com `uv add`; `uv.lock` versionado.
- Commits: `tipo(escopo): descrição` (`feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`). Sem `Co-Authored-By`.
- Não copiar código de outros repositórios.
