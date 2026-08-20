"""Pauses the graph for a platform engineer's approval before provisioning.

`interrupt()` freezes the run and persists the checkpoint; resuming with a
Command(resume=...) picks execution back up exactly here, with the returned
value below.
"""
from langgraph.types import interrupt

from ..state import OrchestratorState


def human_approval(state: OrchestratorState) -> dict:
    decision = interrupt(
        {
            "message": "Approve provisioning?",
            "spec": state["spec"],
            "policy": state["policy"],
            "plan": state["plan"],
        }
    )
    history = state.get("history", []) + [f"human_approval: {decision}"]
    return {
        "approval": decision.get("approval"),
        "approver": decision.get("approver"),
        "history": history,
    }
