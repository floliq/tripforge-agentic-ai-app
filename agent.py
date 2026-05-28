import os
import sqlite3
from pathlib import Path
from typing import Optional

from deepagents import SubAgent, create_deep_agent
from deepagents.backends import FilesystemBackend
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langgraph.checkpoint.sqlite import SqliteSaver

from prompts import WEATHER_ANALYST_SYSTEM_PROMPT, build_main_system_prompt
from tools import geocode_city, fetch_weather, search_poi, get_poi_details

load_dotenv()


def build_model() -> ChatOllama:
    ollama_model = os.getenv("OLLAMA_MODEL")
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

    if not ollama_model:
        raise RuntimeError("OLLAMA_MODEL is not set in environment")

    # Keep model reasoning private: return only user-facing answers.
    chat_model = ChatOllama(
        model=ollama_model,
        base_url=ollama_url,
        reasoning=False,
    )

    return chat_model


def build_checkpointer() -> SqliteSaver:
    checkpoint_conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
    checkpointer = SqliteSaver(checkpoint_conn)
    return checkpointer


def build_agent(
    trip_dir: Path,
    checkpointer: Optional[SqliteSaver] = None,
    wants_poi_context: str = "unknown",
):
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
        tools=[geocode_city, fetch_weather, search_poi, get_poi_details],
        system_prompt=build_main_system_prompt(
            trip_dir=str(trip_dir),
            wants_poi=wants_poi_context,
        ),
        subagents=subagents,
        memory=["./memory/"],
        backend=FilesystemBackend(root_dir=trip_dir, virtual_mode=True),
        checkpointer=checkpointer,
        interrupt_on={"write_file": True, "edit_file": True},
    )

    return agent
