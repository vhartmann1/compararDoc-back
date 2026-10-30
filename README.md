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
| `LEITURAS_SIMULTANEAS` | `8` | Análises lidas ao mesmo tempo; as outras esperam a vez. Ajustar ao limite da API do Claude. |

## Endpoints

| Método e caminho | O quê |
|---|---|
| `GET /api/health` | Status e modo do extrator. |
| `POST /api/analises` | Cria a análise (`multipart`: `arquivos`, `processo`, `modalidade`). Responde `202` e processa em segundo plano. |
| `GET /api/analises` | Lista paginada, mais recentes primeiro, com a contagem por filtro (`usuario_id`, `status`, `q`, `limit`, `offset`). |
| `GET /api/analises/{id}` | Andamento, resultado, arquivos e custo. |
| `POST /api/analises/{id}/refazer-conferencia` | Refaz a conferência com as leituras já gravadas, sem ler de novo. |
| `GET /api/analises/{id}/arquivos/{arquivo_id}` | Arquivo original. |

Aceita PDF, JPG, PNG, `.docx` e `.xlsx`. Tipos de entrada e saída: `app/schemas.py`. Ainda sem login.

## Como funciona

O caminho de um envio, com o lugar de cada etapa:

1. **Recebe** — `app/routes/analises.py` salva os arquivos em `storage/`, responde na hora e segue em segundo plano.
2. **Lê** — `app/services/leitura/`: cada arquivo vira conteúdo (`arquivo_para_conteudo.py`), vai ao Claude com o prompt (`prompts.py`) e a resposta é validada (`formato_da_resposta.py`). O Claude **só extrai**, um arquivo por chamada. PDF com página escaneada de lado é endireitado e lido de novo (`endireitar_paginas.py`).
3. **Compara** — `app/services/comparacao/`: o Python escolhe os documentos, pareia invoice e packing list e aplica as regras de cada campo (`campos/regras_por_campo/`), dos itens (`campos/itens/`) e de coerência. Nenhuma decisão de comparação é do modelo.
4. **Grava** — `app/mongo.py` guarda a extração de cada arquivo e o resultado; `app/db.py` guarda o status (`OK`, `DIVERGENTE` ou `INCOMPLETO`), o total de divergências e o custo.
5. **Entrega** — a tela consulta `GET /api/analises/{id}` até a análise concluir.

`app/services/pipeline.py` liga as etapas 2 e 3.

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
| `app/tipos_de_arquivo.py` | Tipos MIME aceitos (PDF, imagens, Word, Excel). |
| `app/services/leitura/` | Ler os documentos: `arquivo_para_conteudo.py`, `prompts.py`, `formato_da_resposta.py`, `endireitar_paginas.py` e um leitor por modo (`ler_pela_api.py`, `ler_pelo_claude_code.py`, `ler_simulado.py`). |
| `app/services/comparacao/` | Comparar o que foi lido: `comparar_documentos.py` (entrada); `documentos/` (escolha, pareamento, colunas, versões), `normalizacao/`, `partes/` (empresas, Capital, notify, adquirente), `campos/` (com `regras_por_campo/` e `itens/`), `dentro_do_documento/` (contas e inconsistências internas) e `coerencia/`. |
| `app/services/pipeline.py` | Orquestra extração e comparação. |

Arquivos enviados ficam em `storage/`, fora do git. Regras para mexer no código: `AGENTS.md`.
