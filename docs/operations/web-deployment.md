# Деплой веб-морды диспетчерской на VPS

Этот документ описывает, как поднять веб-интерфейс (React + FastAPI) на том же VPS,
где уже живёт OpenClaw + Agent News. Веб-морда **только читает** общую SQLite-базу
(`data/news_bot.db`) — никакие кроны и Telegram-бот не трогаются.

## Архитектура

```
                ┌─────────────────────────────────────────┐
                │   VPS  (там же, где OpenClaw)           │
                │                                         │
   Internet ──▶ │  nginx (host, 80/443, basic auth + TLS) │
                │     │                                   │
                │     ├─▶ 127.0.0.1:8080  agent-news-web-ui   (SPA, nginx)
                │     └─▶ 127.0.0.1:8765  agent-news-web-api  (FastAPI)
                │                                          │
                │       /home/user1/gosb_bot/data/news_bot.db ◀── cron
                └─────────────────────────────────────────┘
```

- Оба контейнера слушают **только loopback** — наружу торчит только хостовый nginx.
- БД монтируется внутрь контейнера **read-only** (`:ro`) — даже если API
  случайно попытается записать, sqlite отдаст ошибку.
- На стороне nginx добавлен Basic Auth, рекомендуется TLS через certbot.

## 1. Требования на VPS

- Linux + systemd (Ubuntu 22.04+ / Debian 12+ проверял разработчик).
- Docker и docker compose plugin (`docker --version`, `docker compose version`).
  Альтернатива: запуск API через systemd, фронт собрать локально и выложить
  файлы — см. раздел «Без Docker».
- nginx (`nginx -v`).
- certbot для Let's Encrypt (`apt install certbot python3-certbot-nginx`).
- `apache2-utils` для `htpasswd` (Basic Auth).

## 2. Порты

| Что | Где | Открыть наружу? |
| --- | --- | --- |
| `agent-news-web-api` | `127.0.0.1:8765` | **Нет**. |
| `agent-news-web-ui` | `127.0.0.1:8080` | **Нет**. |
| хостовый nginx | `0.0.0.0:80` / `0.0.0.0:443` | Да. |

В фаерволе (`ufw`/security group у провайдера) откройте только **80** и **443**:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status
```

## 3. Конфигурация репозитория

```bash
cd /home/user1
git clone https://github.com/slerner007-sl/agent_news.git gosb_bot_web  # или подтянуть в существующий каталог
cd gosb_bot_web
git checkout claude/happy-meitner-Zxk0X
```

Скопируйте пример переменных и поправьте путь к боевой БД:

```bash
cp deploy/web/.env.example deploy/web/.env
nano deploy/web/.env
```

Минимум, что меняем:

- `AGENT_NEWS_DB_HOST_PATH=/home/user1/gosb_bot/data` — каталог, где лежит
  боевая `news_bot.db` (рядом с агент-ньюс кроном).
- При желании заполняем `AGENT_NEWS_WEB_USER` / `AGENT_NEWS_WEB_PASSWORD`,
  если хочется двойную защиту (на уровне API дополнительно к nginx).

## 4. Запуск через Docker

```bash
cd /home/user1/gosb_bot_web
docker compose -f deploy/web/docker-compose.yml --env-file deploy/web/.env up -d --build
docker compose -f deploy/web/docker-compose.yml ps
docker compose -f deploy/web/docker-compose.yml logs -f --tail=100 agent-news-web-api
```

Проверка изнутри VPS:

```bash
curl -sS http://127.0.0.1:8765/health | jq
curl -sSI http://127.0.0.1:8080/
```

`/health` отдаёт `status: ok` и путь к БД. Если `db_exists: false` — путь в
`.env` неверный.

## 5. Hostовый nginx и Basic Auth

1. Создаём htpasswd:
   ```bash
   sudo htpasswd -c /etc/nginx/agent-news.htpasswd radar    # дальше — без -c, чтобы не затирать
   ```
2. Кладём конфиг сайта:
   ```bash
   sudo cp deploy/web/nginx-host.conf.example /etc/nginx/sites-available/agent-news-web
   sudo nano /etc/nginx/sites-available/agent-news-web   # подставить server_name
   sudo ln -s /etc/nginx/sites-available/agent-news-web /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   ```
3. Выпускаем сертификат (certbot сам перепишет vhost):
   ```bash
   sudo certbot --nginx -d radar.example.com
   sudo systemctl reload nginx
   ```

Готово — `https://radar.example.com` спросит логин/пароль и покажет диспетчерскую.

## 6. Без Docker (systemd + nginx + статика)

Если на VPS нет Docker или не хочется его ставить:

```bash
# 1. API через systemd
sudo cp deploy/web/systemd/agent-news-web-api.service /etc/systemd/system/
sudo nano /etc/systemd/system/agent-news-web-api.service   # выставить User/пути
pip3 install --user fastapi 'uvicorn[standard]' python-multipart
sudo systemctl daemon-reload
sudo systemctl enable --now agent-news-web-api
sudo systemctl status agent-news-web-api

# 2. Фронт — собираем локально и кладём готовые файлы
cd web
npm install
VITE_API_BASE="" npm run build
sudo mkdir -p /var/www/agent-news-web
sudo rsync -a --delete dist/ /var/www/agent-news-web/
```

В nginx-конфиге замените блок `location /` на `root /var/www/agent-news-web; try_files $uri /index.html;`
и проксируйте `/api` и `/health` на `127.0.0.1:8765`.

## 7. Обновление

```bash
cd /home/user1/gosb_bot_web
git fetch origin
git checkout claude/happy-meitner-Zxk0X
git pull --ff-only

# Docker:
docker compose -f deploy/web/docker-compose.yml --env-file deploy/web/.env up -d --build

# systemd-вариант:
sudo systemctl restart agent-news-web-api
cd web && npm install && npm run build && sudo rsync -a --delete dist/ /var/www/agent-news-web/
```

## 8. Откат

Docker-вариант (вернуть предыдущий тег/коммит):

```bash
git checkout <prev-commit>
docker compose -f deploy/web/docker-compose.yml --env-file deploy/web/.env up -d --build
```

systemd-вариант:

```bash
sudo systemctl stop agent-news-web-api
git checkout <prev-commit>
sudo systemctl start agent-news-web-api
```

В обоих случаях боевая БД не задета, поэтому откат безопасен.

## 9. Чек-лист после деплоя

- [ ] `curl https://radar.example.com/health` отвечает `200 ok`.
- [ ] Логин/пароль из nginx работает.
- [ ] На странице **Сводка** видны цифры — значит API читает БД.
- [ ] В **Новостях** появляется поток с фильтрами по ГОСБ.
- [ ] В **Новостях** кнопки лайк/дизлайк/комментарий работают.
- [ ] В **Инсайтах** видны управленческие сигналы (если они уже сгенерированы).
- [ ] **База знаний** — кнопка «Загрузить» → документ появляется в списке.
- [ ] **Агент** — отправка сообщения, ответ приходит (может занять до 4 минут).
- [ ] SSE: новости/инсайты появляются без перезагрузки страницы.
- [ ] `journalctl -u agent-news-web-api` — чисто, без ошибок.

## 10. Что делает эта диспетчерская

- Показывает новости, инсайты, фидбек, базу знаний (read).
- Принимает обратную связь (лайк/дизлайк/комменты) — пишет в ту же БД,
  в том же формате, что и Telegram-плагин.
- Загружает документы (метрики, методология) в базу знаний.
- Чат с OpenClaw-агентом через subprocess.
- Обновления в реальном времени через SSE.

## 11. Что НЕ делает (важно)

- Не запускает парсеры и cron-пайплайн.
- Не отправляет ничего в Telegram.
- Не выдаёт «сырые» секреты (`llm_raw_json` и сессия в БД остаются на сервере).

Если потребуется ручной запуск парсинга или редактирование ГОСБов — это
по-прежнему делается через `scripts/` и существующий Telegram-бот.
