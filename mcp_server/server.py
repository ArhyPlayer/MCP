from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from db import init_db
from tools import (
    list_products_tool,
    find_product_tool,
    add_product_tool,
    calculate_tool,
    calculate_advanced_tool,
    search_web_tool,
    get_currency_rates_tool,
    translate_text_tool,
    TOOLS_JSON_SCHEMA,
)


app = FastAPI(title="product-mcp", version="1.0.0")


@app.on_event("startup")
def _on_startup() -> None:
    """Инициализация БД при старте приложения."""
    print("[MCP SERVER] Инициализация базы данных...")
    try:
        init_db()
        print("[MCP SERVER] База данных успешно инициализирована.")
    except Exception as e:
        print(f"[MCP SERVER] ОШИБКА при инициализации БД: {e}")
        raise
    
    # Проверка доступности библиотек для расширенного функционала
    try:
        try:
            from ddgs import DDGS
            print("[MCP SERVER] ✓ Библиотека ddgs доступна")
        except ImportError:
            from duckduckgo_search import DDGS
            print("[MCP SERVER] ✓ Библиотека duckduckgo-search доступна")
    except ImportError:
        print("[MCP SERVER] ⚠️  Библиотека ddgs/duckduckgo-search не найдена. Установите: pip install ddgs")
    
    try:
        from deep_translator import GoogleTranslator
        print("[MCP SERVER] ✓ Библиотека deep-translator доступна")
    except ImportError:
        print("[MCP SERVER] ⚠️  Библиотека deep-translator не найдена. Установите: pip install deep-translator")


class ToolRequest(BaseModel):
    tool: str = Field(..., description="Имя инструмента MCP")
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Параметры для инструмента"
    )


@app.post("/run_tool")
def run_tool(request: ToolRequest):
    """
    Унифицированная точка входа для вызова MCP-инструментов.

    Поддерживаемые инструменты:
    - list_products
    - find_product
    - add_product
    - calculate
    - calculate_advanced
    - search_web
    - get_currency_rates
    - translate_text
    """
    tool_name = request.tool
    params = request.params

    if tool_name == "list_products":
        result = list_products_tool(params)
    elif tool_name == "find_product":
        result = find_product_tool(params)
    elif tool_name == "add_product":
        result = add_product_tool(params)
    elif tool_name == "calculate":
        result = calculate_tool(params)
    elif tool_name == "calculate_advanced":
        result = calculate_advanced_tool(params)
    elif tool_name == "search_web":
        result = search_web_tool(params)
    elif tool_name == "get_currency_rates":
        result = get_currency_rates_tool(params)
    elif tool_name == "translate_text":
        result = translate_text_tool(params)
    else:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    return JSONResponse(content={"tool": tool_name, "response": result})


@app.get("/schema")
def get_schema():
    """
    Вернуть JSON Schema описания MCP-инструментов.

    Это можно использовать как MCP JSON schema для регистрации инструментов
    в клиенте (IDE/агенте), поддерживающем Model Context Protocol.
    """
    return JSONResponse(content=TOOLS_JSON_SCHEMA)


if __name__ == "__main__":
    # Запуск сервера командой: python server.py
    print("[MCP SERVER] Запуск сервера на http://0.0.0.0:8000")
    print("[MCP SERVER] Для остановки нажмите Ctrl+C")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)


