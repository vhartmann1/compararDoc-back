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
- Postgres só com colunas simples: nada de JSON. O que é aninhado vai para o MongoDB (`app/mongo.py`), em duas coleções no espelho das tabelas: `resultados` (um documento por análise, mesmo id) e `extracoes` (um por arquivo, mesmo id). Grava primeiro no Mongo, depois no Postgres.
- No MongoDB, coleção separa o que é lido em momentos diferentes; o que é lido junto fica no mesmo documento. Nada de nome de campo variável (id como chave). Índice só junto com a consulta que o usa: hoje tudo é buscado pelo `_id`.
- As tabelas são criadas na subida (`app/db.py`), o que só cria tabela nova. Enquanto o projeto está em validação, os dados são descartáveis: mudou tabela ou formato de documento, muda o código e recria o banco local. Sem script de migração, campo de versão nem compatibilidade com dado antigo.
- No Postgres, valor de lista fechada (status, etapa, modalidade) tem `CHECK`; dinheiro é `numeric`; índice acompanha a consulta que o usa.
- A aplicação entra no MongoDB com usuário próprio (`readWrite` só no banco dela), nunca como administrador.

## Custo e dados

- Chamada real à API gasta crédito: só com pedido explícito. Para desenvolver, `EXTRATOR_MODO=mock`.
- `.env` e `storage/` nunca vão para o git.
- Dado de documento real (empresa, produto, nº de documento, endereço) não entra em código, teste, comentário ou log: usar dado inventado. O que só serve nesta máquina fica em `avaliacao/` e `tests/test_casos_reais.py`, fora do git.

## Convenções

- Nomes e mensagens em português; mensagens de erro prontas para o usuário, sem stack trace.
- Código simples: funções pequenas, sem abstração especulativa.
- Dependências com `uv add`; `uv.lock` versionado.
- Commits: `tipo(escopo): descrição` (`feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`). Sem `Co-Authored-By`.
- Não copiar código de outros repositórios.
