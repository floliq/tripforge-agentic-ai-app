import json
from datetime import date
from typing import Any

from langgraph.types import Command

from src.llm import build_langfuse_handler, flush_langfuse
from src.agents.factory import build_tripforge_agent
from src.storage.artifacts import create_session_id


def run_cli() -> int:
    session_id = create_session_id()
    thread_id = session_id
    langfuse_handler = build_langfuse_handler(thread_id)
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": [langfuse_handler] if langfuse_handler else [],
        "metadata": {
            "app": "tripforge",
            "session_id": session_id,
            "thread_id": thread_id,
        },
        "run_name": "tripforge-cli",
    }

    print("TripForge")
    print(f"Session: {session_id}")
    user_request = input("Опишите поездку: ").strip()
    if not user_request:
        print("Пустой запрос. Завершение.")
        return 1

    today = date.today().isoformat()
    agent = build_tripforge_agent()
    payload: Any = {
        "messages": [
            {
                "role": "user",
                "content": (
                    f"session_id={session_id}\n"
                    f"thread_id={thread_id}\n"
                    f"today={today}\n"
                    f"Trip request: {user_request}"
                ),
            }
        ]
    }

    try:
        while True:
            result = agent.invoke(payload, config=config, version="v2")
            interrupts = _get_interrupts(result)
            if not interrupts:
                _print_final(result)
                return 0

            decisions = _collect_human_decisions(interrupts[0].value)
            payload = Command(resume={"decisions": decisions})
    finally:
        flush_langfuse(langfuse_handler)



def _print_final(result: Any) -> None:
    # TODO Сделать фидбек финальный
    print("Готово")


def _get_interrupts(result: Any) -> list[Any]:
    interrupts = getattr(result, "interrupts", None)
    if interrupts:
        return list(interrupts)
    if isinstance(result, dict) and result.get("__interrupt__"):
        return list(result["__interrupt__"])
    return []


def _collect_human_decisions(interrupt_value: dict[str, Any]) -> list[dict[str, Any]]:
    actions = interrupt_value.get("action_requests", [])
    review_configs = interrupt_value.get("review_configs", [])
    config_by_name = {item["action_name"]: item for item in review_configs}
    decisions: list[dict[str, Any]] = []

    print("\nТребуется участие человека.")
    for index, action in enumerate(actions, start=1):
        name = action["name"]
        args = action.get("args", {})
        allowed = config_by_name.get(name, {}).get("allowed_decisions", ["approve"])
        print(f"\n[{index}] Tool: {name}")
        print("Arguments:")
        print(json.dumps(args, ensure_ascii=False, indent=2))
        print(f"Allowed decisions: {', '.join(allowed)}")
        decisions.append(_read_decision(name, allowed, args))
    return decisions


def _read_decision(name: str, allowed: list[str], original_args: dict[str, Any]):
    while True:
        decision = input("Decision: ").strip().lower()
        if decision not in allowed:
            print(f"Введите одно из: {', '.join(allowed)}")
            continue
        if decision == "approve":
            return {"type": "approve"}
        if decision == "reject":
            reason = input("Reason: ").strip()
            return {"type": "reject", "message": reason or "Rejected by user"}
        if decision == "respond":
            response = input("Response: ").strip()
            return {"type": "respond", "message": response}
        if decision == "edit":
            print(
                "Введите JSON с новыми arguments. Пустая строка оставит исходные arguments."
            )
            edited = input("Edited arguments JSON: ").strip()
            args = original_args if not edited else json.loads(edited)
            return {"type": "edit", "edited_action": {"name": name, "args": args}}
