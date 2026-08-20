from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph import build_graph


def test_full_run_pauses_for_approval_then_provisions():
    graph = build_graph(MemorySaver())
    config = {"configurable": {"thread_id": "test-thread-1"}}

    result = graph.invoke(
        {"request": {"raw_text": "postgres for team billing, staging", "requester": "alice"}, "history": []},
        config,
    )

    # graph should be paused at the human_approval interrupt
    snapshot = graph.get_state(config)
    assert snapshot.next == ("supervisor",) or "human_approval" in str(snapshot.tasks)
    assert snapshot.values["plan"]["module"] == "modules/rds-postgres"

    result = graph.invoke(Command(resume={"approval": "approved", "approver": "platform-team"}), config)

    final = graph.get_state(config).values
    assert final["status"] == "provisioned"
    assert final["approval"] == "approved"


def test_rejected_policy_ends_without_reaching_approval():
    graph = build_graph(MemorySaver())
    config = {"configurable": {"thread_id": "test-thread-2"}}

    graph.invoke(
        {"request": {"raw_text": "mongodb for team billing, staging", "requester": "alice"}, "history": []},
        config,
    )

    final = graph.get_state(config).values
    assert final["policy"]["approved"] is False
    assert "plan" not in final
