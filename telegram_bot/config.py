import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    telegram_token: str
    openai_api_key: str
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"
    mcp_server_url: str = "http://127.0.0.1:8000"


def load_settings() -> Settings:
    telegram_token = os.getenv("TELEGRAM_API_TOKEN", "")
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000")

    if not telegram_token:
        raise RuntimeError(
            "Не задан TELEGRAM_API_TOKEN в .env (или переменных окружения)."
        )
    if not openai_api_key:
        raise RuntimeError(
            "Не задан OPENAI_API_KEY в .env (или переменных окружения)."
        )

    return Settings(
        telegram_token=telegram_token,
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        openai_model=openai_model,
        mcp_server_url=mcp_server_url,
    )


