from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from pydantic import ValidationError

from src.llm import build_chat_model
from src.models import TripDraft


@tool
def extract_trip_draft(user_request: str) -> str:
    """Extract a partial TripDraft JSON object from the user's free-form trip request."""
    model = build_chat_model()
    prompt = [
        SystemMessage(
            content=(
                "Extract trip planning parameters into JSON matching this schema: "
                "destination, start_date, end_date, duration_days, budget, budget_currency, "
                "travelers, travel_style, interests, constraints, raw_request. "
                "Use null for unknown scalar fields and [] for unknown lists."
            )
        ),
        HumanMessage(content=user_request),
    ]
    try:
        structured = model.with_structured_output(TripDraft).invoke(prompt)
        if isinstance(structured, TripDraft):
            draft = structured
        else:
            draft = TripDraft.model_validate(structured)
        draft.raw_request = user_request
    except (ValidationError, ValueError, TypeError, NotImplementedError):
        draft = _heuristic_extract(user_request)
    return draft.model_dump_json(indent=2)


@tool
def ask_user(question: str) -> str:
    """Ask the human traveler a clarification question and wait for a HITL response."""
    return f"Waiting for traveler response to: {question}"


def _heuristic_extract(user_request: str) -> TripDraft:
    text = user_request.strip()
    destination = _extract_destination(text)
    interests = [
        value
        for key, value in {
            "museum": "museums",
            "food": "food",
            "restaurant": "food",
            "beach": "beaches",
            "hiking": "hiking",
            "history": "history",
            "friends": "friends",
            "weekend": "short city break",
        }.items()
        if key in text.lower()
    ]
    duration = _extract_duration(text)
    budget = _extract_budget(text)
    return TripDraft(
        destination=destination,
        duration_days=duration,
        budget=budget,
        interests=sorted(set(interests)),
        raw_request=user_request,
    )


def _extract_destination(text: str) -> str | None:
    patterns = [
        r"(?:in|to|for|в|во|на)\s+([A-ZА-ЯЁ][\wА-Яа-яёЁ\- ]{2,40})",
        r"([A-ZА-ЯЁ][\wА-Яа-яёЁ\-]{2,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip(" .,!?:;")
    return None


def _extract_duration(text: str) -> int | None:
    lowered = text.lower()
    if "weekend" in lowered or "выходн" in lowered:
        return 2
    if "week" in lowered or "недел" in lowered:
        return 7
    match = re.search(r"(\d+)\s*(?:days|day|дней|дня|день)", lowered)
    return int(match.group(1)) if match else None


def _extract_budget(text: str) -> float | None:
    match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(?:eur|euro|usd|\$|€|руб|rub)", text.lower()
    )
    return float(match.group(1).replace(",", ".")) if match else None


def parse_draft_json(payload: str) -> TripDraft:
    return TripDraft.model_validate(json.loads(payload))
