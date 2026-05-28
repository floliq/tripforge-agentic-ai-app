import json
from pathlib import Path
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from agent import build_agent, build_checkpointer

ALLOWED_ARTIFACT_PATHS = {"/itinerary.md", "/budget.md", "/research.json"}


def _guard_file_action(action: dict) -> dict | None:
    tool_name = action.get("name")
    if tool_name not in {"write_file", "edit_file"}:
        return None

    tool_args = action.get("args", {})
    file_path = str(tool_args.get("file_path", "")).strip()
    if file_path in ALLOWED_ARTIFACT_PATHS:
        return None

    reason = (
        f"Blocked by guard: `{tool_name}` allowed only for {sorted(ALLOWED_ARTIFACT_PATHS)}; "
        f"got `{file_path or '<empty>'}`."
    )
    print(f"\n[HITL guard] {reason}")
    return {"type": "reject", "message": reason}


def _normalize_write_file_action(action: dict) -> dict | None:
    if action.get("name") != "write_file":
        return None

    tool_args = action.get("args", {})
    file_path = str(tool_args.get("file_path", "")).strip()
    if file_path not in ALLOWED_ARTIFACT_PATHS:
        return None

    content = tool_args.get("content")

    if isinstance(content, (dict, list)):
        edited_args = dict(tool_args)
        edited_args["content"] = json.dumps(content, ensure_ascii=False, indent=2)
        return {
            "type": "edit",
            "edited_action": {"name": "write_file", "args": edited_args},
        }

    if not isinstance(content, str):
        reason = (
            "Blocked by guard: `write_file.content` must be a string "
            f"for `{file_path}`."
        )
        print(f"\n[HITL guard] {reason}")
        return {"type": "reject", "message": reason}

    if file_path == "/research.json":
        try:
            json.loads(content)
        except json.JSONDecodeError:
            reason = (
                "Blocked by guard: `/research.json` content must be a valid JSON string."
            )
            print(f"\n[HITL guard] {reason}")
            return {"type": "reject", "message": reason}

    return None


def _extract_hitl_payload(result: dict) -> dict:
    interrupts = result.get("__interrupt__", [])
    if not interrupts:
        return {}

    raw_interrupt = interrupts[0]
    if hasattr(raw_interrupt, "value"):
        return raw_interrupt.value
    if isinstance(raw_interrupt, dict):
        return raw_interrupt.get("value", raw_interrupt)
    return {}


def _prompt_decision(action: dict, allowed: list[str]) -> dict | None:
    tool_name = action.get("name", "unknown")
    tool_args = action.get("args", {})
    description = action.get("description", "")

    print("\n--- HITL review ---")
    if description:
        print(description)
    else:
        print(f"Tool: {tool_name}\nArgs: {tool_args}")

    print("Выберите операцию:")
    for idx, decision in enumerate(allowed, start=1):
        print(f"{idx}) {decision}")
    print("0) exit")

    while True:
        choice = input("Номер: ").strip()
        if choice == "0":
            return None
        if not choice.isdigit() or not (1 <= int(choice) <= len(allowed)):
            print("Некорректный выбор. Повторите ввод.")
            continue

        decision_type = allowed[int(choice) - 1]
        if decision_type == "approve":
            return {"type": "approve"}
        if decision_type == "reject":
            message = input("Причина reject (опционально): ").strip()
            return {"type": "reject", "message": message} if message else {"type": "reject"}
        if decision_type == "respond":
            message = input("Ответ вместо tool execution: ").strip()
            if not message:
                print("Для respond нужен непустой текст.")
                continue
            return {"type": "respond", "message": message}
        if decision_type == "edit":
            print("Введите JSON для новых args (пример: {\"file_path\":\"/research.json\"})")
            edited_args_raw = input("edited args JSON: ").strip()
            try:
                edited_args = json.loads(edited_args_raw)
            except json.JSONDecodeError:
                print("Некорректный JSON. Повторите ввод.")
                continue
            if not isinstance(edited_args, dict):
                print("edited args должны быть JSON-объектом.")
                continue
            return {
                "type": "edit",
                "edited_action": {"name": tool_name, "args": edited_args},
            }


def _build_resume_payload(result: dict) -> dict | None:
    payload = _extract_hitl_payload(result)
    action_requests = payload.get("action_requests", [])
    review_configs = payload.get("review_configs", [])
    if not action_requests:
        return {"decisions": [{"type": "approve"}]}

    allowed_map = {
        cfg.get("action_name"): cfg.get(
            "allowed_decisions", ["approve", "edit", "reject", "respond"]
        )
        for cfg in review_configs
    }

    decisions = []
    for action in action_requests:
        auto_decision = _guard_file_action(action) or _normalize_write_file_action(action)
        if auto_decision is not None:
            decisions.append(auto_decision)
            continue

        allowed = allowed_map.get(
            action.get("name"), ["approve", "edit", "reject", "respond"]
        )
        decision = _prompt_decision(action, allowed)
        if decision is None:
            return None
        decisions.append(decision)
    return {"decisions": decisions}


def print_last_assistant(result: dict) -> None:
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            print(f"\nAssistant: {msg.content}\n")
            return
    if messages:
        print(f"\nAssistant: {messages[-1]}\n")
    else:
        print("\nAssistant: (no messages)\n")


def main():
    trip_id = str(uuid4())
    config = {"configurable": {"thread_id": trip_id}}

    trip_dir = Path("trips") / trip_id
    trip_dir.mkdir(parents=True, exist_ok=True)

    print(f"trip_id: {trip_id}")
    print(f"trip_dir: {trip_dir}")
    print("Введите запрос (exit для выхода)\n")

    checkpointer = build_checkpointer()
    agent = build_agent(trip_dir=trip_dir, checkpointer=checkpointer)

    user_text = input("You: ").strip()
    while user_text.lower() not in {"exit", "quit"}:
        if not user_text:
            user_text = input("You: ").strip()
            continue

        result = agent.invoke(
            {"messages": [HumanMessage(content=user_text)]},
            config=config,
        )

        while result.get("__interrupt__"):
            print("\n[HITL interrupt]")
            resume_payload = _build_resume_payload(result)
            if resume_payload is None:
                print("Session stopped.")
                return
            result = agent.invoke(Command(resume=resume_payload), config=config)

        print_last_assistant(result)
        user_text = input("You: ").strip()


if __name__ == "__main__":
    main()
