from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from src.clients.travel_api import TravelApiClient, facts_from_route_legs
from src.models import Place, RouteLeg
from src.rag.store import TravelFactStore


class RoutePlanningState(TypedDict, total=False):
    session_id: str
    destination_name: str
    city_transport_mode: Literal["walking", "bicycle", "car"]
    points: list[dict[str, Any]]
    route_points: list[Place]
    route_legs: list[RouteLeg]
    indexed: int
    status: str
    routing_status: str
    error: str | None


def run_route_planning(
    *,
    session_id: str,
    destination_name: str,
    points: list[dict[str, Any]],
    city_transport_mode: Literal["walking", "bicycle", "car"],
) -> dict[str, Any]:
    """Run deterministic city route planning and return JSON-ready output."""
    graph = _build_route_planning_graph()
    result = graph.invoke(
        {
            "session_id": session_id,
            "destination_name": destination_name,
            "points": points,
            "city_transport_mode": city_transport_mode,
        }
    )
    route_legs = result.get("route_legs", [])
    return {
        "status": result.get("status", "unknown"),
        "routing_status": result.get("routing_status", "unknown"),
        "indexed": result.get("indexed", 0),
        "session_id": session_id,
        "destination_name": destination_name,
        "route_legs": [leg.model_dump(mode="json") for leg in route_legs],
        "error": result.get("error"),
    }


def _build_route_planning_graph():
    graph = StateGraph(RoutePlanningState)
    graph.add_node("prepare_route_points", _prepare_route_points)
    graph.add_node("fetch_routes", _fetch_routes)
    graph.add_node("index_routes", _index_routes)
    graph.add_edge(START, "prepare_route_points")
    graph.add_edge("prepare_route_points", "fetch_routes")
    graph.add_edge("fetch_routes", "index_routes")
    graph.add_edge("index_routes", END)
    return graph.compile()


def _prepare_route_points(state: RoutePlanningState) -> RoutePlanningState:
    route_points = _places_from_route_points(state.get("points", []))
    return {"route_points": route_points}


def _fetch_routes(state: RoutePlanningState) -> RoutePlanningState:
    route_points = state.get("route_points", [])
    mode = state["city_transport_mode"]
    try:
        route_legs = TravelApiClient().route_legs(route_points, mode)
        return {
            "route_legs": route_legs,
            "routing_status": "ok",
            "status": "routes_fetched",
            "error": None,
        }
    except Exception as exc:
        return {
            "route_legs": _fallback_route_legs(route_points, mode, str(exc)),
            "routing_status": "fallback",
            "status": "routes_fallback",
            "error": str(exc),
        }


def _index_routes(state: RoutePlanningState) -> RoutePlanningState:
    route_legs = state.get("route_legs", [])
    try:
        route_facts = facts_from_route_legs(route_legs)
        indexed = TravelFactStore(session_id=state["session_id"]).add_facts(route_facts)
        return {"indexed": indexed, "status": "indexed"}
    except Exception as exc:
        return {
            "indexed": 0,
            "status": "index_failed",
            "error": str(exc),
        }


def _places_from_route_points(points: list[dict[str, Any]]) -> list[Place]:
    places: list[Place] = []
    for idx, point in enumerate(points, start=1):
        latitude = point.get("latitude")
        longitude = point.get("longitude")
        if latitude is None or longitude is None:
            continue
        name = str(point.get("name") or f"Stop {idx}")
        places.append(
            Place(
                name=name,
                category=str(point.get("category") or "route_stop"),
                summary=str(point.get("summary") or f"Route stop: {name}."),
                latitude=float(latitude),
                longitude=float(longitude),
                metadata=dict(point.get("metadata") or {}),
            )
        )
    return places


def _fallback_route_legs(
    points: list[Place],
    mode: Literal["walking", "bicycle", "car"],
    error: str,
) -> list[RouteLeg]:
    if len(points) < 2:
        return [
            RouteLeg(
                origin="route origin",
                destination="route destination",
                mode=mode,
                summary=(
                    "Routing unavailable because fewer than two points with coordinates "
                    "were provided."
                ),
                metadata={"routing_status": "unavailable", "error": error},
            )
        ]

    return [
        RouteLeg(
            origin=origin.name,
            destination=destination.name,
            mode=mode,
            summary=(
                f"{origin.name} to {destination.name}: selected transport is {mode}, "
                "but distance and duration are unavailable from OpenRouteService."
            ),
            metadata={"routing_status": "unavailable", "error": error},
        )
        for origin, destination in zip(points, points[1:], strict=False)
    ]
