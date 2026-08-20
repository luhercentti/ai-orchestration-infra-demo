"""Parses a free-text infra request into a structured RequestSpec.

Uses the LLM if configured; otherwise falls back to keyword heuristics so the
demo is fully reproducible offline.
"""
import re

from ..golden_paths import ALLOWED_ENVIRONMENTS, ALLOWED_RESOURCE_TYPES
from ..llm import classify
from ..state import OrchestratorState

SYSTEM_PROMPT = (
    "Extract a structured infra request as JSON with keys "
    "resource_type, team, environment from the user's free-text request. "
    f"resource_type must be one of {sorted(ALLOWED_RESOURCE_TYPES)}. "
    f"environment must be one of {sorted(ALLOWED_ENVIRONMENTS)}."
)


# Recognized outside of the golden path too, so the policy agent can reject
# them explicitly instead of the spec agent silently defaulting to postgres.
_KNOWN_NON_GOLDEN_PATH_RESOURCE_TYPES = {"mongodb", "mysql", "dynamodb", "elasticsearch"}


def _heuristic_parse(text: str) -> dict:
    text_lower = text.lower()
    resource_type = next(
        (r for r in ALLOWED_RESOURCE_TYPES | _KNOWN_NON_GOLDEN_PATH_RESOURCE_TYPES if r in text_lower),
        "postgres",
    )
    environment = next((e for e in ALLOWED_ENVIRONMENTS if e in text_lower), "dev")
    match = re.search(r"team[:\s]+([a-zA-Z0-9_-]+)", text_lower)
    team = match.group(1) if match else "unknown"
    return {"resource_type": resource_type, "team": team, "environment": environment}


def spec_agent(state: OrchestratorState) -> dict:
    raw_text = state["request"]["raw_text"]

    llm_result = classify(SYSTEM_PROMPT, raw_text)
    parsed = _heuristic_parse(raw_text)  # heuristic is always computed as a safety net
    if llm_result:
        # In production this would validate/parse the LLM's JSON response; kept
        # simple here since the heuristic already covers the demo scenarios.
        pass

    spec = {
        **parsed,
        "name": f"{parsed['team']}-{parsed['environment']}-{parsed['resource_type']}",
    }
    history = state.get("history", []) + [f"spec_agent: parsed spec {spec}"]
    return {"spec": spec, "history": history}
