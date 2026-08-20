# Other orchestration scenarios (for later)

The chosen demo scenario (self-service infrastructure request copilot) is described
in the root [README.md](README.md). These are the other DevOps/platform-engineer
scenarios considered, kept here to implement later. Each follows the same pattern:
supervisor + specialist agents + shared state + checkpointing + human-in-the-loop
gate before anything side-effecting.

## 1. Incident Response Copilot

**Trigger**: PagerDuty/Alertmanager fires an alert.

- **Supervisor** — classifies the alert (infra, app, deploy-related?) and decides
  which specialist to invoke.
- **Triage agent** — pulls recent logs (Loki/CloudWatch), metrics
  (Prometheus/Datadog), and recent deploys (ArgoCD/GitHub) to build a timeline.
- **Diagnosis agent** — correlates symptoms against a runbook knowledge base (RAG
  over internal wikis/postmortems), proposes root cause + confidence.
- **Remediation agent** — proposes an action (rollback deployment, scale up,
  restart pod, bump a rate limit) but never executes directly.
- **Human-in-the-loop gate** — on-call engineer approves/edits the remediation in
  Slack.
- **Executor tool** — runs the approved action via kubectl/Helm/Terraform, then a
  **verification agent** checks if the alert cleared.

Why it's strong: the clearest "agentic workflow with real consequences" story —
shows judgment about safe automation.

## 2. PR / Deployment Readiness Copilot

**Trigger**: a pull request opens or a deploy is requested.

- **Supervisor** — decides what checks are relevant based on what changed (infra
  files? app code? both?).
- **IaC review agent** — runs `terraform plan`/`tflint`/policy-as-code
  (OPA/Conftest) and summarizes risk (e.g. "this deletes a security group").
- **K8s manifest agent** — validates against org policies (resource limits set?
  probes present? PDB present?).
- **Cost agent** — estimates cost delta (Infracost) from the plan.
- **Human-in-the-loop gate** — a human approves merge/deploy given the aggregated
  risk summary.

Why it's strong: directly showcases Terraform/K8s literacy combined with agentic
reasoning, tied to daily platform-engineering work (every PR).

## 3. Cost/Resource Optimization Copilot

**Trigger**: scheduled (nightly) run over the cluster/account.

- **Supervisor** — decides which subsystem to analyze (compute, storage, unused
  resources).
- **Analysis agents (parallel)** — one for idle EC2/EKS nodes, one for oversized
  PVCs, one for unattached EBS/orphaned load balancers.
- **Recommendation agent** — aggregates into a prioritized action list with
  estimated savings.
- **Human-in-the-loop gate** — a human picks which recommendations to auto-apply
  vs skip.

Why it's strong: easy to demo with mock data, low "risk" story, good for a live
audience demo since nothing scary happens without approval.
