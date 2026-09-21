"""Общие тексты, формат списков и вспомогательные функции хендлеров."""

from __future__ import annotations

from html import escape

from aiogram.enums import ParseMode
from aiogram.types import Message

from bot.audit.models import AuditEntry
from bot.audit.repository import AuditRepository
from bot.db.models import Task
from bot.db.tasks import LIST_LIMIT

MAX_MESSAGE_LEN = 4000

NO_ACCESS_TEXT = (
    "Пока нет доступных задач. Добавьте меня в чат или напишите /add."
)

GROUP_START_TEXT = (
    "Привет! Я бот для сбора идей и задач команды.\n\n"
    "Пишите <code>/add текст</code>, я сохраню."
)

PRIVATE_START_TEXT = (
    "Привет! Я бот для сбора идей и задач команды.\n\n"
    "Напишите /help, чтобы увидеть все команды."
)

HELP_TEXT = (
    "Привет! Я бот для сбора идей и задач команды.\n\n"
    "<b>В группе</b> работают только /start и /add.\n"
    "<b>В личке</b> видны задачи всех чатов, где вы состоите.\n\n"
    "<b>Команды в личке:</b>\n"
    "<code>/add текст</code> — добавить задачу в этот личный чат\n"
    "<code>/list</code> — открытые задачи доступных чатов\n"
    "<code>/search текст</code> — поиск по доступным чатам\n"
    "<code>/done ID</code> — закрыть задачу (автор или админ чата)\n"
    "<code>/delete ID</code> — удалить задачу (только админ чата)\n"
    "<code>/export csv</code> — выгрузить доступные задачи в CSV\n"
    "<code>/export md</code> — выгрузить доступные задачи в Markdown\n"
    "<code>/stats</code> — статистика по доступным чатам\n"
    "<code>/audit</code> — журнал действий (если вы админ хотя бы одного чата)\n"
    "<code>/chats</code> — список доступных чатов и ваша роль\n\n"
    "В группе: <code>/add@bot текст</code>."
)


def format_task_line(task: Task) -> str:
    """Собрать HTML-строку задачи без названия чата."""
    username = task["username"]
    if username:
        author = f"@{escape(username)}"
    else:
        author = f"id:{task['user_id']}"
    text = escape(task["text"])
    created = escape(str(task["created_at"]))
    return f"<b>#{task['id']}</b> | {created} | {author} | {text}"


def format_task_block(task: Task, chat_title: str) -> str:
    """Формат задачи для лички: ID, чат, дата, автор и текст."""
    username = task["username"]
    if username:
        author = f"@{escape(username)}"
    else:
        author = f"id:{task['user_id']}"
    date = escape(str(task["created_at"])[:10])
    title = escape(chat_title)
    text = escape(task["text"])
    return f"<b>#{task['id']}</b> [{title}] {date} {author}\n{text}"


def split_telegram_messages(text: str, max_len: int = MAX_MESSAGE_LEN) -> list[str]:
    """Разбить текст на части, не превышающие лимит Telegram."""
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0

    for line in text.split("\n"):
        if len(line) > max_len:
            flush()
            for index in range(0, len(line), max_len):
                chunks.append(line[index : index + max_len])
            continue

        extra = len(line) + (1 if current else 0)
        if current_len + extra > max_len:
            flush()
            extra = len(line)
        current.append(line)
        current_len += extra

    flush()
    return chunks


def build_task_list_text(
    tasks: list[Task],
    *,
    title: str,
    has_more: bool,
    chat_titles: dict[int, str] | None = None,
) -> str:
    """Собрать текст списка задач с заголовком и подсказкой про /export."""
    lines = [title, ""]
    if chat_titles is None:
        lines.extend(format_task_line(task) for task in tasks)
    else:
        blocks = [
            format_task_block(task, chat_titles.get(task["chat_id"], str(task["chat_id"])))
            for task in tasks
        ]
        lines.append("\n\n".join(blocks))
    if has_more:
        lines.append("")
        lines.append(
            f"Показаны последние {LIST_LIMIT} записей. "
            "Остальные можно выгрузить через /export."
        )
    return "\n".join(lines)


async def send_html_parts(message: Message, text: str) -> None:
    """Отправить HTML-текст одним или несколькими сообщениями."""
    for part in split_telegram_messages(text):
        await message.answer(part, parse_mode=ParseMode.HTML)


def parse_task_id(raw: str | None) -> int | None:
    """Разобрать положительный ID задачи из аргументов команды."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        task_id = int(text.split()[0])
    except ValueError:
        return None
    if task_id <= 0:
        return None
    return task_id


async def write_audit(
    audit: AuditRepository,
    message: Message,
    action: str,
    target_id: int | None = None,
    details: str | None = None,
    chat_id: int | None = None,
) -> None:
    """Записать действие в журнал, если известен отправитель."""
    user = message.from_user
    if user is None:
        return
    audit_chat_id = message.chat.id if chat_id is None else chat_id
    await audit.log_action(
        chat_id=audit_chat_id,
        user_id=user.id,
        username=user.username,
        action=action,
        target_id=target_id,
        details=details,
    )


async def write_audit_for_chats(
    audit: AuditRepository,
    message: Message,
    action: str,
    chat_ids: list[int],
    target_id: int | None = None,
    details: str | None = None,
) -> None:
    """Записать одно действие по каждому затронутому чату."""
    for cid in chat_ids:
        await write_audit(
            audit,
            message,
            action,
            target_id=target_id,
            details=details,
            chat_id=cid,
        )


def format_audit_line(entry: AuditEntry, chat_title: str | None = None) -> str:
    """Собрать строку журнала: дата | кто | действие [| Чат: название]."""
    if entry["username"]:
        who = f"@{entry['username']}"
    else:
        who = f"id:{entry['user_id']}"

    action = entry["action"]
    target_id = entry["target_id"]
    details = entry["details"] or ""

    if action in {"add", "done", "delete"} and target_id is not None:
        what = f"{action} #{target_id}"
    elif action == "export":
        what = f"export {details}".strip()
    elif action == "search":
        what = f"search {details}".strip()
    elif action == "denied":
        what = f"denied {details}".strip()
    elif target_id is not None:
        what = f"{action} #{target_id}"
    else:
        what = action

    line = f"{entry['created_at']} | {who} | {what}"
    if chat_title:
        line = f"{line} | Чат: {chat_title}"
    return line
