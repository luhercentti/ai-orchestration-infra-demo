"""Builds the LangGraph StateGraph: nodes, edges, conditional routing."""
from langgraph.graph import END, StateGraph

from .agents.human_approval import human_approval
from .agents.plan_agent import plan_agent
from .agents.policy_agent import policy_agent
from .agents.provisioning_agent import provisioning_agent
from .agents.spec_agent import spec_agent
from .agents.supervisor import route, supervisor
from .state import OrchestratorState


def build_graph(checkpointer=None):
    graph = StateGraph(OrchestratorState)

    graph.add_node("supervisor", supervisor)
    graph.add_node("spec_agent", spec_agent)
    graph.add_node("policy_agent", policy_agent)
    graph.add_node("plan_agent", plan_agent)
    graph.add_node("human_approval", human_approval)
    graph.add_node("provisioning_agent", provisioning_agent)

    graph.set_entry_point("supervisor")

    # Every specialist reports back to the supervisor, which re-routes.
    for node in ("spec_agent", "policy_agent", "plan_agent", "human_approval", "provisioning_agent"):
        graph.add_edge(node, "supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route,
        {
            "spec_agent": "spec_agent",
            "policy_agent": "policy_agent",
            "plan_agent": "plan_agent",
            "human_approval": "human_approval",
            "provisioning_agent": "provisioning_agent",
            "end": END,
        },
    )

    return graph.compile(checkpointer=checkpointer)
