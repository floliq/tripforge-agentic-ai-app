import json
from typing import Any

from langchain_core.tools import tool
from src.models import TripDraft, BudgetLine
from src.rag.store import TravelFactStore
from src.storage.artifacts import save_trip_artifacts

@tool
def search_travel_facts(session_id: str, query: str, limit: int = 6) -> str:
    """Search indexed ChromaDB travel facts for a trip session."""
    facts = TravelFactStore(session_id=session_id).search(query=query, limit=limit)
    return json.dumps([fact.model_dump(mode="json") for fact in facts], ensure_ascii=False, indent=2)


@tool
def save_artifacts(
    session_id: str,
    draft_json: str | dict[str, Any],
    itinerary_markdown: str,
    budget_json: str | dict[str, Any] | list[dict[str, Any]],
) -> str:
    """Save meta.json, itinerary.md, and budget.json under artifacts/<session_id>/."""
    draft = _parse_draft(draft_json)
    budget = _parse_budget(budget_json)
    paths = save_trip_artifacts(session_id, draft, _normalize_markdown(itinerary_markdown), budget)
    return json.dumps(paths, indent=2)


def _parse_draft(payload: str | dict[str, Any]) -> TripDraft:
    data = json.loads(payload) if isinstance(payload, str) else dict(payload)

    if "total_budget" in data and "budget" not in data:
        data["budget"] = data["total_budget"]
    if "traveler_count" in data and "travelers" not in data:
        data["travelers"] = data["traveler_count"]
    if "focus" in data and not data.get("interests"):
        data["interests"] = [data["focus"]]

    draft = TripDraft.model_validate(data)
    if draft.duration_days is None and draft.start_date and draft.end_date:
        duration_days = (draft.end_date - draft.start_date).days + 1
        draft = draft.model_copy(update={"duration_days": duration_days})

    missing = draft.missing_required_fields()
    if missing:
        raise ValueError(f"draft_json is missing required TripDraft fields: {', '.join(missing)}")

    return draft


def _parse_budget(payload: str | dict[str, Any] | list[dict[str, Any]]) -> list[BudgetLine]:
    data = json.loads(payload) if isinstance(payload, str) else payload

    default_currency = "EUR"
    if isinstance(data, dict):
        default_currency = data.get("currency", default_currency)
        budget_items = data.get("items") or data.get("breakdown") or data.get("budget") or []
    else:
        budget_items = data

    if not budget_items:
        raise ValueError("budget_json must include at least one budget item")

    normalized_items = []
    for item in budget_items:
        normalized = dict(item)
        if "notes" in normalized and "note" not in normalized:
            normalized["note"] = normalized["notes"]
        normalized.setdefault("currency", default_currency)
        normalized_items.append(normalized)

    return [BudgetLine.model_validate(item) for item in normalized_items]


def _normalize_markdown(markdown: str) -> str:
    # Tool calls sometimes arrive with literal "\n" sequences instead of real newlines.
    return markdown.replace("\\n", "\n")