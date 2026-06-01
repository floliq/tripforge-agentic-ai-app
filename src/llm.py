import os
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from langchain_ollama import ChatOllama, OllamaEmbeddings

from src.config import Settings


def build_chat_model(settings: Settings | None = None) -> ChatOllama:
    settings = settings or Settings()
    return ChatOllama(model=settings.ollama_model, base_url=settings.ollama_base_url)


def build_embeddings(settings: Settings | None = None) -> OllamaEmbeddings:
    settings = settings or Settings()
    return OllamaEmbeddings(
        model=settings.ollama_embed_model, base_url=settings.ollama_base_url
    )

def build_langfuse_handler(thread_id: str) -> Any | None:
    settings = Settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None

    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_BASE_URL", settings.langfuse_base_url)

    from langfuse.langchain import CallbackHandler

    return CallbackHandler(trace_context={"trace_id": _langfuse_trace_id(thread_id)})


def _langfuse_trace_id(thread_id: str) -> str:
    return uuid5(NAMESPACE_URL, f"tripforge:{thread_id}").hex


def flush_langfuse(handler: Any | None) -> None:
    if not handler:
        return

    from langfuse import get_client

    get_client().flush()
