from __future__ import annotations

import json
import re
from typing import Literal

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
                "travelers, travel_style, needs_accommodation, accommodation_style, "
                "city_transport_mode, interests, constraints, raw_request. "
                "needs_accommodation is true when the traveler needs overnight lodging. "
                "accommodation_style is budget, comfort, or luxury when lodging is needed. "
                "city_transport_mode is walking, bicycle, or car when the traveler says "
                "how they will move around the city. "
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
    needs_accommodation = _extract_needs_accommodation(text)
    return TripDraft(
        destination=destination,
        duration_days=duration,
        budget=budget,
        needs_accommodation=needs_accommodation,
        accommodation_style=_extract_accommodation_style(text),
        city_transport_mode=_extract_city_transport_mode(text),
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


def _extract_needs_accommodation(text: str) -> bool | None:
    lowered = text.lower()
    if any(
        value in lowered
        for value in (
            "без ночлега",
            "без гостиницы",
            "без отеля",
            "no accommodation",
            "no hotel",
            "without lodging",
        )
    ):
        return False
    if any(
        value in lowered
        for value in (
            "ночлег",
            "гостиниц",
            "отель",
            "хостел",
            "hotel",
            "hostel",
            "lodging",
            "accommodation",
        )
    ):
        return True
    return None


def _extract_accommodation_style(
    text: str,
) -> Literal["budget", "comfort", "luxury"] | None:
    lowered = text.lower()
    if any(value in lowered for value in ("люкс", "luxury", "premium")):
        return "luxury"
    if any(value in lowered for value in ("комфорт", "comfort")):
        return "comfort"
    if any(
        value in lowered for value in ("бюджет", "дешев", "budget", "cheap", "hostel")
    ):
        return "budget"
    return None


def _extract_city_transport_mode(
    text: str,
) -> Literal["walking", "bicycle", "car"] | None:
    lowered = text.lower()
    if any(
        value in lowered
        for value in (
            "пешком",
            "ходить",
            "гулять",
            "walk",
            "walking",
            "on foot",
        )
    ):
        return "walking"
    if any(
        value in lowered
        for value in (
            "велосипед",
            "велике",
            "байк",
            "bike",
            "bicycle",
            "cycling",
        )
    ):
        return "bicycle"
    if any(
        value in lowered
        for value in (
            "машин",
            "авто",
            "такси",
            "car",
            "drive",
            "driving",
            "taxi",
        )
    ):
        return "car"
    return None
