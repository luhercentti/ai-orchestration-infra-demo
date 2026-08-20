"""Parses a free-text infra request into a structured RequestSpec.

Uses the LLM if configured; otherwise falls back to keyword heuristics so the
demo is fully reproducible offline without an API key.
"""
import json
import logging
import re

from ..golden_paths import ALLOWED_ENVIRONMENTS, ALLOWED_RESOURCE_TYPES
from ..llm import classify
from ..state import OrchestratorState

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Extract a structured infra request and return ONLY a JSON object with keys: "
    "resource_type (string — the AWS/cloud resource type, e.g. postgres, redis, s3, "
    "ec2, iam-user, vpc, rds, lambda, etc.), "
    "team (string — the team or owner name), "
    "environment (one of: dev, staging, prod). "
    "If a field is not mentioned, use 'unknown' for team and 'dev' for environment. "
    "Return only the JSON object, no explanation, no markdown."
)

# Used only in heuristic fallback mode (no LLM configured). When the LLM is
# active it extracts any resource type from natural language without this list.
_KNOWN_NON_GOLDEN_PATH_RESOURCE_TYPES = {
    "mongodb", "mysql", "dynamodb", "elasticsearch",
    "ec2", "vm", "lambda", "sqs", "sns",
    "ecs", "eks", "fargate", "kinesis", "cloudfront",
    "iam", "vpc", "rds", "alb", "nlb",
}


def _parse_llm_result(llm_result: str) -> dict | None:
    """Parses the LLM's JSON response. Returns None if unparseable."""
    try:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", llm_result.strip())
        data = json.loads(cleaned)
        if isinstance(data.get("resource_type"), str):
            return {
                "resource_type": data["resource_type"].lower().strip(),
                "team": str(data.get("team", "unknown")).lower().strip() or "unknown",
                "environment": str(data.get("environment", "dev")).lower().strip(),
            }
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning("Failed to parse LLM spec response: %s | raw: %s", e, llm_result)
    return None


def _extract_resource_type(text: str) -> str:
    text_lower = text.lower()
    for r in sorted(ALLOWED_RESOURCE_TYPES, key=len, reverse=True):
        if r in text_lower:
            return r
    for r in sorted(_KNOWN_NON_GOLDEN_PATH_RESOURCE_TYPES, key=len, reverse=True):
        if r in text_lower:
            return r
    match = re.search(
        r"\b(?:need|want|create|setup|provision|spin up|a|an)\s+(?:a\s+|an\s+)?([a-z][a-z0-9_-]+)",
        text_lower,
    )
    if match:
        candidate = match.group(1)
        if candidate not in {"a", "an", "the", "new", "some", "my", "our"}:
            return candidate
    return "unknown"


def _heuristic_parse(text: str) -> dict:
    text_lower = text.lower()
    resource_type = _extract_resource_type(text_lower)
    environment = next((e for e in ALLOWED_ENVIRONMENTS if e in text_lower), "dev")
    match = re.search(r"team[:\s]+([a-zA-Z0-9_-]+)", text_lower)
    team = match.group(1) if match else "unknown"
    return {"resource_type": resource_type, "team": team, "environment": environment}


def spec_agent(state: OrchestratorState) -> dict:
    raw_text = state["request"]["raw_text"]

    llm_result = classify(SYSTEM_PROMPT, raw_text)
    parsed = _parse_llm_result(llm_result) if llm_result else None

    if parsed is None:
        if llm_result:
            logger.warning("LLM returned unparseable spec, falling back to heuristics")
        parsed = _heuristic_parse(raw_text)

    spec = {
        **parsed,
        "name": f"{parsed['team']}-{parsed['environment']}-{parsed['resource_type']}",
    }
    history = state.get("history", []) + [f"spec_agent: parsed spec {spec}"]
    return {"spec": spec, "history": history}
