"""Checks a RequestSpec against golden-path rules: allowed types/environments,
naming convention, and quota."""
from ..golden_paths import ALLOWED_ENVIRONMENTS, ALLOWED_RESOURCE_TYPES, QUOTAS
from ..state import OrchestratorState

# Mock "current usage" store — a real implementation would query the cloud
# provider or a resource inventory service.
_CURRENT_USAGE = {}


def policy_agent(state: OrchestratorState) -> dict:
    spec = state["spec"]
    violations = []

    if spec["resource_type"] not in ALLOWED_RESOURCE_TYPES:
        violations.append(f"resource_type '{spec['resource_type']}' is not on the golden path")

    if spec["environment"] not in ALLOWED_ENVIRONMENTS:
        violations.append(f"environment '{spec['environment']}' is not allowed")

    quota = QUOTAS.get(spec["team"], QUOTAS["default"]).get(spec["resource_type"], 0)
    used = _CURRENT_USAGE.get((spec["team"], spec["environment"], spec["resource_type"]), 0)
    if used >= quota:
        violations.append(
            f"quota exceeded: {spec['team']} already has {used}/{quota} "
            f"{spec['resource_type']} resources in {spec['environment']}"
        )

    policy = {"approved": len(violations) == 0, "violations": violations}
    history = state.get("history", []) + [f"policy_agent: {policy}"]
    return {"policy": policy, "history": history}
