import json
from datetime import date
from typing import Any

from langchain_core.tools import tool

from src.clients.travel_api import TravelApiClient, facts_from_places, facts_from_weather
from src.models import Coordinates, TravelFact
from src.rag.store import TravelFactStore


@tool
def fetch_geocode(destination: str) -> str:
    """Fetch destination coordinates from Nominatim."""
    coordinates = TravelApiClient().geocode(destination)
    return coordinates.model_dump_json(indent=2)


def _coordinates(
    destination_name: str,
    latitude: float,
    longitude: float,
    country: str | None = None,
) -> Coordinates:
    return Coordinates(
        name=destination_name,
        latitude=latitude,
        longitude=longitude,
        country=country,
    )


def _as_string_list(value: list[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return json.loads(value) if value.strip() else []
    return value


@tool
def fetch_places(
    destination_name: str,
    latitude: float,
    longitude: float,
    country: str | None = None,
    interests: list[str] | None = None,
) -> str:
    """Fetch attractions and places from OpenTripMap for the given coordinates."""
    coordinates = _coordinates(destination_name, latitude, longitude, country)
    places = TravelApiClient().places(coordinates, _as_string_list(interests))
    return json.dumps(
        [place.model_dump(mode="json") for place in places],
        ensure_ascii=False,
        indent=2,
    )


@tool
def fetch_weather_outline(
    destination_name: str,
    latitude: float,
    longitude: float,
    country: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Fetch a daily weather outline from Open-Meteo."""
    coordinates = _coordinates(destination_name, latitude, longitude, country)
    parsed_start = date.fromisoformat(start_date) if start_date else None
    parsed_end = date.fromisoformat(end_date) if end_date else None
    weather = TravelApiClient().weather_outline(coordinates, parsed_start, parsed_end)
    return weather.model_dump_json(indent=2)


@tool
def index_travel_facts(
    session_id: str,
    facts: list[TravelFact],
) -> str:
    """Index travel facts in ChromaDB for this trip session."""
    parsed_facts = [
        fact if isinstance(fact, TravelFact) else TravelFact.model_validate(fact)
        for fact in facts
    ]
    count = TravelFactStore(session_id=session_id).add_facts(parsed_facts)
    return json.dumps({"indexed": count, "session_id": session_id}, indent=2)
