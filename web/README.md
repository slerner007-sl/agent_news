# Agent News — веб-диспетчерская

React + Vite + Ant Design. Визуальный стиль (Apple-подобный) перенят из
прототипа `radar-info` и адаптирован к домену Agent News: новости, инсайты,
ГОСБы, обратная связь, база знаний.

## Локальный запуск

```bash
cd web
npm install
cp .env.example .env   # при необходимости поправьте VITE_API_PROXY
npm run dev            # http://localhost:5173
```

Параллельно нужно поднять API:

```bash
# из корня репозитория
PYTHONPATH=src python3 -m agent_news.web   # слушает 0.0.0.0:8765
```

Dev-сервер Vite автоматически проксирует `/api/*` и `/health` на API.

## Production-сборка

```bash
npm run build           # dist/
```

Получившийся каталог `dist/` отдаёт nginx (см. `deploy/web/Dockerfile.frontend`
или раздел «Без Docker» в `docs/operations/web-deployment.md`).

## Структура

```
web/
├── index.html
├── package.json
├── vite.config.ts
└── src/
    ├── App.tsx               – маршруты + тема antd
    ├── main.tsx              – точка входа React
    ├── api/client.ts         – axios + типы
    ├── layout/AppHeader.tsx  – sticky-хедер со статусом API
    ├── pages/                – Dashboard / News / Insights / Gosbs / Feedback / Knowledge / Settings
    └── styles/global.css     – Apple-подобные токены и базовые стили
```

Никаких бизнес-операций фронт не делает — только GET'ы к
`/api/v1/{news,insights,gosbs,feedback,knowledge,stats}` и `/health`.
