from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class TripDraft(BaseModel):
    destination: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = Field(default=None, ge=1)
    travelers: int | None = Field(default=None, ge=1)
    travel_style: Literal["budget", "comfort", "premium"] | None = None
    interests: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    raw_request: str | None = None

    def missing_required_fields(self) -> list[str]:
        required = ["destination", "duration_days", "travelers", "interests"]
        return [field for field in required if not getattr(self, field)]


class Coordinates(BaseModel):
    name: str
    latitude: float
    longitude: float
    country: str | None = None


class TravelFact(BaseModel):
    source: str
    title: str
    summary: str
    category: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Place(BaseModel):
    name: str
    category: str
    summary: str
    latitude: float | None = None
    longitude: float | None = None


class WeatherOutline(BaseModel):
    destination: str
    forecast: list[dict[str, Any]]


class BudgetLine(BaseModel):
    category: str
    amount: float
    currency: str = "EUR"
    note: str | None = None


class TripArtifacts(BaseModel):
    session_id: str
    draft: TripDraft
    itinerary_markdown: str
    budget: list[BudgetLine]
