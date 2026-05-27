import os
import sqlite3
from typing import Optional

from deepagents import SubAgent, create_deep_agent
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langgraph.checkpoint.sqlite import SqliteSaver

from prompts import WEATHER_ANALYST_SYSTEM_PROMPT, MAIN_SYSTEM_PROMPT
from tools import geocode_city, fetch_weather

load_dotenv()


def build_model() -> ChatOllama:
    ollama_model = os.getenv("OLLAMA_MODEL")
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

    if not ollama_model:
        raise RuntimeError("OLLAMA_MODEL is not set in environment")

    chat_model = ChatOllama(model=ollama_model, base_url=ollama_url)

    return chat_model


def build_checkpointer() -> SqliteSaver:
    checkpoint_conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
    checkpointer = SqliteSaver(checkpoint_conn)
    return checkpointer


def build_agent(checkpointer: Optional[SqliteSaver] = None):
    if checkpointer is None:
        checkpointer = build_checkpointer()
    weather_analyst_agents: SubAgent = {
        "name": "weather_analyst",
        "description": "Analyzes weather trends and gives practical recommendations.",
        "system_prompt": WEATHER_ANALYST_SYSTEM_PROMPT,
    }
    subagents = [weather_analyst_agents]

    agent = create_deep_agent(
        model=build_model(),
        tools=[geocode_city, fetch_weather],
        system_prompt=MAIN_SYSTEM_PROMPT,
        subagents=subagents,
        memory=["./memory/"],
        checkpointer=checkpointer,
        interrupt_on={"write_file": True, "edit_file": True},
    )

    return agent
