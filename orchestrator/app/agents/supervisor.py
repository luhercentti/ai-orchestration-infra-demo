"""The supervisor node: the only place routing decisions are made.

Every other node just does its one job and reports back into shared state; the
supervisor re-evaluates state after each hop and decides what runs next. This
keeps routing logic centralized and inspectable instead of scattered as
if/else branches throughout the codebase.
"""
from ..state import OrchestratorState


def supervisor(state: OrchestratorState) -> dict:
    if "spec" not in state:
        next_node = "spec_agent"
    elif "policy" not in state:
        next_node = "policy_agent"
    elif not state["policy"]["approved"]:
        next_node = "end"
    elif "plan" not in state:
        next_node = "plan_agent"
    elif "approval" not in state:
        next_node = "human_approval"
    elif state["approval"] == "approved" and state.get("status") != "provisioned":
        next_node = "provisioning_agent"
    else:
        next_node = "end"

    history = state.get("history", []) + [f"supervisor: routing to '{next_node}'"]
    return {"next": next_node, "history": history}


def route(state: OrchestratorState) -> str:
    """Conditional-edge selector: reads the supervisor's decision from state."""
    return state["next"]
