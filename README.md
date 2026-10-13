# compararDocs — backend

API que lê Invoice, Packing List e BL/AWB/CRT com a Claude API e aponta o que diverge entre eles. A tela fica em `CompararDocs-Frontend`.

**Stack:** Python 3.12 · FastAPI · Postgres (SQLModel) · MongoDB · SDK `anthropic` · uv · pytest

## Rodar

```bash
cp .env.example .env        # preencha ANTHROPIC_API_KEY
docker compose up -d        # Postgres e MongoDB locais
uv sync
uv run fastapi dev app/main.py
```

Documentação interativa em http://localhost:8000/docs. Sem chave, sobe em **modo mock** (valores fixos, sem custo).

## Configuração (`.env`)

| Variável | Padrão | O quê |
|---|---|---|
| `ANTHROPIC_API_KEY` | vazio | Chave da Anthropic. Sem ela, modo mock. |
| `EXTRATOR_MODO` | `auto` | `auto`, `claude`, `mock` ou `claude_code` (CLI do Claude Code, sem gastar a API; só teste local). |
| `MODELO_CLAUDE` | `claude-opus-5-5` | Modelo da leitura. |
| `DATABASE_URL` | Postgres do `docker-compose.yaml` | Análises e arquivos (`postgresql+psycopg://…`). |
| `MONGO_URL` / `MONGO_DB` | usuário da aplicação no MongoDB do `docker-compose.yaml` / `comparardocs` | Resultado de cada análise e extração de cada arquivo. |
| `STORAGE_DIR` | `storage/` | Arquivos enviados. |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Origens liberadas (JSON). |
| `MAX_ARQUIVOS` / `MAX_TAMANHO_MB` | `20` / `32` | Limites por análise. |

## Endpoints

| Método e caminho | O quê |
|---|---|
| `GET /api/health` | Status e modo do extrator. |
| `POST /api/analises` | Cria a análise (`multipart`: `arquivos`, `processo`, `modalidade`). Responde `202` e processa em segundo plano. |
| `GET /api/analises` | Lista paginada, mais recentes primeiro, com a contagem por filtro (`usuario_id`, `status`, `q`, `limit`, `offset`). |
| `GET /api/analises/{id}` | Andamento, resultado, arquivos e custo. |
| `GET /api/analises/{id}/arquivos/{arquivo_id}` | Arquivo original. |

Aceita PDF, JPG, PNG, `.docx` e `.xlsx`. Tipos de entrada e saída: `app/schemas.py`. Ainda sem login.

## Como funciona

1. Recebe os arquivos, salva e responde na hora.
2. O Claude **só extrai** os dados, um arquivo por chamada.
3. O Python normaliza e **compara**: pesos, volumes, quantidade, NCM, nº da invoice, PO, partes, portos, incoterm, moeda e itens.
4. Grava no MongoDB a extração de cada arquivo e o resultado da análise e, no Postgres, o status (`OK`, `DIVERGENTE` ou `INCOMPLETO`), o total de divergências e o custo.

## Bancos

| Onde | O quê |
|---|---|
| Postgres | Uma linha por análise e por arquivo: quem enviou, status, datas, contadores e custo. É o que a listagem filtra, conta e pagina. |
| MongoDB, coleção `resultados` | Um documento por análise, com o mesmo id dela: o resultado que a tela mostra. |
| MongoDB, coleção `extracoes` | Um documento por arquivo, com o mesmo id dele: o que foi lido, para auditoria. |
| `storage/` | Os arquivos enviados. |

As tabelas e o usuário da aplicação no MongoDB são criados na primeira subida. Enquanto o projeto está em validação, mudança de esquema não tem migração: recria-se o banco local (`docker compose down -v && docker compose up -d`).

Em produção:

- Senhas próprias (as do `docker-compose.yaml` são para uso local) e, no Postgres, usuário da aplicação que não seja o administrador.
- Volume persistente e cópia de segurança dos dois bancos (`pg_dump`, `mongodump`).
- MongoDB em nó único funciona; para alta disponibilidade, conjunto de réplicas (com `replicaSet` na `MONGO_URL`).

## Testes

```bash
uv run pytest -q    # não chama a API
```

## Estrutura

| Caminho | O quê |
|---|---|
| `app/main.py`, `app/config.py` | App e configuração. |
| `app/routes/analises.py` | Endpoints e tarefa em segundo plano. |
| `app/db.py`, `app/models.py` | Postgres: conexão e tabelas (criadas na subida), com restrições e índices. |
| `app/mongo.py` | MongoDB: coleções `resultados` (por análise) e `extracoes` (por arquivo), com os mesmos ids do Postgres. |
| `docker/` | Arquivos usados pelo `docker-compose.yaml` (criação do usuário da aplicação no MongoDB). |
| `app/schemas.py` | Tipos da API, da extração e do resultado. |
| `app/services/conversor.py` | Arquivo → conteúdo enviado ao Claude. |
| `app/services/extrator.py`, `prompts.py` | Chamada à API e instruções. |
| `app/services/extrator_claude_code.py` | A mesma leitura pela CLI do Claude Code (teste local). |
| `app/services/normalizacao.py`, `comparador.py` | Regras de comparação. |
| `app/services/pipeline.py` | Orquestra extração e comparação. |

Arquivos enviados ficam em `storage/`, fora do git. Regras para mexer no código: `AGENTS.md`.
