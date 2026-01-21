from typing import Any, Dict, List
import ast
import operator as op
import math
import requests

# Импорт будет выполняться динамически в функции поиска

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None

from db import list_products, find_product, add_product


# --- Безопасный калькулятор через AST ---

SAFE_OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.Mod: op.mod,
    ast.USub: op.neg,
}


def _eval_ast(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)
    if isinstance(node, ast.Constant):
        # Python 3.8+: числа попадают сюда
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Разрешены только числовые литералы")
    if isinstance(node, ast.Num):  # на случай старых версий Python
        return node.n
    if isinstance(node, ast.BinOp):
        left = _eval_ast(node.left)
        right = _eval_ast(node.right)
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"Оператор {op_type.__name__} не разрешён")
        return SAFE_OPERATORS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        operand = _eval_ast(node.operand)
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"Унарный оператор {op_type.__name__} не разрешён")
        return SAFE_OPERATORS[op_type](operand)
    raise ValueError(f"Недопустимое выражение: узел {type(node).__name__}")


def eval_expression(expression: str) -> float:
    """Безопасно вычислить арифметическое выражение."""
    try:
        parsed = ast.parse(expression, mode="eval")
        return float(_eval_ast(parsed))
    except Exception as exc:
        raise ValueError(f"Ошибка при вычислении выражения: {exc}") from exc


# --- Обёртки MCP-инструментов ---

def list_products_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """MCP tool: вернуть список товаров."""
    products = list_products()
    return {"products": products}


def find_product_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """MCP tool: найти товары по имени."""
    name = params.get("name")
    if not isinstance(name, str) or not name:
        return {"error": "Параметр 'name' (string) обязателен"}
    products = find_product(name)
    return {"products": products}


def add_product_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """MCP tool: добавить товар."""
    name = params.get("name")
    category = params.get("category")
    price = params.get("price")

    if not isinstance(name, str) or not isinstance(category, str):
        return {"error": "Параметры 'name' и 'category' должны быть строками"}
    if not isinstance(price, (int, float)):
        return {"error": "Параметр 'price' должен быть числом"}

    product = add_product(name, category, float(price))
    return {"product": product}


def calculate_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """MCP tool: безопасный калькулятор (базовые операции)."""
    expression = params.get("expression")
    if not isinstance(expression, str) or not expression.strip():
        return {"error": "Параметр 'expression' (string) обязателен"}
    try:
        result = eval_expression(expression)
        return {"result": result}
    except ValueError as exc:
        return {"error": str(exc)}


def calculate_advanced_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """MCP tool: расширенный калькулятор с математическими функциями."""
    expression = params.get("expression")
    if not isinstance(expression, str) or not expression.strip():
        return {"error": "Параметр 'expression' (string) обязателен"}
    
    # Безопасный словарь с математическими функциями
    safe_dict = {
        "__builtins__": {},
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
    }
    
    try:
        # Безопасное вычисление с использованием eval (только математические функции)
        result = eval(expression, safe_dict)
        return {"result": float(result)}
    except Exception as exc:
        return {"error": f"Ошибка при вычислении: {str(exc)}"}


def search_web_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """MCP tool: поиск информации в интернете через DuckDuckGo."""
    query = params.get("query")
    if not isinstance(query, str) or not query.strip():
        return {"error": "Параметр 'query' (string) обязателен"}
    
    max_results = params.get("max_results", 5)
    if not isinstance(max_results, int) or max_results < 1 or max_results > 10:
        max_results = 5
    
    # Динамический импорт библиотеки (чтобы точно использовать окружение, где запущен сервер)
    try:
        # Пробуем новое имя библиотеки (ddgs)
        try:
            from ddgs import DDGS
        except ImportError:
            # Пробуем старое имя (duckduckgo_search)
            from duckduckgo_search import DDGS
        print(f"[SEARCH] Библиотека импортирована, выполняю поиск: {query}")
        
        # Пробуем использовать DDGS
        ddgs = None
        results = None
        
        try:
            # Пробуем с контекстным менеджером (новые версии)
            ddgs = DDGS()
            if hasattr(ddgs, '__enter__'):
                with ddgs as d:
                    results = list(d.text(query, max_results=max_results))
            else:
                results = list(ddgs.text(query, max_results=max_results))
        except Exception as e1:
            print(f"[SEARCH] Ошибка при использовании DDGS: {e1}")
            try:
                # Пробуем без контекстного менеджера
                ddgs = DDGS()
                results = list(ddgs.text(query, max_results=max_results))
            except Exception as e2:
                print(f"[SEARCH] Ошибка при повторной попытке: {e2}")
                raise
        
        print(f"[SEARCH] Найдено результатов: {len(results) if results else 0}")
        
        if not results:
            return {
                "results": [],
                "query": query,
                "message": "По вашему запросу ничего не найдено. Попробуйте изменить формулировку."
            }
        
        formatted_results = []
        for r in results:
            # Обрабатываем разные форматы ответа от библиотеки
            if isinstance(r, dict):
                title = r.get("title") or r.get("text", "")
                body = r.get("body") or r.get("snippet", "") or r.get("description", "")
                url = r.get("href") or r.get("url", "") or r.get("link", "")
            else:
                # Если это объект с атрибутами
                title = getattr(r, "title", "") or getattr(r, "text", "")
                body = getattr(r, "body", "") or getattr(r, "snippet", "") or getattr(r, "description", "")
                url = getattr(r, "href", "") or getattr(r, "url", "") or getattr(r, "link", "")
            
            if title or body or url:
                formatted_results.append({
                    "title": str(title) if title else "",
                    "body": str(body) if body else "",
                    "url": str(url) if url else "",
                })
        
        print(f"[SEARCH] Отформатировано результатов: {len(formatted_results)}")
        
        if formatted_results:
            return {"results": formatted_results, "query": query}
        else:
            print("[SEARCH] Не удалось отформатировать результаты")
    except ImportError as e:
        print(f"[SEARCH] Библиотека не импортирована: {e}")
        # Библиотека не установлена, пробуем альтернативный метод
        pass
    except Exception as exc:
        # Ошибка при использовании библиотеки, пробуем альтернативный метод
        print(f"[SEARCH] Ошибка duckduckgo-search: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        pass
    
    # Если ничего не сработало, возвращаем ошибку
    print(f"[SEARCH] Все методы поиска не сработали для запроса: {query}")
    return {
        "error": "Поиск в интернете временно недоступен. Убедитесь, что:\n1. MCP сервер запущен из виртуального окружения\n2. Библиотека duckduckgo-search установлена: pip install duckduckgo-search\n3. Сервер перезапущен после установки библиотеки",
        "query": query
    }
    
    # Если ничего не сработало, возвращаем ошибку с инструкцией
    return {
        "error": "Не удалось выполнить поиск. Убедитесь, что MCP сервер запущен из виртуального окружения, где установлена библиотека duckduckgo-search. Установите: pip install duckduckgo-search",
        "query": query
    }


def get_currency_rates_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """MCP tool: получить курс валют (EUR/USD/RUB)."""
    base_currency = params.get("base", "USD").upper()
    target_currencies = params.get("currencies", ["EUR", "RUB"])
    
    if not isinstance(target_currencies, list):
        target_currencies = [target_currencies] if isinstance(target_currencies, str) else ["EUR", "RUB"]
    
    # Используем бесплатный API exchangerate-api.com
    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        rates = {}
        for currency in target_currencies:
            currency = currency.upper()
            if currency in data.get("rates", {}):
                rates[currency] = data["rates"][currency]
        
        return {
            "base": base_currency,
            "rates": rates,
            "date": data.get("date", ""),
        }
    except Exception as exc:
        return {"error": f"Ошибка при получении курса валют: {str(exc)}"}


def translate_text_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """MCP tool: перевести текст на указанный язык."""
    if GoogleTranslator is None:
        return {"error": "Библиотека deep-translator не установлена. Установите: pip install deep-translator"}
    
    text = params.get("text")
    target_lang = params.get("target_language", "en").lower()
    source_lang = params.get("source_language", "auto")
    
    if not isinstance(text, str) or not text.strip():
        return {"error": "Параметр 'text' (string) обязателен"}
    
    # Маппинг языков
    lang_map = {
        "en": "en",
        "english": "en",
        "английский": "en",
        "de": "de",
        "german": "de",
        "немецкий": "de",
        "fr": "fr",
        "french": "fr",
        "французский": "fr",
        "ru": "ru",
        "russian": "ru",
        "русский": "ru",
    }
    
    target_lang = lang_map.get(target_lang, target_lang)
    
    # Определяем исходный язык, если не указан
    if source_lang == "auto":
        source_lang = None  # deep-translator определит автоматически
    else:
        source_lang = lang_map.get(source_lang, source_lang)
    
    try:
        if GoogleTranslator is None:
            return {"error": "Библиотека deep-translator не установлена. Установите: pip install deep-translator"}
        
        # Если исходный язык не указан, пробуем определить автоматически
        if source_lang is None:
            # Пробуем перевести с автоопределением (deep-translator поддерживает это)
            translator = GoogleTranslator(source='auto', target=target_lang)
        else:
            translator = GoogleTranslator(source=source_lang, target=target_lang)
        
        translated_text = translator.translate(text)
        
        # Определяем исходный язык (если не был указан)
        detected_source = source_lang if source_lang else "auto"
        
        return {
            "original_text": text,
            "translated_text": translated_text,
            "source_language": detected_source,
            "target_language": target_lang,
        }
    except Exception as exc:
        return {"error": f"Ошибка при переводе: {str(exc)}"}


# --- JSON Schema описания инструментов для MCP ---

TOOLS_JSON_SCHEMA: Dict[str, Any] = {
    "name": "product-mcp",
    "version": "1.0.0",
    "tools": {
        "list_products": {
            "description": "Вернуть список всех товаров.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "products": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "category": {"type": "string"},
                                "price": {"type": "number"},
                            },
                            "required": ["id", "name", "category", "price"],
                        },
                    }
                },
                "required": ["products"],
                "additionalProperties": False,
            },
        },
        "find_product": {
            "description": "Найти товары по подстроке в названии (регистронезависимо).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "products": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "category": {"type": "string"},
                                "price": {"type": "number"},
                            },
                            "required": ["id", "name", "category", "price"],
                        },
                    }
                },
                "required": ["products"],
                "additionalProperties": False,
            },
        },
        "add_product": {
            "description": "Добавить новый товар.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                    "price": {"type": "number"},
                },
                "required": ["name", "category", "price"],
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "product": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "category": {"type": "string"},
                            "price": {"type": "number"},
                        },
                        "required": ["id", "name", "category", "price"],
                    }
                },
                "required": ["product"],
                "additionalProperties": False,
            },
        },
        "calculate": {
            "description": "Безопасно вычислить арифметическое выражение.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string"},
                },
                "required": ["expression"],
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "number"},
                    "error": {"type": "string"},
                },
                "required": [],
                "additionalProperties": False,
            },
        },
        "calculate_advanced": {
            "description": "Расширенный калькулятор с математическими функциями (sin, cos, sqrt, log и др.).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Математическое выражение с функциями (например: 'sqrt(16) + sin(pi/2)')"},
                },
                "required": ["expression"],
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "number"},
                    "error": {"type": "string"},
                },
                "required": [],
                "additionalProperties": False,
            },
        },
        "search_web": {
            "description": "Поиск информации в интернете через DuckDuckGo.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос"},
                    "max_results": {"type": "integer", "description": "Максимальное количество результатов (1-10, по умолчанию 5)"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "body": {"type": "string"},
                                "url": {"type": "string"},
                            },
                        },
                    },
                    "query": {"type": "string"},
                    "error": {"type": "string"},
                },
                "required": [],
                "additionalProperties": False,
            },
        },
        "get_currency_rates": {
            "description": "Получить актуальный курс валют (EUR/USD/RUB и другие).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "base": {"type": "string", "description": "Базовая валюта (по умолчанию USD)"},
                    "currencies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список валют для получения курса (по умолчанию ['EUR', 'RUB'])",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "base": {"type": "string"},
                    "rates": {"type": "object"},
                    "date": {"type": "string"},
                    "error": {"type": "string"},
                },
                "required": [],
                "additionalProperties": False,
            },
        },
        "translate_text": {
            "description": "Перевести текст на указанный язык (английский, немецкий, французский, русский).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Текст для перевода"},
                    "target_language": {"type": "string", "description": "Целевой язык (en/de/fr/ru или названия)"},
                    "source_language": {"type": "string", "description": "Исходный язык (по умолчанию auto)"},
                },
                "required": ["text", "target_language"],
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "original_text": {"type": "string"},
                    "translated_text": {"type": "string"},
                    "source_language": {"type": "string"},
                    "target_language": {"type": "string"},
                    "error": {"type": "string"},
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
}


