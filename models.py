from datetime import date
from typing import Literal

from pydantic import BaseModel


class TripRequest(BaseModel):
    city: str | None = None
    trip_purpose: str | None = None
    time_hint: str | None = None
    raw_request: str | None = None
    days: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    budget: float | None = None
    interests: list[str] = []
    pace: Literal["relaxed", "moderate", "active"] = "moderate"
    origin_city: str | None = None

    def is_complete(self) -> bool:
        has_destination = bool(self.city)
        has_time = self.days is not None or (
            self.date_from is not None and self.date_to is not None
        )
        return has_destination and has_time


class DayPlan(BaseModel):
    day: int
    date: date
    activities: list[str] = []
    notes: str | None = None


class TripItinerary(BaseModel):
    city: str
    days: list[DayPlan]
    tips: list[str] = []


class GeocodeResult(BaseModel):
    city: str
    latitude: float
    longitude: float
    country: str | None = None


class WeatherDay(BaseModel):
    date: date
    temperature: float
    description: str
    wind_speed: float


class WeatherResult(BaseModel):
    latitude: float
    longitude: float
    date_from: date
    date_to: date
    days_weather: list[WeatherDay]
