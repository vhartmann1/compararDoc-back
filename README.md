# compararDocs — backend

API que lê Invoice, Packing List e BL/AWB/CRT com a Claude API e aponta o que diverge entre eles. A tela fica em `CompararDocs-Frontend`.

**Stack:** Python 3.12 · FastAPI · Postgres (SQLModel) · SDK `anthropic` · uv · pytest

## Rodar

```bash
cp .env.example .env        # preencha ANTHROPIC_API_KEY
docker compose up -d        # Postgres local
uv sync
uv run fastapi dev app/main.py
```

Documentação interativa em http://localhost:8000/docs. Sem chave, sobe em **modo mock** (valores fixos, sem custo).

## Configuração (`.env`)

| Variável | Padrão | O quê |
|---|---|---|
| `ANTHROPIC_API_KEY` | vazio | Chave da Anthropic. Sem ela, modo mock. |
| `EXTRATOR_MODO` | `auto` | `auto`, `claude` ou `mock`. |
| `MODELO_CLAUDE` | `claude-opus-5-5` | Modelo da leitura. |
| `DATABASE_URL` | Postgres do `docker-compose.yaml` | Banco (`postgresql+psycopg://…`). |
| `STORAGE_DIR` | `storage/` | Arquivos enviados. |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Origens liberadas (JSON). |
| `MAX_ARQUIVOS` / `MAX_TAMANHO_MB` | `20` / `32` | Limites por análise. |

## Endpoints

| Método e caminho | O quê |
|---|---|
| `GET /api/health` | Status e modo do extrator. |
| `POST /api/analises` | Cria a análise (`multipart`: `arquivos`, `processo`, `modalidade`). Responde `202` e processa em segundo plano. |
| `GET /api/analises` | Lista, mais recentes primeiro (`usuario_id`, `limit`). |
| `GET /api/analises/{id}` | Andamento, resultado, arquivos e custo. |
| `GET /api/analises/{id}/arquivos/{arquivo_id}` | Arquivo original. |

Aceita PDF, JPG, PNG, `.docx` e `.xlsx`. Tipos de entrada e saída: `app/schemas.py`. Ainda sem login.

## Como funciona

1. Recebe os arquivos, salva e responde na hora.
2. O Claude **só extrai** os dados, um arquivo por chamada.
3. O Python normaliza e **compara**: pesos, volumes, quantidade, NCM, nº da invoice, PO, partes, portos, incoterm, moeda e itens.
4. Grava o resultado (`OK`, `DIVERGENTE` ou `INCOMPLETO`), o que foi extraído e o custo.

## Testes

```bash
uv run pytest -q    # não chama a API
```

## Estrutura

| Caminho | O quê |
|---|---|
| `app/main.py`, `app/config.py` | App e configuração. |
| `app/routes/analises.py` | Endpoints e tarefa em segundo plano. |
| `app/db.py`, `app/models.py` | Conexão e tabelas (criadas na subida). |
| `app/schemas.py` | Tipos da API, da extração e do resultado. |
| `app/services/conversor.py` | Arquivo → conteúdo enviado ao Claude. |
| `app/services/extrator.py`, `prompts.py` | Chamada à API e instruções. |
| `app/services/normalizacao.py`, `comparador.py` | Regras de comparação. |
| `app/services/pipeline.py` | Orquestra extração e comparação. |

Arquivos enviados ficam em `storage/`, fora do git. Regras para mexer no código: `AGENTS.md`.
