import json

from langchain_core.tools import tool
from src.models import BudgetLine, SaveArtifactsInput, TripDraft
from src.rag.store import TravelFactStore
from src.storage.artifacts import save_trip_artifacts


@tool
def search_travel_facts(session_id: str, query: str, limit: int = 6) -> str:
    """Search indexed ChromaDB travel facts for a trip session."""
    facts = TravelFactStore(session_id=session_id).search(query=query, limit=limit)
    return json.dumps(
        [fact.model_dump(mode="json") for fact in facts], ensure_ascii=False, indent=2
    )


@tool(args_schema=SaveArtifactsInput)
def save_artifacts(
    session_id: str,
    draft_json: TripDraft,
    itinerary_markdown: str,
    budget_json: list[BudgetLine],
) -> str:
    """Save meta.json, itinerary.md, and budget.json under artifacts/<session_id>/."""
    paths = save_trip_artifacts(
        session_id,
        draft_json,
        _normalize_markdown(itinerary_markdown),
        budget_json,
    )
    return json.dumps(paths, indent=2)


def _normalize_markdown(markdown: str) -> str:
    # Tool calls sometimes arrive with literal "\n" sequences instead of real newlines.
    return markdown.replace("\\n", "\n")
