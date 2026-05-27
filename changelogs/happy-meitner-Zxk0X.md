# happy-meitner-Zxk0X — веб-морда диспетчерской

## What

Подключил визуальный слой (веб-морда) поверх существующей диспетчерской
Agent News / OpenClaw. За основу взят визуальный стиль и структура из
прототипа `radar-info` (React + Vite + Ant Design, Apple-подобная тема,
sticky-хедер, layout страниц), но переписан под домен Agent News:

- **Сводка** — карточки по ГОСБ / новостям / инсайтам / отзывам / знаниям,
  разбивка по приоритетам, последние запуски дайджеста, гистограмма
  потока новостей по дням.
- **Новости** — фильтры по ГОСБ, горизонту, флаг «только релевантные»,
  поиск; для каждой новости показаны классификации LLM, отправки и реакции.
- **Инсайты** — карточки с приоритетом/типом/статусом, связанными новостями,
  метриками, реакциями пользователей.
- **ГОСБ / Обратная связь / База знаний / Настройки** — табличные/карточные
  представления существующих сущностей.

Backend — лёгкий FastAPI, читающий **только** существующую `data/news_bot.db`
через тот же путь, что и runtime-код (`agent_news.db.DB_PATH`). Запись
не делается ни в одном эндпоинте. Опционально поднимается HTTP Basic Auth
на уровне API (помимо nginx).

## Where

- `src/agent_news/web/` — FastAPI-приложение, репозиторий запросов
  (`repository.py`), роуты (`routes/{news,insights,gosbs,feedback,knowledge,stats}.py`),
  Basic-auth dependency, entrypoint `python -m agent_news.web`.
- `web/` — фронт на React 18 + Vite + Ant Design 5 (`package.json`, `vite.config.ts`,
  `tsconfig*.json`, `src/App.tsx`, `src/pages/*.tsx`, `src/layout/AppHeader.tsx`,
  `src/api/client.ts`, `src/styles/global.css`).
- `deploy/web/` — `Dockerfile.backend`, `Dockerfile.frontend` (multi-stage:
  Node build → nginx:alpine), `docker-compose.yml` (оба сервиса слушают
  только loopback), `nginx-host.conf.example` (TLS + Basic Auth),
  `nginx-frontend.conf` (SPA fallback), `systemd/agent-news-web-api.service`,
  `requirements-web.txt`, `.env.example`.
- `docs/operations/web-deployment.md` — пошаговая инструкция деплоя на VPS
  (порты, фаервол, htpasswd, certbot, обновление, откат, чек-лист).
- `tests/test_web_api.py` — интеграционный smoke-test всех эндпоинтов и
  Basic-auth гейта.
- `web/README.md` — короткая справка по фронту (dev / build / структура).

## Verify

Backend:

```bash
PYTHONPATH=src python3 -m py_compile src/agent_news/*.py \
    src/agent_news/web/*.py src/agent_news/web/routes/*.py
PYTHONPATH=src python3 tests/test_web_api.py        # «web api ok»
PYTHONPATH=src python3 tests/test_holdings_loader.py
PYTHONPATH=src python3 tests/test_run_id.py
PYTHONPATH=src python3 tests/test_insights.py
PYTHONPATH=src python3 -m agent_news.web            # 0.0.0.0:8765
```

Frontend:

```bash
cd web
npm install
npm run build                                       # → web/dist/
npm run dev                                         # http://localhost:5173
```

Полный стек на VPS:

```bash
cp deploy/web/.env.example deploy/web/.env          # выставить AGENT_NEWS_DB_HOST_PATH
docker compose -f deploy/web/docker-compose.yml --env-file deploy/web/.env up -d --build
curl -sS http://127.0.0.1:8765/health
```

## Issues

- Боевая `news_bot.db` лежит на VPS по пути `/home/user1/gosb_bot/data/news_bot.db`
  (захардкожено в `src/agent_news/bot_handler.py`). В compose-файле этот
  путь задаётся через `AGENT_NEWS_DB_HOST_PATH` и монтируется read-only.
- Фронт собирается в один чанк ~1 МБ (antd подтянут целиком). При желании
  можно поделить на чанки — это уже косметика, на UX не влияет.
- Bundle не подключает Leaflet/Chart.js из прототипа radar-info: для текущего
  набора экранов достаточно нативного гистограмм-блока и таблиц antd.

## Next

После деплоя на VPS пользователь потыкает интерфейс и пришлёт правки.
Возможные дальнейшие шаги (не делаю до фидбэка):

- Дашборд по конкретному ГОСБ (drill-down с одной страницы).
- Карта точек и индикаторов из плагина 2GIS (опционально, если потребуется).
- Управляющие действия (запуск парсинга, статус ран-а) — это нужно делать
  через очередь к существующим скриптам и тщательно прятать за nginx ACL.
