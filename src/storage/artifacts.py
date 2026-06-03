import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from src.models import TripDraft, BudgetLine
from src.config import Settings


def create_session_id() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")


def session_dir(session_id: str, settings: Settings | None = None) -> Path:
    settings = settings or Settings()
    path = settings.artifacts_dir / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_trip_artifacts(
    session_id: str,
    draft: TripDraft,
    itinerary_markdown: str,
    budget: list[BudgetLine],
    settings: Settings | None = None,
) -> dict[str, str]:
    path = session_dir(session_id, settings)
    meta_path = path / "meta.json"
    itinerary_path = path / "itinerary.md"
    budget_path = path / "budget.json"

    _write_json(
        meta_path,
        {
            "session_id": session_id,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "draft": draft,
        },
    )
    itinerary_path.write_text(itinerary_markdown, encoding="utf-8")
    _write_json(
        budget_path, {"items": budget, "total": sum(item.amount for item in budget)}
    )

    return {
        "meta": str(meta_path),
        "itinerary": str(itinerary_path),
        "budget": str(budget_path),
    }


def _write_json(path: Path, payload: dict) -> None:
    def default(value: object) -> object:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        raise TypeError(
            f"Object of type {type(value).__name__} is not JSON serializable"
        )

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=default),
        encoding="utf-8",
    )
