# End-to-End Flow — Who Does What and When

This document explains the full lifecycle of a request through the system:
what runs automatically, what requires a human, and how the local demo maps
to a real production deployment.

---

## The three roles

| Role | What they do |
|---|---|
| **Developer** | Submits an infra request in plain language via the API |
| **Graph (automated)** | Runs all agents, enforces policy, generates the plan, freezes at approval |
| **Platform engineer** | Reviews the frozen plan and approves or rejects it |

---

## Full request lifecycle, step by step

### Step 1 — Developer submits the request

```bash
curl -X POST localhost:8000/requests \
  -H 'content-type: application/json' \
  -d '{"raw_text": "I need a postgres database for team billing, staging", "requester": "alice"}'
```

The graph immediately runs through five agents **automatically**, without any human
involvement:

1. `supervisor` → routes to `spec_agent`
2. `spec_agent` → parses "postgres / billing / staging" from the free text, stores
   the structured spec in shared state
3. `supervisor` → routes to `policy_agent`
4. `policy_agent` → checks quota and golden-path rules → approved, no violations
5. `supervisor` → routes to `plan_agent`
6. `plan_agent` → selects `modules/rds-postgres`, estimates $60/mo, assigns a
   deterministic `workspace_key` (`billing-staging-postgres`)
7. `supervisor` → routes to `human_approval`
8. `human_approval` → calls `interrupt()` — **graph freezes here**

The full state is persisted to Postgres at this point. The API call returns
immediately with a `thread_id` and an `interrupts` payload. The developer's job
is done — they are now waiting for approval.

**The API does not wait for the platform engineer.** It returns as soon as the
graph is frozen. The run can wait in this state for minutes, hours, or days —
nothing is lost if the server restarts because the checkpoint is in Postgres.

---

### Step 2 — Platform engineer reviews and decides

The platform engineer inspects the frozen state:

```bash
curl localhost:8000/requests/<thread_id>
```

They see exactly what the developer asked for, whether policy approved it, which
Terraform module will run, and the estimated monthly cost. They can then approve:

```bash
curl -X POST localhost:8000/requests/<thread_id>/approve \
  -H 'content-type: application/json' \
  -d '{"approval": "approved", "approver": "platform-team"}'
```

Or reject:
```bash
curl -X POST localhost:8000/requests/<thread_id>/approve \
  -H 'content-type: application/json' \
  -d '{"approval": "rejected", "approver": "platform-team"}'
```

The graph resumes from the exact checkpoint in Postgres — not from scratch. It
continues from `human_approval` to the next step:

8. `supervisor` → routes to `provisioning_agent`
9. `provisioning_agent` → executes `terraform apply` against workspace
   `billing-staging-postgres` (simulated in the demo; real in production)
10. `supervisor` → routes to `END`

**In a real system**, the platform engineer would not use `curl`. The approval call
would come from a Slack bot command, an internal portal button, or an automated
policy engine — the API is the same, only the client changes.

---

### Step 3 — Developer checks the outcome

```bash
curl localhost:8000/requests/<thread_id>
# "status": "provisioned"    ← resource was created
# "approval": "approved"     ← who approved it
# "approver": "platform-team"
# "history": [...]           ← full audit trail of every agent hop
```

The `history` field is the complete audit log — every routing decision the
supervisor made, every agent that ran, and what it produced. This is what you'd
send to compliance, attach to a ticket, or use to debug a failed run.

---

## Sequence diagram

```
Developer                    Graph (automated)               Platform Engineer
    │                              │                                │
    ├── POST /requests ───────────►│                                │
    │                   supervisor → spec_agent                     │
    │                   supervisor → policy_agent                   │
    │                   supervisor → plan_agent                     │
    │                   supervisor → human_approval                 │
    │                        FROZEN (checkpoint in Postgres)        │
    │◄── returns thread_id ────────┤                                │
    │    + interrupts payload      │                                │
    │    (developer is now done)   │                                │
    │                              │◄──── POST /approve ───────────┤
    │                   supervisor → provisioning_agent             │
    │                   supervisor → END                            │
    │                              │                                │
    ├── GET /requests/<id> ───────►│                                │
    │◄── status: provisioned ──────┤                                │
```

---

## How the local demo differs from production

| | Local demo (`make dev`) | Production (AWS) |
|---|---|---|
| **Postgres** | Docker container on your laptop | RDS Aurora (provisioned by `infra/`) |
| **Redis** | Docker container on your laptop | ElastiCache (provisioned by `infra/`) |
| **Orchestrator** | Docker container via Compose | K8s Deployment on EKS (`k8s/`) |
| **`terraform apply`** | Simulated — log line only | Real — runs against AWS via `provisioning_agent` |
| **Approval client** | Raw `curl` | Slack bot / internal portal / policy engine |
| **Tracing** | Optional (`LANGFUSE_*` env vars) | Langfuse + SLOs from `observability/slo.yaml` |

The graph logic, agents, checkpointing, and human-in-the-loop interrupt are
**identical** in both environments. Only the infrastructure and approval client
change.

---

## When each folder becomes active

```
Before first production deploy:
  infra/     terraform apply        → EKS + RDS + Redis + IAM created (one-time)

On each deploy:
  tests/     make test              → verify orchestrator/app/ still works
  k8s/       kubectl apply -f k8s/  → new container version rolls out on EKS

At request time (every API call):
  orchestrator/  only this folder runs — FastAPI + LangGraph graph

When extending the platform:
  platform/  make new-agent NAME=x  → scaffold a new specialist agent

Ongoing operations:
  observability/  slo.yaml          → reference for dashboard + alert thresholds
```
