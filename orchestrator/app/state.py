"""Shared state schema passed between every node in the graph."""
from typing import List, Literal, Optional
from typing_extensions import TypedDict


class InfraRequest(TypedDict, total=False):
    raw_text: str
    requester: str


class RequestSpec(TypedDict, total=False):
    resource_type: str  # postgres | redis | s3 | ...
    team: str
    environment: str  # dev | staging | prod
    name: str  # derived, e.g. team-environment-resourcetype


class PolicyResult(TypedDict, total=False):
    approved: bool
    violations: List[str]


class TerraformPlan(TypedDict, total=False):
    module: str
    diff_summary: str
    estimated_monthly_cost_usd: float
    workspace_key: str  # deterministic key -> idempotent apply


class OrchestratorState(TypedDict, total=False):
    request: InfraRequest
    spec: RequestSpec
    policy: PolicyResult
    plan: TerraformPlan
    approval: Optional[Literal["approved", "rejected"]]
    approver: Optional[str]
    status: str
    next: str
    history: List[str]
