"""Renders the Terraform plan/diff for an approved spec.

The `workspace_key` is deterministic from the spec so a resumed/replayed run
always targets the same Terraform workspace/state — this is what makes the
eventual `terraform apply` idempotent.
"""
from ..golden_paths import ESTIMATED_MONTHLY_COST_USD, TERRAFORM_MODULES
from ..state import OrchestratorState


def plan_agent(state: OrchestratorState) -> dict:
    spec = state["spec"]
    module = TERRAFORM_MODULES[spec["resource_type"]]
    cost = ESTIMATED_MONTHLY_COST_USD[spec["resource_type"]][spec["environment"]]

    plan = {
        "module": module,
        "diff_summary": f"+ resource to create via {module} named '{spec['name']}'",
        "estimated_monthly_cost_usd": cost,
        "workspace_key": spec["name"],
    }
    history = state.get("history", []) + [f"plan_agent: {plan}"]
    return {"plan": plan, "history": history}
