from datetime import date
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field


class TripDraft(BaseModel):
    destination: str | None = Field(
        default=None,
        description="Plain destination string, e.g. 'Brest, Belarus'. Do not pass an object.",
    )
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = Field(default=None, ge=1)
    budget: float | None = Field(default=None, ge=0)
    budget_currency: str | None = None
    travelers: int | None = Field(default=None, ge=1)
    travel_style: Literal["budget", "comfort", "premium"] | None = Field(
        default=None,
        description="Only budget, comfort, or premium. Put themes like history into interests.",
    )
    needs_accommodation: bool | None = Field(
        default=None,
        description="Whether the traveler needs overnight accommodation for this trip.",
    )
    accommodation_style: Literal["budget", "comfort", "luxury"] | None = Field(
        default=None,
        description=(
            "Preferred accommodation tier when needs_accommodation is true: "
            "budget, comfort, or luxury."
        ),
    )
    interests: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(
        default_factory=list,
        description="Plain list of text constraints. Do not pass an object.",
    )
    raw_request: str | None = None

    def missing_required_fields(self) -> list[str]:
        required = [
            "destination",
            "duration_days",
            "travelers",
            "interests",
            "needs_accommodation",
        ]
        missing = [field for field in required if getattr(self, field) in (None, [], "")]
        if self.needs_accommodation and not self.accommodation_style:
            missing.append("accommodation_style")
        return missing


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
    metadata: dict[str, Any] = Field(default_factory=dict)


class WeatherOutline(BaseModel):
    destination: str
    forecast: list[dict[str, Any]]


class BudgetLine(BaseModel):
    category: str
    amount: float
    currency: str = "EUR"
    note: str | None = Field(default=None, validation_alias=AliasChoices("note", "notes"))


class SaveArtifactsInput(BaseModel):
    session_id: str = Field(description="Current trip session id.")
    draft_json: TripDraft = Field(
        description=(
            "TripDraft only. destination must be a plain string; travel_style must be "
            "budget, comfort, premium, or null; constraints must be a list of strings. "
            "needs_accommodation must be a boolean and accommodation_style must be "
            "budget, comfort, luxury, or null. "
            "Do not include logistics, key_attractions, weather_summary, coordinates, "
            "or budget breakdown objects here."
        )
    )
    itinerary_markdown: str = Field(description="Final itinerary as a Markdown string.")
    budget_json: list[BudgetLine] = Field(
        description=(
            "List of BudgetLine objects only. Each item must include category, amount, "
            "currency, and note."
        )
    )