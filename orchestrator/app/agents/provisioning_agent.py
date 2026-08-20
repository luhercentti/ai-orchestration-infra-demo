"""Applies the Terraform plan. In this demo the actual `terraform apply` is
simulated; the important part is that the operation is keyed by the plan's
deterministic `workspace_key`, so a replayed/resumed run can never
double-provision the same resource."""
from ..state import OrchestratorState


def provisioning_agent(state: OrchestratorState) -> dict:
    if state.get("approval") != "approved":
        history = state.get("history", []) + ["provisioning_agent: skipped (not approved)"]
        return {"status": "rejected", "history": history}

    plan = state["plan"]
    # Real implementation: `terraform apply -input=false` against a workspace
    # named plan["workspace_key"], with a lock to guard concurrent resumes.
    history = state.get("history", []) + [
        f"provisioning_agent: applied '{plan['module']}' as workspace '{plan['workspace_key']}'"
    ]
    return {"status": "provisioned", "history": history}
