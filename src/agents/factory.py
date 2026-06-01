from datetime import date

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver

from src.agents.prompts import (
    CLARIFY_PROMPT,
    RESEARCH_PROMPT,
    PLANNER_PROMPT,
    SUPERVISOR_PROMPT,
)
from src.llm import build_chat_model
from src.tools.clarify import extract_trip_draft, ask_user
from src.tools.research import (
    fetch_geocode,
    fetch_places,
    fetch_weather_outline,
    index_travel_facts,
)
from src.tools.planner import search_travel_facts, save_artifacts


def _with_today(prompt: str) -> str:
    today = date.today().isoformat()
    return (
        f"{prompt}\n\nToday's date: {today}. "
        "Use this calendar year when the user omits a year. "
        "Do not use dates before today."
    )


def build_tripforge_agent(checkpointer: MemorySaver | None = None):
    """Build the supervisor Deep Agent with three task-tool subagents."""
    model = build_chat_model()
    checkpointer = checkpointer or MemorySaver()

    clarify_tools = [extract_trip_draft, ask_user]
    research_tools = [
        fetch_geocode,
        fetch_places,
        fetch_weather_outline,
        index_travel_facts,
    ]
    planner_tools = [search_travel_facts, save_artifacts]

    subagents = [
        {
            "name": "clarify-agent",
            "description": "Extracts trip draft fields and asks the traveler for missing details.",
            "system_prompt": _with_today(CLARIFY_PROMPT),
            "tools": clarify_tools,
            "interrupt_on": {"ask_user": {"allowed_decisions": ["respond"]}},
        },
        {
            "name": "research-agent",
            "description": "Fetches travel facts from free APIs and indexes them in ChromaDB.",
            "system_prompt": _with_today(RESEARCH_PROMPT),
            "tools": research_tools,
            "interrupt_on": {
                "fetch_geocode": {"allowed_decisions": ["approve", "edit", "reject"]},
                "fetch_places": {"allowed_decisions": ["approve", "edit", "reject"]},
                "fetch_weather_outline": {
                    "allowed_decisions": ["approve", "edit", "reject"]
                },
            },
        },
        {
            "name": "planner-agent",
            "description": "Builds the itinerary and budget, then saves final artifacts.",
            "system_prompt": PLANNER_PROMPT,
            "tools": planner_tools,
            "interrupt_on": {
                "save_artifacts": {"allowed_decisions": ["approve", "edit", "reject"]}
            },
        },
    ]

    return create_deep_agent(
        model=model,
        tools=[
            extract_trip_draft,
            ask_user,
            fetch_geocode,
            fetch_places,
            fetch_weather_outline,
            index_travel_facts,
            search_travel_facts,
            save_artifacts,
        ],
        system_prompt=_with_today(SUPERVISOR_PROMPT),
        subagents=subagents,
        interrupt_on={
            "ask_user": {"allowed_decisions": ["respond"]},
            "fetch_geocode": {"allowed_decisions": ["approve", "edit", "reject"]},
            "fetch_places": {"allowed_decisions": ["approve", "edit", "reject"]},
            "fetch_weather_outline": {
                "allowed_decisions": ["approve", "edit", "reject"]
            },
            "save_artifacts": {"allowed_decisions": ["approve", "edit", "reject"]},
        },
        checkpointer=checkpointer,
    )
