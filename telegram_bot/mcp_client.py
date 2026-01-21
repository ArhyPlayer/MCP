from typing import Any, Dict, List

import httpx

from config import load_settings


settings = load_settings()


def _call_mcp_tool(tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Вызвать MCP tool через HTTP API MCP-сервера.
    """
    url = f"{settings.mcp_server_url.rstrip('/')}/run_tool"
    payload = {"tool": tool, "params": params}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.ConnectError:
        return {
            "error": "Соединение не установлено (сервер недоступен). Убедитесь, что MCP сервер запущен."
        }
    except httpx.TimeoutException:
        return {
            "error": "Превышено время ожидания ответа от сервера."
        }
    except httpx.HTTPStatusError as e:
        return {
            "error": f"Ошибка HTTP {e.response.status_code}: {e.response.text}"
        }
    except Exception as e:
        return {
            "error": f"Неожиданная ошибка при обращении к серверу: {str(e)}"
        }

    # Ожидаем формат: {"tool": "...", "response": {...}}
    return data.get("response", {})


def list_products() -> Dict[str, Any]:
    return _call_mcp_tool("list_products", {})


def find_product(name: str) -> Dict[str, Any]:
    return _call_mcp_tool("find_product", {"name": name})


def add_product(name: str, category: str, price: float) -> Dict[str, Any]:
    return _call_mcp_tool(
        "add_product", {"name": name, "category": category, "price": price}
    )


def calculate(expression: str) -> Dict[str, Any]:
    return _call_mcp_tool("calculate", {"expression": expression})


def calculate_advanced(expression: str) -> Dict[str, Any]:
    return _call_mcp_tool("calculate_advanced", {"expression": expression})


def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    return _call_mcp_tool("search_web", {"query": query, "max_results": max_results})


def get_currency_rates(base: str = "USD", currencies: List[str] = None) -> Dict[str, Any]:
    if currencies is None:
        currencies = ["EUR", "RUB"]
    return _call_mcp_tool("get_currency_rates", {"base": base, "currencies": currencies})


def translate_text(text: str, target_language: str, source_language: str = "auto") -> Dict[str, Any]:
    return _call_mcp_tool("translate_text", {
        "text": text,
        "target_language": target_language,
        "source_language": source_language,
    })


TOOL_NAME_TO_FUNC = {
    "list_products": list_products,
    "find_product": find_product,
    "add_product": add_product,
    "calculate": calculate,
    "calculate_advanced": calculate_advanced,
    "search_web": search_web,
    "get_currency_rates": get_currency_rates,
    "translate_text": translate_text,
}


