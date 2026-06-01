from datetime import date, timedelta
from typing import Any, Literal

import requests

from src.config import Settings
from src.models import Coordinates, Place, WeatherOutline, TravelFact


class TravelApiClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "TripForge/0.1 educational CLI"})

    def geocode(self, destination: str) -> Coordinates:
        response = self.session.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": destination,
                "format": "json",
                "limit": 1,
                "addressdetails": 1,
            },
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        #print(data)
        if not data:
            raise ValueError(f"Destination not found: {destination}")

        first = data[0]
        address = first.get("address", {})
        return Coordinates(
            name=first.get("display_name", destination),
            latitude=float(first["lat"]),
            longitude=float(first["lon"]),
            country=address.get("country"),
        )

    def places(
        self, coordinates: Coordinates, interests: list[str] | None = None
    ) -> list[Place]:
        return self._places_radius(coordinates, limit=self.settings.max_places)

    def hotels(
        self,
        coordinates: Coordinates,
        accommodation_style: Literal["budget", "comfort", "luxury"] | None = None,
    ) -> list[Place]:
        places = self._places_radius(
            coordinates,
            kinds="accomodations",
            limit=self.settings.max_hotels,
        )
        hotels: list[Place] = []
        for place in places:
            tier = _classify_accommodation(place.metadata.get("kinds", ""))
            if accommodation_style and tier != accommodation_style:
                continue
            hotels.append(
                place.model_copy(
                    update={
                        "category": f"accommodation_{tier}",
                        "summary": (
                            f"{place.name} is a {tier} accommodation option near "
                            f"{coordinates.name}. Tags: {place.metadata.get('kinds', '')}."
                        ),
                        "metadata": {
                            **place.metadata,
                            "accommodation_style": tier,
                        },
                    }
                )
            )
        return hotels

    def _places_radius(
        self,
        coordinates: Coordinates,
        *,
        kinds: str | None = None,
        limit: int,
    ) -> list[Place]:
        if not self.settings.opentripmap_api_key:
            raise Exception("OpenTripMap API key not set")

        params: dict[str, Any] = {
            "radius": 8000,
            "lon": coordinates.longitude,
            "lat": coordinates.latitude,
            "limit": limit,
            "format": "json",
            "apikey": self.settings.opentripmap_api_key,
        }
        if kinds:
            params["kinds"] = kinds

        response = self.session.get(
            "https://api.opentripmap.com/0.1/en/places/radius",
            params=params,
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()

        places: list[Place] = []
        for item in response.json():
            name = item.get("name") or "Unnamed interesting place"
            item_kinds = item.get("kinds", kinds or "attraction")
            places.append(
                Place(
                    name=name,
                    category=item_kinds.split(",")[0],
                    summary=f"{name} near {coordinates.name}. Tags: {item_kinds}.",
                    latitude=item.get("point", {}).get("lat"),
                    longitude=item.get("point", {}).get("lon"),
                    metadata={
                        "xid": item.get("xid"),
                        "kinds": item_kinds,
                    },
                )
            )
        #print(places)
        return places

    def weather_outline(
        self,
        coordinates: Coordinates,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> WeatherOutline:
        params: dict[str, Any] = {
            "latitude": coordinates.latitude,
            "longitude": coordinates.longitude,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
        }
        if start_date and end_date:
            params["start_date"] = start_date.isoformat()
            params["end_date"] = end_date.isoformat()
        else:
            today = date.today()
            params["start_date"] = today.isoformat()
            params["end_date"] = (today + timedelta(days=6)).isoformat()

        response = self.session.get(
            "https://api.open-meteo.com/v1/forecast",
            params=params,
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        daily = response.json().get("daily", {})
        forecast = []
        for idx, day in enumerate(daily.get("time", [])):
            # TODO
            forecast.append(
                {
                    "date": day,
                    "temp_min_c": _safe_list_get(daily.get("temperature_2m_min"), idx),
                    "temp_max_c": _safe_list_get(daily.get("temperature_2m_max"), idx),
                    "precipitation_probability": _safe_list_get(
                        daily.get("precipitation_probability_max"), idx
                    ),
                }
            )
        #print(forecast)
        return WeatherOutline(destination=coordinates.name, forecast=forecast)


def facts_from_places(places: list[Place]) -> list[TravelFact]:
    return [
        TravelFact(
            source="opentripmap",
            title=place.name,
            summary=place.summary,
            category=place.category,
            metadata={
                "latitude": place.latitude,
                "longitude": place.longitude,
                **place.metadata,
            },
        )
        for place in places
    ]


def facts_from_hotels(hotels: list[Place]) -> list[TravelFact]:
    return [
        TravelFact(
            source="opentripmap",
            title=hotel.name,
            summary=hotel.summary,
            category=hotel.category,
            metadata={
                "latitude": hotel.latitude,
                "longitude": hotel.longitude,
                **hotel.metadata,
            },
        )
        for hotel in hotels
    ]


def facts_from_weather(weather: WeatherOutline) -> list[TravelFact]:
    return [
        TravelFact(
            source="open-meteo",
            title=f"Weather on {item['date']}",
            summary=(
                f"Forecast for {weather.destination}: {item.get('temp_min_c')}.."
                f"{item.get('temp_max_c')} C, precipitation probability "
                f"{item.get('precipitation_probability')}%."
            ),
            category="weather",
            metadata=item,
        )
        for item in weather.forecast
    ]


def _safe_list_get(items: list[Any] | None, idx: int) -> Any:
    if not items or idx >= len(items):
        return None
    return items[idx]


def _classify_accommodation(kinds: str) -> Literal["budget", "comfort", "luxury"]:
    kind_set = {kind.strip() for kind in kinds.split(",") if kind.strip()}
    if kind_set & {"hostels", "guest_houses", "motels"}:
        return "budget"
    if kind_set & {"resorts", "villas"}:
        return "luxury"
    return "comfort"
