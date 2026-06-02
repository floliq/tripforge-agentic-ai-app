import json
from datetime import date
from typing import Literal

from langchain_core.tools import tool

from src.clients.travel_api import (
    TravelApiClient,
    facts_from_hotels,
    facts_from_places,
)
from src.graphs import run_route_planning
from src.models import Coordinates, Place, TravelFact
from src.rag.store import TravelFactStore


@tool
def fetch_geocode(destination: str) -> str:
    """Fetch destination coordinates from Nominatim."""
    coordinates = TravelApiClient().geocode(destination)
    return coordinates.model_dump_json(indent=2)


@tool
def fetch_places_with_routes(
    session_id: str,
    destination_name: str,
    latitude: float,
    longitude: float,
    country: str | None = None,
    interests: list[str] | None = None,
    city_transport_mode: Literal["walking", "bicycle", "car"] = "walking",
) -> str:
    """Fetch places and plan route legs between those places."""
    coordinates = _coordinates(destination_name, latitude, longitude, country)
    places = TravelApiClient().places(coordinates, _as_string_list(interests))
    place_facts = facts_from_places(places)

    place_index_error = None
    try:
        places_indexed = TravelFactStore(session_id=session_id).add_facts(place_facts)
    except Exception as exc:
        places_indexed = 0
        place_index_error = str(exc)

    route_points = [
        place.model_dump(mode="json")
        for place in places
        if place.latitude is not None and place.longitude is not None
    ]
    route_result = run_route_planning(
        session_id=session_id,
        destination_name=destination_name,
        points=route_points,
        city_transport_mode=city_transport_mode,
    )
    return json.dumps(
        {
            "session_id": session_id,
            "destination_name": destination_name,
            "places_indexed": places_indexed,
            "place_index_error": place_index_error,
            "places": [place.model_dump(mode="json") for place in places],
            "route_planning": route_result,
        },
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
def fetch_hotels(
    destination_name: str,
    latitude: float,
    longitude: float,
    country: str | None = None,
    accommodation_style: Literal["budget", "comfort", "luxury"] | None = None,
) -> str:
    """Fetch accommodation options from OpenTripMap for the given coordinates."""
    coordinates = _coordinates(destination_name, latitude, longitude, country)
    hotels = TravelApiClient().hotels(coordinates, accommodation_style)
    return json.dumps(
        [hotel.model_dump(mode="json") for hotel in hotels],
        ensure_ascii=False,
        indent=2,
    )


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


def accommodation_facts_from_json(hotels_json: str) -> list[TravelFact]:
    payload = json.loads(hotels_json)
    hotels = [Place.model_validate(item) for item in payload]
    return facts_from_hotels(hotels)

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