# Runbook — Local Development & Production Deployment

This file is the operational companion to the root README. It covers:
1. What each folder does and how data flows through the system at runtime
2. Running the demo locally on a laptop (no cloud account needed)
3. Visualising the graph with LangGraph Studio
4. Deploying to production on AWS (EKS + RDS + ElastiCache)

---

## 1. Solution overview — folder roles and runtime flow

```
Developer request (HTTP)
        │
        ▼
orchestrator/          ← FastAPI + LangGraph graph (the brains)
  app/main.py          ← receives POST /requests, starts a graph run
  app/graph.py         ← defines nodes, edges, conditional routing
  app/agents/
    supervisor.py      ← routing: decides which node runs next
    spec_agent.py      ← parses free-text into a structured spec
    policy_agent.py    ← checks golden-path rules, quota, naming
    plan_agent.py      ← renders the Terraform diff + cost estimate
    human_approval.py  ← pauses the run here, waits for a decision
    provisioning_agent.py ← executes (simulated) terraform apply
  app/state.py         ← shared state schema all nodes read/write
  app/checkpointer.py  ← Postgres checkpoint store (MemorySaver in tests)
  app/tracing.py       ← optional Langfuse tracing (no-op if unconfigured)
  app/golden_paths.py  ← catalog: allowed types, modules, quotas, cost table

        │ state persisted after every node
        ▼
Postgres (RDS in prod, local container in dev)
  ← stores checkpoints; a paused run survives pod restarts and can be
    resumed by any replica, not just the one that started the run

        │ routing decisions flow through
        ▼
Redis (ElastiCache in prod, local container in dev)
  ← fast-path: token streaming, pub/sub events pushed to the client

        │ traces (optional)
        ▼
Langfuse  ← per-node latency, token cost, prompt/output for each hop

infra/    ← Terraform; provisions the AWS resources above (one-time setup)
k8s/      ← Kubernetes manifests; deploys the orchestrator onto the EKS cluster
platform/ ← golden-path tooling: scaffold_agent.py, Makefile
observability/ ← slo.yaml: the reliability contract dashboards/alerts use
tests/    ← pytest (no Postgres needed; uses in-memory checkpointer)
```

### Runtime flow for a single request

```
POST /requests  →  supervisor  →  spec_agent  →  supervisor
                →  policy_agent  →  supervisor
                →  plan_agent   →  supervisor
                →  human_approval  (INTERRUPT — run frozen in Postgres)
                        ↓
              platform engineer calls POST /requests/<id>/approve
                        ↓
                →  supervisor  →  provisioning_agent  →  supervisor  →  END
```

At each arrow, LangGraph checkpoints state to Postgres before the next node runs.
If the process crashes anywhere in the chain, the run can be resumed from the last
checkpoint by any pod — no data is lost.

---

## 2. Local run (no AWS account, no API keys required)

### Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin) — to run Postgres + Redis + Portal
- Python 3.12 (for running tests without Docker)
- Node.js 20+ (portal runs inside Docker via Compose, but needed if running it directly)
- `make` (pre-installed on macOS/Linux)

### 2a. Start the full stack

```bash
git clone <repo-url>
cd ai-orchestration-demo

cp .env.example .env
# .env is already usable with empty API keys — agents run in heuristic mode.
# Optionally fill in OPENAI_API_KEY and LANGFUSE_* if you want them.

make dev
# Starts: postgres:16 + redis:7 + orchestrator + portal (Next.js)
# Orchestrator API:  http://localhost:8000
# Swagger UI:        http://localhost:8000/docs  ← interactive API browser (see note below)
# Portal (web GUI):  http://localhost:3001       ← submit requests + approval queue
```

> **Swagger UI** (`/docs`) is FastAPI's auto-generated interactive API browser. It
> lists all five endpoints (`POST /requests`, `GET /requests`, `GET /requests/{id}`,
> `POST /requests/{id}/approve`, `GET /health`), lets you fill in a form for each
> one, click Execute, and see the full JSON response — exactly like `curl` but in
> a browser tab with no typing. Useful for quickly exploring the API or debugging
> without copy-pasting `curl` commands.

### 2b. Use the portal (recommended for demos)

Open **http://localhost:3001** in a browser:

- **New Request** page (`/`) — fill in the plain-language request and your name,
  click Submit. The graph runs all agents automatically and the page shows the
  parsed spec, Terraform module, and estimated cost once the run pauses.
- **Approval Queue** (`/approvals`) — lists all submitted requests with their
  status. Pending-approval runs show Approve / Reject buttons. Click Approve and
  the graph resumes; the status updates to `provisioned`.

### 2c. Exercise the full agent flow via curl

```bash
# Step 1 — submit an infra request (this starts the graph run)
#
# What happens internally when you run this:
#   1. FastAPI receives the request and creates a new graph run (thread_id = UUID)
#   2. supervisor → spec_agent (parses "postgres / billing / staging" from the text)
#   3. supervisor → policy_agent (checks quota and golden-path rules → approved)
#   4. supervisor → plan_agent (selects modules/rds-postgres, estimates $60/mo)
#   5. supervisor → human_approval — graph hits interrupt(), freezes here,
#      persists full state to Postgres, and returns the response to you
#
# The API call returns immediately once the run is frozen. It does NOT wait for
# a human to approve — that is a separate call (Step 3 below).
#
# Copy the "thread_id" from the response — you need it for Steps 2 and 3.
curl -s -X POST localhost:8000/requests \
  -H 'content-type: application/json' \
  -d '{"raw_text": "I need a postgres database for team billing, staging", "requester": "alice"}' \
  | python3 -m json.tool

# Example response shape:
# {
#   "thread_id": "3f2a1c...",          ← copy this
#   "values": {
#     "spec":   { "resource_type": "postgres", "team": "billing", "environment": "staging" },
#     "policy": { "approved": true, "violations": [] },
#     "plan":   { "module": "modules/rds-postgres", "estimated_monthly_cost_usd": 60 }
#   },
#   "next_nodes": ["supervisor"],
#   "interrupts": [{ "value": { "message": "Approve provisioning?", ... } }]
#                                      ↑ this confirms the run is paused and waiting
# }

# Step 2 — inspect the current state (frozen at the approval gate)
curl -s localhost:8000/requests/<thread_id> | python3 -m json.tool

# Step 3 — approve (resume the graph)
curl -s -X POST localhost:8000/requests/<thread_id>/approve \
  -H 'content-type: application/json' \
  -d '{"approval": "approved", "approver": "platform-team"}' \
  | python3 -m json.tool
# status should now be "provisioned"

# Step 4 — try a rejection (quota/naming policy failure)
curl -s -X POST localhost:8000/requests \
  -H 'content-type: application/json' \
  -d '{"raw_text": "I need a mongodb for team x", "requester": "bob"}' \
  | python3 -m json.tool
# policy_agent rejects it; run ends without reaching human_approval
```

### 2c. Run the test suite (no Docker needed)

```bash
make test
# Creates a virtualenv, installs requirements, runs pytest.
# Uses MemorySaver (in-memory checkpointer) — no Postgres required.
# 15 tests: supervisor routing, spec parsing, policy checks, full graph HITL flow.
```

### 2d. Scaffold a new agent node (golden-path demo)

```bash
make new-agent NAME=cost_agent
# Creates orchestrator/app/agents/cost_agent.py from the template and
# prints the 3 steps to wire it into the graph.
```

### 2e. Stop the local stack

```bash
make down
# docker compose down -v  (removes volumes — checkpoint data is wiped)
```

---

## 3. Visualise the graph with LangGraph Studio

LangGraph Studio is a free macOS desktop app that connects to a running LangGraph
server and shows the graph visually — nodes, edges, live state at each hop, which
node is executing, and a full history of past runs you can replay step by step.

### Install

Download from: **https://studio.langchain.com** (macOS only; free)

### Run

`make dev` must already be running (the orchestrator needs to be up). Then:

```bash
# In the repo root — langgraph.json points Studio at the graph
langgraph dev
# or open LangGraph Studio and point it at the repo folder
```

Studio reads `langgraph.json` (already in the repo root) which tells it:
- Where the graph file is (`orchestrator/app/graph.py:build_graph`)
- Which `.env` file to use

Once connected you can:
- See the full graph diagram (nodes + edges)
- Submit a test input and watch each node light up as it executes
- Inspect the shared state after each hop (spec, policy result, plan, etc.)
- See the `interrupt()` pause at `human_approval` and resume it from the UI
- Replay any past run from any checkpoint

> Studio is the best way to **demo the graph visually** to an audience — it makes
> the supervisor routing and state flow visible in real time without any code.

---

## 4. Production deployment on AWS (EKS)

### Prerequisites

- AWS CLI configured (`aws configure`) with an IAM user/role that can create EKS,
  RDS, ElastiCache, and IAM resources
- Terraform >= 1.7 (`brew install terraform` or use tfenv)
- kubectl + helm
- Docker (to build and push the image)
- An ECR repository (or any container registry)

### Step 1 — Provision AWS infrastructure with Terraform

```bash
cd infra

# Initialise — downloads AWS provider and community modules
terraform init

# Review what will be created (EKS, RDS, ElastiCache, IAM roles, VPC)
terraform plan -var="environment=staging"

# Apply — this takes ~15-20 min (EKS cluster creation dominates)
terraform apply -var="environment=staging"

# Capture outputs for the next steps
terraform output -json > ../infra-outputs.json
```

Key resources created:
| Resource | Purpose |
|---|---|
| VPC + subnets | Private networking; EKS nodes and RDS are not publicly exposed |
| EKS cluster | Runs the orchestrator Deployment |
| RDS Postgres | LangGraph checkpoint store (durable, resumable runs) |
| ElastiCache Redis | Fast-path streaming state |
| AWS Secrets Manager | API keys; accessed via IRSA (pod-level IAM, not node-wide) |
| IRSA role | Least-privilege IAM for the orchestrator pod |

### Step 2 — Build and push the container image

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build for linux/amd64 (EKS nodes are x86 by default unless you change instance type)
docker buildx build --platform linux/amd64 \
  -t <account-id>.dkr.ecr.us-east-1.amazonaws.com/ai-orchestration-demo:latest \
  ./orchestrator --push
```

### Step 3 — Store secrets in AWS Secrets Manager

```bash
# Database credentials are auto-managed by RDS (manage_master_user_password = true)
# You only need to store the model API key manually:
aws secretsmanager put-secret-value \
  --secret-id "ai-orchestration-demo-staging/openai-api-key" \
  --secret-string "sk-..."
```

### Step 4 — Configure kubectl

```bash
aws eks update-kubeconfig \
  --region us-east-1 \
  --name $(cat infra-outputs.json | python3 -c "import sys,json; print(json.load(sys.stdin)['eks_cluster_name']['value'])")
kubectl get nodes   # should list your node group
```

### Step 5 — Create the Kubernetes namespace and secrets

```bash
kubectl apply -f k8s/namespace.yaml

# Create the secret (populate from Secrets Manager or directly for staging):
DB_URL=$(aws secretsmanager get-secret-value \
  --secret-id ai-orchestration-demo-staging/db-url \
  --query SecretString --output text)

kubectl create secret generic orchestrator-secrets \
  -n ai-orchestration-demo \
  --from-literal=DATABASE_URL="$DB_URL" \
  --from-literal=OPENAI_API_KEY="$(aws secretsmanager get-secret-value \
    --secret-id ai-orchestration-demo-staging/openai-api-key \
    --query SecretString --output text)"
```

In a real team setup you would replace this with the External Secrets Operator
pulling directly from Secrets Manager so secrets rotate automatically.

### Step 6 — Deploy the orchestrator

Update the image reference in `k8s/deployment.yaml` to match your ECR image, then:

```bash
# Apply in order: namespace first, then the rest
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/pdb.yaml

# Watch the rollout
kubectl rollout status deployment/orchestrator -n ai-orchestration-demo

# Tail logs
kubectl logs -f deployment/orchestrator -n ai-orchestration-demo
```

### Step 7 — Expose the service

The Service is `ClusterIP` (internal only). Options to expose it:
- **AWS Load Balancer Controller** (recommended for production) — annotate the
  Service or create an Ingress to provision an ALB
- **kubectl port-forward** for quick staging access:
  ```bash
  kubectl port-forward svc/orchestrator 8000:80 -n ai-orchestration-demo
  # then hit localhost:8000 as in local dev
  ```

### Step 8 — Verify end to end

```bash
# Port-forward or via ALB
curl -X POST http://<endpoint>/requests \
  -H 'content-type: application/json' \
  -d '{"raw_text": "postgres for team payments, prod", "requester": "alice"}'
```

Confirm in RDS that a checkpoint row was written:
```bash
kubectl exec -n ai-orchestration-demo deploy/orchestrator -- \
  python3 -c "
import os, psycopg
with psycopg.connect(os.environ['DATABASE_URL']) as c:
    print(c.execute('SELECT COUNT(*) FROM checkpoints').fetchone())
"
```

### Step 9 — Tear down (staging only)

```bash
cd infra
terraform destroy -var="environment=staging"
# Will fail if deletion_protection=true (prod only) — intentional safety guard.
```

---

## 5. Observability (both local and prod)

### Langfuse (optional tracing)

Set in `.env` (local) or Kubernetes secret (prod):
```
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com   # or your self-hosted URL
```

Once set, every graph run emits a trace with per-node span (latency, tokens, cost).
Use the Langfuse UI to validate the SLOs defined in `observability/slo.yaml`.

Self-hosted option — add to `docker-compose.yml` for local use:
```yaml
  langfuse:
    image: langfuse/langfuse:latest
    environment:
      DATABASE_URL: postgresql://langgraph:langgraph@postgres:5432/langfuse
    ports:
      - "3000:3000"
```

### SLO reference

See `observability/slo.yaml` for the full contract. Key numbers to alert on:
- `p95(supervisor node latency) > 2s` → investigate LLM latency or cold-start
- `checkpoint_write_error > 0` → RDS connectivity / storage issue
- `provisioning_success_rate < 99%` → tool failure or quota issue

---

## 6. Quick-reference cheat sheet

| Goal | Command |
|---|---|
| Start local stack (API + portal) | `make dev` |
| Open web portal | http://localhost:3001 |
| Open Swagger API browser | http://localhost:8000/docs |
| Visualise graph (LangGraph Studio) | `langgraph dev` (Studio app must be installed) |
| Run tests | `make test` |
| Stop local stack | `make down` |
| Add a new agent node | `make new-agent NAME=<name>` |
| Provision AWS infra | `cd infra && terraform apply` |
| Deploy to K8s | `kubectl apply -f k8s/` |
| Tear down AWS | `cd infra && terraform destroy` |
| Watch pod logs | `kubectl logs -f deploy/orchestrator -n ai-orchestration-demo` |
| Inspect a run's state | `GET /requests/<thread_id>` |
| Resume a paused run | `POST /requests/<thread_id>/approve` |
