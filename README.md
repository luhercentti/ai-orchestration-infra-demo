# AI Multi-Agent Orchestration Demo (LangGraph)

A production-shaped demo of a LangGraph-based multi-agent system, built to show three things together rather than in isolation:

1. **Infra fundamentals** — Terraform + Kubernetes done the way a platform team would do them.
2. **Agentic workflow depth** — a supervisor/specialist LangGraph with durable checkpointing,
   human-in-the-loop approval, and replay-safe tool calls.
3. **Platform-as-a-product thinking** — a golden path for adding new agents, an explicit
   SLO contract, and dashboards to prove it, not just logs.

The scenario: a **self-service infrastructure request copilot** — a developer asks
for infra (e.g. "a new Postgres database for team X, staging") in plain language,
a **supervisor agent** routes the request through policy checks and a Terraform
plan, and a **platform engineer approves** before anything is actually provisioned.
This is the "platform as a product" pitch made concrete: a golden-path request
mediated by agents instead of a ticket queue.

Other candidate scenarios (incident response, PR/deploy readiness, cost
optimization) are documented in [OTHER_EXAMPLES.md](OTHER_EXAMPLES.md) for later.

**Step-by-step local and production deployment instructions are in [RUNBOOK.md](RUNBOOK.md).**

**Full end-to-end request flow (who does what, when, and how local differs from prod) is in [FLOW.md](FLOW.md).**

## How the multi-agent orchestration actually works

This is the core mechanic of the demo, explained step by step:

1. **The graph is the orchestrator.** Instead of one LLM call, `orchestrator/graph.py`
   defines a directed graph: each **node** is either an agent (an LLM call with a
   specific role/prompt) or a tool (a plain function). **Edges** define what can run
   next. There is no fixed script — the path through the graph is decided at runtime.

2. **Shared state, not message-passing.** Every node reads and writes to one shared
   **state object** (the request, conversation history, retrieved documents, tool
   results, routing decision so far). Agents don't call each other directly — they
   read what previous agents wrote to state and add their own contribution to it.
   This is what makes the system inspectable: at any point you can dump the state
   and see exactly what every agent has done so far.

3. **The supervisor node decides routing.** On each turn, the supervisor agent looks
   at the current state and outputs a decision (e.g. "parse the request into a spec",
   "run policy checks", "generate the Terraform plan", "this needs approval", "we're
   done — provision it"). A **conditional edge** reads that decision and routes
   execution to the matching node. This is the "explicit graph with conditional
   routing" idea — routing logic is data (the supervisor's output), not hardcoded
   if/else chains scattered through the app.

4. **Specialist agents do one job each.** A **spec agent** turns the free-text
   request into a structured spec matched against golden-path templates; a
   **policy agent** checks it against quota, naming conventions, and compliance
   rules; a **plan agent** renders the Terraform diff from the matching module.
   Each returns control to the supervisor by updating state — the supervisor
   re-evaluates and decides the next hop. This loop (supervisor → specialist →
   supervisor → ...) continues until the supervisor decides the task is complete.

5. **Checkpointing makes every hop durable.** After each node runs, LangGraph
   persists the full state to Postgres (`orchestrator/` checkpointer config). This
   means: if the process crashes mid-run, a new pod can resume exactly where the
   run left off; a run can be paused indefinitely and resumed hours later; and every
   past run can be replayed step by step for debugging — you're not re-running the
   whole conversation from scratch.

6. **Human-in-the-loop is a graph interrupt, not a side channel.** Before the
   **provisioning agent** applies the Terraform plan, the graph hits an
   `interrupt()` node. This pauses execution and persists the checkpoint — the run
   is literally frozen in the database waiting for a platform engineer's decision.
   An approval (via API/Slack/queue) simply writes the decision back and resumes
   the graph from that exact checkpoint. There is no separate "pending approvals"
   system to keep in sync with the agent state — the graph *is* the source of
   truth.

7. **Tool calls are idempotent by design.** Because a paused/replayed run can
   re-execute a node, the provisioning agent's `terraform apply` call uses a
   deterministic workspace/state key derived from the request, so a resumed run
   can never double-provision or drift the same resource.

In short: the "AI orchestration" here is not one model deciding everything in a
single prompt — it's a graph of narrow-purpose agents, a supervisor that routes
between them based on shared state, and a persistence layer that makes the whole
multi-step process durable, pausable, and safely resumable.

## Repository layout

```
infra/            Terraform for AWS (EKS, RDS Postgres, ElastiCache Redis, IAM/IRSA, Secrets Manager)
k8s/              Kubernetes manifests / Helm chart for the orchestrator service
orchestrator/     The LangGraph app itself (FastAPI + graph nodes + checkpointing)
platform/         Golden-path tooling: Makefile/CLI, agent scaffolding, onboarding docs
observability/    Tracing (Langfuse/OTel), Grafana dashboards, SLO definitions
tests/            pytest (unit + routing), eval dataset, load test (k6/Locust)
docker-compose.yml  Local, cloud-free reproduction of the full stack
Makefile          Single entrypoint: make dev / make test / make deploy
```

### `infra/` — Terraform (provision AWS infrastructure, one-time setup)
Contains four `.tf` files that describe every AWS resource the orchestrator needs
to run in production: VPC + subnets, EKS cluster (where the K8s workloads run),
RDS Postgres (the LangGraph checkpoint store — what makes runs durable and
resumable across pod restarts), ElastiCache Redis (fast-path streaming state),
IAM roles scoped per-pod via IRSA (the orchestrator pod gets only the permissions
it needs — read two secrets — not broad node-level credentials), and Secrets
Manager entries for model API keys.

This folder is **not** used for local development — `docker-compose.yml` covers
that. It is run once (`terraform apply`) when standing up a new environment, and
again when infrastructure needs to change. It does not deploy the application;
that is `k8s/`. Kept separate because infra changes rarely and carries its own
Terraform state lifecycle, while the app can deploy many times a day.

Files: `versions.tf` (provider + backend config), `variables.tf` (region, env,
instance sizes), `main.tf` (all resources), `outputs.tf` (cluster name, DB
endpoint, Redis endpoint — used as inputs to the K8s deployment steps).

### `k8s/` — Kubernetes manifests (deploy and operate the orchestrator on EKS)
Describes how the orchestrator container runs on the EKS cluster that `infra/`
builds. This is **not** used locally — `docker-compose.yml` replaces it for
development. It is applied with `kubectl apply -f k8s/` when deploying or updating
the live service.

- `namespace.yaml` — isolates all resources under `ai-orchestration-demo`
- `deployment.yaml` — 3 replicas, resource requests/limits sized from load tests,
  readiness + liveness probes hitting `/health`, and a `preStop` sleep so
  in-flight graph runs have time to reach their next checkpoint before the pod
  receives SIGTERM (without this, a rolling update can interrupt a mid-run graph)
- `service.yaml` — ClusterIP; exposes the app inside the cluster (add an Ingress
  or AWS Load Balancer Controller annotation to expose it externally)
- `hpa.yaml` — autoscales replicas 3→10 based on CPU utilisation
- `pdb.yaml` — PodDisruptionBudget ensures at least 2 replicas stay up during
  node drain/cluster upgrades, preventing a complete outage
- `secret.example.yaml` — documents the expected secret shape; real values come
  from Secrets Manager via the External Secrets Operator in a team setup

### `orchestrator/` — the LangGraph application (the live service)
This is the only folder that runs at request time. It is the FastAPI service that
receives HTTP calls, runs the LangGraph graph, and returns results. Everything else
in the repo exists to deploy, test, or observe this folder.

- `Dockerfile` — builds the container image pushed to ECR and run in K8s
- `requirements.txt` — pinned Python dependencies
- `app/main.py` — three FastAPI endpoints: `POST /requests` (start a run),
  `GET /requests/{id}` (inspect state), `POST /requests/{id}/approve` (resume)
- `app/graph.py` — assembles the StateGraph: registers every node and edge,
  wires the Postgres checkpointer, returns the compiled graph
- `app/state.py` — the shared state schema (`OrchestratorState`) — every node
  reads from and writes to this single object; nothing is passed between agents
  directly
- `app/agents/supervisor.py` — the routing brain; reads the current state and
  decides which node runs next; the only place routing logic lives
- `app/agents/spec_agent.py` — parses free-text into a structured spec; uses the
  LLM if `OPENAI_API_KEY` is set, otherwise falls back to keyword heuristics
- `app/agents/policy_agent.py` — checks the spec against golden-path rules
  (allowed resource types, environments, per-team quota)
- `app/agents/plan_agent.py` — selects the right Terraform module and produces a
  cost estimate; assigns a deterministic `workspace_key` so any later apply is
  idempotent
- `app/agents/human_approval.py` — calls `interrupt()` to freeze the run;
  execution does not continue until someone calls the approve endpoint
- `app/agents/provisioning_agent.py` — executes the approved plan (simulated here;
  real implementation runs `terraform apply` against the workspace)
- `app/checkpointer.py` — returns a Postgres checkpointer when `DATABASE_URL` is
  set, or an in-memory checkpointer for tests/CI (no database needed)
- `app/golden_paths.py` — the platform catalog: allowed resource types, Terraform
  module paths, per-team quotas, cost table
- `app/llm.py` — LLM client factory; returns `None` when no API key is set so
  agents fall back to deterministic logic and the demo works offline
- `app/tracing.py` — attaches Langfuse callback to graph invocations; a no-op
  when `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are unset

### `platform/` — golden-path tooling (for teams adding new agents)
Contains the tooling that makes this a platform rather than a one-off script.
It is **not** used at runtime by the live service and is **not** needed to run
the demo locally. It is used by any engineer who wants to extend the orchestrator
with a new specialist agent.

- `scaffold_agent.py` — generates a new agent file from a template
  (`make new-agent NAME=cost_agent`), pre-wired with the correct function
  signature and state types, and prints the exact three steps needed to register
  it in the graph. The point: a new agent should take minutes to add, not require
  reading the entire codebase.

The root `Makefile` is also part of this layer — it is the single entrypoint so
no one has to memorise docker/pip/pytest commands (`make dev`, `make test`,
`make new-agent NAME=x`).

### `observability/` — reliability contract and tracing config
This folder answers the question: "how do you know the system is healthy?" It is
**not** application code and does **not** run at request time. It is a versioned
set of operational commitments and wiring configs.

- `slo.yaml` — five explicit SLOs with targets and measurement sources:
  routing latency (p95 < 2s), checkpoint durability (zero write failures),
  human-approval turnaround (p95 < 4h), provisioning success rate (≥ 99%),
  and end-to-end error rate (< 1%). These are the numbers your dashboards and
  alerts should be built against. Keeping them as a versioned file — not a
  dashboard setting someone clicked — means they are reviewable, diffable, and
  don't silently drift.

Tracing is wired in `orchestrator/app/tracing.py` (not in this folder) and emits
a per-node span to Langfuse for every graph run when `LANGFUSE_PUBLIC_KEY` and
`LANGFUSE_SECRET_KEY` are set. When they are not set, tracing is a no-op and the
service runs normally — nothing breaks.

### `tests/` — correctness checks for `orchestrator/app/`
These tests have one purpose: verify that the code in `orchestrator/app/` behaves
correctly before you ship a change. They do **not** run at API call time and are
never executed by the live service. Run them locally with `make test` after any
change to the graph, agents, or routing logic — takes ~1 second, no Docker, no
database, no API key needed (uses LangGraph's in-memory checkpointer).

The CI pipeline (`.github/workflows/ci.yml`) runs the same `make test` on demand
— trigger it manually from the GitHub Actions tab before merging or deploying.

Four test modules:

- **`test_supervisor.py`** — unit tests for the routing brain: confirms the
  supervisor sends the run to `spec_agent` when no spec exists yet, to
  `policy_agent` once a spec is present, to `plan_agent` once policy passes, to
  `human_approval` once a plan exists, to `provisioning_agent` after approval, and
  to `END` once provisioned. If you change routing logic, these break first.

- **`test_spec_agent.py`** — confirms the spec agent correctly extracts
  `resource_type`, `team`, and `environment` from free-text (e.g. "postgres for
  team billing, staging") and applies safe defaults when fields are missing.

- **`test_policy_agent.py`** — confirms the policy agent approves valid specs and
  rejects disallowed resource types (e.g. `mongodb`, which is not on the golden
  path) and unknown environments.

- **`test_graph.py`** — end-to-end integration test of the whole graph using
  LangGraph's in-memory checkpointer: submits a request, asserts the run pauses at
  the `human_approval` interrupt with the correct plan in state, resumes it with an
  approval decision, and asserts the final status is `provisioned`. Also tests the
  rejection path (policy failure ends the run before reaching the approval gate).

## Local run (no cloud required)

`docker-compose.yml` spins up Postgres (checkpoints), Redis, and the orchestrator
together, so the full demo runs on a laptop with no AWS cost and no API key
required (the spec/policy/plan agents fall back to deterministic heuristics when
`OPENAI_API_KEY` is unset — see `orchestrator/app/llm.py`). `infra/` and `k8s/`
describe the path to production; they aren't required to see the demo work
end to end.

```bash
cp .env.example .env        # fill in OPENAI_API_KEY / LANGFUSE_* if you want them
make dev                    # docker compose up --build
make test                   # pytest, no Docker required (in-memory checkpointer)

# once running:
curl -X POST localhost:8000/requests \
  -H 'content-type: application/json' \
  -d '{"raw_text": "I need a postgres database for team billing, staging", "requester": "alice"}'
# -> { "thread_id": "...", "interrupts": [ ... approval payload ... ] }

curl -X POST localhost:8000/requests/<thread_id>/approve \
  -H 'content-type: application/json' \
  -d '{"approval": "approved", "approver": "platform-team"}'

curl localhost:8000/requests/<thread_id>   # inspect state at any point
```

`infra/` (Terraform: EKS, RDS, ElastiCache, IRSA) and `k8s/` (Deployment, HPA,
PDB, probes) describe the production deployment path and are syntactically
validated (`terraform validate`) but not applied as part of this demo.


## Why this shape

Terraform and Kubernetes are the baseline expectation. What differentiates this
repo is showing all three layers together: infra done properly, an agentic
workflow that accounts for real failure modes (replay, idempotency, versioned
graphs), and a platform layer that treats reliability and developer experience as
first-class, versioned commitments rather than afterthoughts.
