# TripForge

CLI-ассистент для планирования поездки: сбор фактов из туристических API, RAG на ChromaDB, маршрут по дням и смета. Оркестрация — **LangGraph** + **Deep Agents**, LLM — локальная **Ollama**, travel-tools также через **MCP**, на критических шагах — **Human-in-the-Loop**.


## Требования

- Python ≥ 3.13
- [uv](https://docs.astral.sh/uv/) — менеджер зависимостей
- [Ollama](https://ollama.com/) — локально, chat-модель с **tool calling** и отдельная embed-модель

## Быстрый старт

### 1. Зависимости проекта

```bash
# в корне репозитория
uv init --name tripforge
uv add langchain langchain-ollama langgraph langgraph-checkpoint-sqlite \
  deepagents langfuse pydantic python-dotenv httpx chromadb langchain-chroma \
  mcp langchain-mcp-adapters
uv add --dev ruff pytest

uv sync
```

### 2. Ollama

```bash
ollama pull qwen3:32b          # или ваша chat-модель с tool calling
ollama pull nomic-embed-text   # embeddings для Chroma

ollama list
# curl http://localhost:11434/api/tags
```

### 3. Переменные окружения

```bash
cp .env.example .env
```

Заполните минимум:

- `NOMINATIM_USER_AGENT` — обязателен для Nominatim (формат: `App/1.0 (contact@example.com)`)
- `OPENTRIPMAP_API_KEY` — ключ с [OpenTripMap](https://dev.opentripmap.org/) (для POI)
- `OLLAMA_MODEL`, `OLLAMA_EMBED_MODEL` — имена скачанных моделей

Опционально: `LANGFUSE_*` для трейсинга.

### 4. Проверка окружения

```bash
uv run python -c "import langchain, langgraph, deepagents, chromadb; print('ok')"
```

### 5. Запуск (после реализации `main.py`)

```bash
uv sync
uv run python main.py
```

Resume сессии с тем же `trip_id`:

```bash
uv run python main.py --trip-id <uuid>
```

## Переменные `.env`

| Переменная | Назначение |
|------------|------------|
| `OLLAMA_URL` | URL Ollama (по умолчанию `http://localhost:11434`) |
| `OLLAMA_MODEL` | Chat-модель с tool calling |
| `OLLAMA_MODEL_FALLBACK` | Запасная модель |
| `OLLAMA_EMBED_MODEL` | Модель embeddings (Chroma) |
| `CHROMA_PERSIST_DIR` | Каталог Chroma (по умолчанию `./chroma`) |
| `OPENTRIPMAP_API_KEY` | API key OpenTripMap |
| `NOMINATIM_USER_AGENT` | User-Agent для Nominatim |
| `LANGFUSE_PUBLIC_KEY` | Langfuse (опционально) |
| `LANGFUSE_SECRET_KEY` | Langfuse (опционально) |
| `LANGFUSE_HOST` | Langfuse host (опционально) |
| `USE_MCP_TOOLS` | `true` — API tools через MCP; `false` — in-process (по умолчанию) |
| `MCP_TRIPFORGE_COMMAND` | Команда запуска MCP-сервера (напр. `uv run tripforge-mcp`) |

## MCP (Model Context Protocol)

Этап 4 проекта — работа с MCP:

1. **MCP-сервер** — публикует travel tools (`geocode_city`, `fetch_weather`, POI, wiki) для Cursor и агента:
   ```bash
   uv run tripforge-mcp
   ```

2. **Cursor** — скопируйте `.cursor/mcp.json.example` → `.cursor/mcp.json` и перезапустите MCP в IDE.

3. **Агент через MCP**:
   ```bash
   USE_MCP_TOOLS=true uv run python main.py
   ```

## Структура проекта

```
.
  main.py              # CLI
  graph.py             # LangGraph (HITL macro)
  agent.py             # Deep Agent
  hitl.py              # Human-in-the-Loop UI
  models.py            # Pydantic-модели
  prompts.py           # System prompts
  rag.py               # Chroma ingest + search
  mcp_client.py        # MCP-клиент для агента
  mcp_server/          # MCP-сервер (stdio)
  tools/               # API tools (общая логика для MCP и @tool)
  memory/              # Память между сессиями
  trips/<trip_id>/     # Артефакты поездки (gitignore)
  chroma/              # Векторное хранилище (gitignore)
  checkpoints.sqlite   # LangGraph checkpoint (gitignore)
```

## Внешние API

| Сервис | Ключ | Лимиты |
|--------|------|--------|
| Ollama | — | Локально |
| Open-Meteo | — | Разумное использование |
| Nominatim | User-Agent | 1 req/s |
| Wikipedia REST | — | Разумное использование |
| OpenTripMap | API key | 5000 req/day, **non-commercial** |

OpenTripMap используется в учебных/portfolio целях (non-commercial license).

## Smoke-тест Ollama

После реализации `scripts/smoke_ollama.py`:

```bash
uv run python scripts/smoke_ollama.py
```

Проверяет, что chat-модель вызывает tools (критично для Deep Agents).
