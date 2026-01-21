import asyncio
import json
from typing import Any, Dict, List
from collections import defaultdict

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from openai import OpenAI

from config import load_settings
from mcp_client import TOOL_NAME_TO_FUNC


settings = load_settings()

bot = Bot(token=settings.telegram_token)
dp = Dispatcher()

# Хранилище истории диалогов для каждого пользователя
# Ключ: user_id (int), значение: список сообщений (List[Dict[str, Any]])
user_conversations: Dict[int, List[Dict[str, Any]]] = defaultdict(list)

# Максимальное количество сообщений в истории (чтобы не превышать лимиты токенов)
MAX_HISTORY_MESSAGES = 20


def get_quick_menu_keyboard() -> InlineKeyboardMarkup:
    """Создать быстрое меню (inline keyboard) для быстрого доступа к функциям."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Все товары", callback_data="action_list"),
            InlineKeyboardButton(text="🔍 Поиск товара", callback_data="action_search"),
        ],
        [
            InlineKeyboardButton(text="➕ Добавить товар", callback_data="action_add"),
            InlineKeyboardButton(text="🧮 Калькулятор", callback_data="action_calc"),
        ],
        [
            InlineKeyboardButton(text="🌐 Поиск в интернете", callback_data="action_web_search"),
            InlineKeyboardButton(text="💱 Курс валют", callback_data="action_currency"),
        ],
        [
            InlineKeyboardButton(text="🌍 Переводчик", callback_data="action_translate"),
        ],
    ])
    return keyboard

# Инициализация OpenAI клиента с поддержкой ProxyAPI
openai_client_kwargs = {"api_key": settings.openai_api_key}
if settings.openai_base_url:
    openai_client_kwargs["base_url"] = settings.openai_base_url
openai_client = OpenAI(**openai_client_kwargs)


TOOLS_SPEC: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_products",
            "description": "Вернуть список всех товаров из каталога.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_product",
            "description": "Найти товары по части названия (например: 'чай').",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Часть названия товара для поиска.",
                    }
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_product",
            "description": "Добавить новый товар в каталог.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Название товара."},
                    "category": {
                        "type": "string",
                        "description": "Категория товара (например: 'фрукты').",
                    },
                    "price": {
                        "type": "number",
                        "description": "Цена товара в условных единицах.",
                    },
                },
                "required": ["name", "category", "price"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Безопасный калькулятор для арифметических выражений.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Арифметическое выражение, например '(2 + 3) * 4'.",
                    }
                },
                "required": ["expression"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_advanced",
            "description": "Расширенный калькулятор с математическими функциями (sin, cos, sqrt, log, pi, e и др.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Математическое выражение с функциями, например 'sqrt(16) + sin(pi/2)'.",
                    }
                },
                "required": ["expression"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Поиск актуальной информации в интернете через DuckDuckGo. Используй этот инструмент, когда пользователь запрашивает актуальную информацию, которую нельзя получить из базы знаний модели (например: погода, новости, текущие события, актуальные данные).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос на русском или английском языке (например: 'погода в Москве', 'курс доллара сегодня', 'новости Python').",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Максимальное количество результатов (1-10, по умолчанию 5).",
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_currency_rates",
            "description": "Получить актуальный курс валют (EUR/USD/RUB и другие).",
            "parameters": {
                "type": "object",
                "properties": {
                    "base": {
                        "type": "string",
                        "description": "Базовая валюта (по умолчанию USD).",
                    },
                    "currencies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список валют для получения курса (по умолчанию ['EUR', 'RUB']).",
                    }
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "translate_text",
            "description": "Перевести текст на указанный язык (английский, немецкий, французский, русский).",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Текст для перевода.",
                    },
                    "target_language": {
                        "type": "string",
                        "description": "Целевой язык: 'en' (английский), 'de' (немецкий), 'fr' (французский), 'ru' (русский) или названия.",
                    },
                    "source_language": {
                        "type": "string",
                        "description": "Исходный язык (по умолчанию 'auto' для автоматического определения).",
                    }
                },
                "required": ["text", "target_language"],
                "additionalProperties": False,
            },
        },
    },
]


SYSTEM_PROMPT = (
    "Ты Telegram-бот магазина товаров с расширенным функционалом. "
    "Отвечай красиво и структурировано (списки, абзацы, заголовки), но без излишней воды. "
    "Ты умеешь вызывать следующие инструменты:\n\n"
    "**Каталог товаров:**\n"
    "- list_products: показать все товары;\n"
    "- find_product: найти товары по подстроке названия;\n"
    "- add_product: добавить новый товар;\n\n"
    "**Вычисления:**\n"
    "- calculate: простой калькулятор для арифметических выражений;\n"
    "- calculate_advanced: расширенный калькулятор с функциями (sin, cos, sqrt, log, pi, e и др.);\n\n"
    "**Интернет и информация:**\n"
    "- search_web: поиск информации в интернете через DuckDuckGo. "
    "При использовании этого инструмента ВСЕГДА используй найденную информацию для ответа пользователю. "
    "Если результаты поиска содержат информацию по запросу - используй её для формирования ответа, "
    "цитируй источники (URL) и предоставляй конкретную информацию из результатов поиска;\n"
    "- get_currency_rates: получить актуальный курс валют (EUR/USD/RUB и другие);\n"
    "- translate_text: перевести текст на английский, немецкий, французский или русский.\n\n"
    "ВАЖНО: При выводе списка товаров ВСЕГДА показывай ID товара из базы данных (поле 'id'), а не нумерацию 1, 2, 3... "
    "Формат: 'ID: [id] - [название] - [цена] ₽' или 'ID [id]: [название] ([категория]) - [цена] ₽'.\n\n"
    "Пользователь может писать на обычном русском языке: "
    "'покажи все товары', 'найди чай', 'добавь товар яблоки 120 фрукт', "
    "'найди в интернете погода в Москве', 'курс доллара', 'переведи на английский привет'.\n"
    "1) Если для ответа достаточно твоих общих знаний, не вызывай инструменты.\n"
    "2) Если нужно работать с каталогом, вычислениями, поиском, курсом валют или переводом — используй соответствующий tool.\n"
    "3) Если запрос пользователя непонятен или в нём не хватает данных — задай уточняющий вопрос.\n"
    "4) Всегда формируй итоговый ответ человеку на естественном русском языке."
)


def _call_mcp_from_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Вызвать реальный MCP-инструмент на основе tool_call от модели.
    """
    func = TOOL_NAME_TO_FUNC.get(tool_name)
    if func is None:
        return {"error": f"Неизвестный инструмент: {tool_name}"}
    try:
        return func(**arguments)
    except TypeError:
        # На случай несоответствия аргументов
        return {"error": "Неверные аргументы для инструмента"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Ошибка при вызове инструмента: {exc}"}


def _clean_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Очистить историю от некорректных tool messages.
    Tool messages должны следовать за assistant messages с tool_calls.
    """
    cleaned = []
    i = 0
    while i < len(history):
        msg = history[i]
        role = msg.get("role")
        
        if role == "tool":
            # Tool message должен следовать за assistant с tool_calls
            if cleaned and cleaned[-1].get("role") == "assistant" and cleaned[-1].get("tool_calls"):
                cleaned.append(msg)
            # Иначе пропускаем tool message (некорректная структура)
        elif role in ("user", "assistant", "system"):
            cleaned.append(msg)
        # Пропускаем неизвестные роли
        i += 1
    
    return cleaned


def _trim_history_safely(history: List[Dict[str, Any]], max_size: int) -> List[Dict[str, Any]]:
    """
    Безопасно обрезать историю, не разрывая последовательности assistant -> tool messages.
    """
    if len(history) <= max_size:
        return history
    
    # Обрезаем с конца, но пропускаем tool messages без assistant
    trimmed = history[-max_size:]
    
    # Если первое сообщение - tool, ищем связанный assistant
    if trimmed and trimmed[0].get("role") == "tool":
        # Ищем предыдущий assistant с tool_calls
        start_idx = len(history) - max_size
        if start_idx > 0 and history[start_idx - 1].get("role") == "assistant" and history[start_idx - 1].get("tool_calls"):
            # Включаем assistant в начало
            trimmed.insert(0, history[start_idx - 1])
            # Удаляем последнее сообщение, чтобы сохранить размер
            if len(trimmed) > max_size:
                trimmed = trimmed[:max_size]
        else:
            # Нет связанного assistant - удаляем tool message
            trimmed = trimmed[1:]
    
    return trimmed


def run_llm_pipeline(user_text: str, user_id: int) -> str:
    """
    Синхронный пайплайн:
    1) Отправить запрос в LLM с описанием tools.
    2) При необходимости вызвать MCP tools.
    3) Вернуть финальный текст ответа.
    
    Args:
        user_text: Текст сообщения пользователя
        user_id: ID пользователя для хранения истории диалога
    """
    # Получаем историю диалога для пользователя
    history = user_conversations.get(user_id, [])
    
    # Очищаем историю от некорректных tool messages
    history = _clean_history(history)
    
    # Безопасно ограничиваем размер истории
    if len(history) > MAX_HISTORY_MESSAGES:
        history = _trim_history_safely(history, MAX_HISTORY_MESSAGES)
        # Дополнительная очистка после обрезки
        history = _clean_history(history)
        user_conversations[user_id] = history
    
    # Формируем список сообщений: system prompt + история + новое сообщение
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    # Добавляем историю (без system prompt, он уже есть)
    messages.extend(history)
    # Добавляем новое сообщение пользователя
    messages.append({"role": "user", "content": user_text})

    first_response = openai_client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        tools=TOOLS_SPEC,
        tool_choice="auto",
    )

    message = first_response.choices[0].message

    # Если модель не захотела вызывать инструменты — сразу возвращаем её ответ
    if not getattr(message, "tool_calls", None):
        final_text = message.content or "Извини, я не смог сформировать ответ."
        
        # Сохраняем в историю: сообщение пользователя и ответ ассистента
        user_conversations[user_id].append({"role": "user", "content": user_text})
        user_conversations[user_id].append({"role": "assistant", "content": final_text})
        
        # Безопасно ограничиваем размер истории
        if len(user_conversations[user_id]) > MAX_HISTORY_MESSAGES:
            user_conversations[user_id] = _trim_history_safely(user_conversations[user_id], MAX_HISTORY_MESSAGES)
            # Дополнительная очистка после обрезки
            user_conversations[user_id] = _clean_history(user_conversations[user_id])
        
        return final_text

    # Иначе вызываем все запрошенные инструменты
    tool_messages: List[Dict[str, Any]] = []
    for tool_call in message.tool_calls:
        tool_name = tool_call.function.name
        raw_args = tool_call.function.arguments
        try:
            arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            arguments = {}

        tool_result = _call_mcp_from_tool(tool_name, arguments or {})

        tool_messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": json.dumps(tool_result, ensure_ascii=False),
            }
        )

    # Второй ход — даём модели результаты инструментов и просим финальный ответ пользователю
    messages.append(
        {
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ],
        }
    )
    messages.extend(tool_messages)

    second_response = openai_client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
    )
    final_message = second_response.choices[0].message
    final_text = final_message.content or "Извини, я не смог сформировать ответ."
    
    # Сохраняем историю диалога для случая с вызовами инструментов
    # Добавляем сообщение пользователя
    user_conversations[user_id].append({"role": "user", "content": user_text})
    
    # Сохраняем сообщение ассистента с tool_calls
    assistant_msg = {
        "role": "assistant",
        "content": message.content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in message.tool_calls
        ],
    }
    user_conversations[user_id].append(assistant_msg)
    
    # Сохраняем результаты инструментов
    user_conversations[user_id].extend(tool_messages)
    
    # Сохраняем финальный ответ ассистента
    user_conversations[user_id].append({"role": "assistant", "content": final_text})
    
    # Безопасно ограничиваем размер истории после добавления
    if len(user_conversations[user_id]) > MAX_HISTORY_MESSAGES:
        user_conversations[user_id] = _trim_history_safely(user_conversations[user_id], MAX_HISTORY_MESSAGES)
        # Дополнительная очистка после обрезки
        user_conversations[user_id] = _clean_history(user_conversations[user_id])
    
    return final_text


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    # Очищаем историю диалога при команде /start
    user_id = message.from_user.id
    user_conversations[user_id] = []
    
    text = (
        "Привет! Я бот для работы с базой данных товаров.\n\n"
        "Я могу помочь вам:\n\n"
        "📦 Каталог товаров:\n"
        "- Показать все товары\n"
        "- Найти товары по названию\n"
        "- Добавить новый товар\n\n"
        "🧮 Вычисления:\n"
        "- Простые математические вычисления\n"
        "- Расширенный калькулятор с функциями (sin, cos, sqrt, log и др.)\n\n"
        "🌐 Интернет и информация:\n"
        "- Поиск информации в интернете (DuckDuckGo)\n"
        "- Получение актуального курса валют (EUR/USD/RUB и другие)\n\n"
        "🌍 Перевод:\n"
        "- Перевод текста на английский, немецкий, французский и русский\n\n"
        "Просто напишите мне, что вы хотите сделать, например:\n"
        "\"покажи все товары\"\n"
        "\"найди чай\"\n"
        "\"добавь товар яблоки 120 фрукт\"\n"
        "\"посчитай (2 + 3) * 4\"\n"
        "\"посчитай sqrt(16) + sin(pi/2)\"\n"
        "\"найди в интернете погода в Москве\"\n"
        "\"покажи курс доллара\"\n"
        "\"переведи на английский привет\"\n\n"
        "Также используйте быстрое меню внизу для быстрого доступа к функциям.\n\n"
        "Начнём!"
    )
    # Добавляем быстрое меню к приветственному сообщению
    keyboard = get_quick_menu_keyboard()
    await message.answer(text, reply_markup=keyboard)


@dp.message()
async def handle_message(message: Message) -> None:
    user_text = message.text or ""
    user_id = message.from_user.id

    # Выполняем LLM-пайплайн в отдельном потоке, чтобы не блокировать event loop
    reply_text = await asyncio.to_thread(run_llm_pipeline, user_text, user_id)

    # Добавляем быстрое меню к ответу
    keyboard = get_quick_menu_keyboard()
    await message.answer(reply_text, reply_markup=keyboard)


@dp.callback_query()
async def handle_callback(callback: CallbackQuery) -> None:
    """Обработчик нажатий на кнопки быстрого меню."""
    user_id = callback.from_user.id
    action = callback.data
    
    # Определяем текст запроса на основе действия
    action_texts = {
        "action_list": "покажи все товары",
        "action_search": "найди товары",
        "action_add": "добавь товар",
        "action_calc": "посчитай",
        "action_web_search": "найди в интернете",
        "action_currency": "покажи курс валют",
        "action_translate": "переведи текст",
    }
    
    user_text = action_texts.get(action, "")
    if not user_text:
        await callback.answer("Неизвестное действие")
        return
    
    # Показываем индикатор загрузки
    await callback.answer("Обрабатываю запрос...")
    
    # Выполняем LLM-пайплайн
    reply_text = await asyncio.to_thread(run_llm_pipeline, user_text, user_id)
    
    # Отправляем ответ с быстрым меню
    keyboard = get_quick_menu_keyboard()
    await callback.message.answer(reply_text, reply_markup=keyboard)


async def main() -> None:
    print(
        f"[BOT] Запуск Telegram-бота. "
        f"Модель: {settings.openai_model}, MCP сервер: {settings.mcp_server_url}"
    )
    
    # Проверка доступности MCP сервера
    import httpx
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{settings.mcp_server_url.rstrip('/')}/schema")
            response.raise_for_status()
        print(f"[BOT] MCP сервер доступен: {settings.mcp_server_url}")
    except Exception as e:
        print(
            f"[BOT] ⚠️  ВНИМАНИЕ: MCP сервер недоступен ({settings.mcp_server_url}): {e}"
        )
        print("[BOT] Убедитесь, что MCP сервер запущен (python server.py в папке mcp_server)")
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


