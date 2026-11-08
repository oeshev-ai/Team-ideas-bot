# Team Ideas Bot

> Telegram-бот для сбора идей и задач команды в общем чате: модерация, поиск и экспорт в CSV/Markdown.

## Проблема

Идеи команды тонут в переписке группового чата: нет единого списка, непонятно, что ещё открыто и что уже сделано. К созвону сложно быстро собрать итог, а разбор «кто закрыл / удалил задачу» превращается в ручной поиск по истории.

## Решение

Бот принимает идеи через `/add` прямо в группе. В личке участник видит задачи всех чатов, где состоит, может искать, экспортировать и закрывать свои записи; администратор чата — закрывать чужие, мягко удалять и смотреть журнал `/audit`. Всё хранится в SQLite на диске и переживает перезапуск бота.

## Что внутри

- Технологии: Python 3.10+, aiogram 3.x, aiosqlite / SQLite (WAL), python-dotenv, Docker Compose
- Архитектура: модульный пакет `bot/` — handlers → permissions/access → repositories (tasks + audit) → SQLite; работа через polling
- Деплой: Docker Compose с volume `./data` (база) и `./logs` (технический лог)

## Как запустить

```bash
git clone https://github.com/oeshev-ai/Team-ideas-bot.git
cd Team-ideas-bot
cp .env.example .env   # укажите BOT_TOKEN от @BotFather
docker compose up -d --build
```

Локально без Docker: `python -m venv .venv`, активируйте окружение, `pip install -r requirements.txt`, затем `python -m bot`.

## Результат

- Идеи из чата не теряются в ленте — единый список со статусами `open` / `done` / `deleted`
- Права совпадают с ролями Telegram (автор / администратор), без отдельной «админки» бота
- Экспорт в CSV и Markdown плюс журнал `/audit` для разбора действий
- База на диске и Docker volume — данные сохраняются между рестартами

## Контакт

Telegram: [@OEShevchenko](https://t.me/OEShevchenko)  
Email: oeshevip@yandex.ru
