# Adding New Resource Types to the Golden Path

This guide is for platform engineers who want to add a new AWS resource type
(e.g. `rds-mysql`, `eks-cluster`, `sqs-queue`) so developers can request it
through the infra request copilot.

---

## What controls which resources are allowed

Everything lives in **one file**:

```
orchestrator/app/golden_paths.py
```

This is the platform catalog. It defines:
- Which resource types are on the golden path (`ALLOWED_RESOURCE_TYPES`)
- Per-team quotas (`QUOTAS`)
- Which Terraform module to use for each type (`TERRAFORM_MODULES`)
- Estimated monthly cost per environment (`ESTIMATED_MONTHLY_COST_USD`)

The AI (LLM) understands any resource name in natural language — it does not need
to be hardcoded anywhere. The golden path file controls what gets **approved** vs
**rejected**, not what gets **understood**.

---

## Current golden-path resources

| Type | Terraform module | Dev | Staging | Prod |
|---|---|---|---|---|
| `postgres` | `infra/modules/rds-postgres/` | $25/mo | $60/mo | $400/mo |
| `redis` | `infra/modules/elasticache-redis/` | $15/mo | $40/mo | $250/mo |
| `s3` | `infra/modules/s3-bucket/` | $1/mo | $2/mo | $10/mo |
| `kafka-topic` | `infra/modules/msk-topic/` | $0 | $0 | $5/mo |
| `iam-user` | `infra/modules/iam-user/` | $0 | $0 | $0 |
| `ec2` | `infra/modules/ec2-instance/` | $10/mo | $30/mo | $200/mo |

---

## How to add a new resource type

### Step 1 — Add the Terraform module

Create a folder under `infra/modules/<resource-type>/` with three files:

```
infra/modules/<resource-type>/
  variables.tf    ← inputs: name, environment, plus resource-specific vars
  main.tf         ← the actual AWS resources
  outputs.tf      ← at minimum: the resource ARN or endpoint
```

**Required variables in every module** (the provisioning agent passes these):

```hcl
variable "name" {
  description = "Unique name derived from workspace_key (e.g. team-env-type)"
  type        = string
}

variable "environment" {
  type = string  # dev | staging | prod
}
```

See existing modules for reference — `infra/modules/rds-postgres/` is the most
complete example.

### Step 2 — Register it in `golden_paths.py`

Open `orchestrator/app/golden_paths.py` and add entries in all four places:

```python
# 1. Allow the type
ALLOWED_RESOURCE_TYPES = {
    "postgres", "redis", "s3", "kafka-topic", "iam-user", "ec2",
    "rds-mysql",   # ← add here
}

# 2. Set quotas
QUOTAS = {
    "default": {
        "postgres": 3, "redis": 3, "s3": 10, "kafka-topic": 20,
        "iam-user": 5, "ec2": 5,
        "rds-mysql": 3,   # ← add here
    },
}

# 3. Point to the Terraform module
TERRAFORM_MODULES = {
    "postgres": "modules/rds-postgres",
    ...
    "rds-mysql": "modules/rds-mysql",   # ← add here
}

# 4. Set cost estimates (used in the approval UI)
ESTIMATED_MONTHLY_COST_USD = {
    "postgres": {"dev": 25, "staging": 60, "prod": 400},
    ...
    "rds-mysql": {"dev": 20, "staging": 50, "prod": 350},   # ← add here
}
```

### Step 3 — Run tests

```bash
make test
```

Existing tests should still pass. Add a test for the new type in
`tests/test_policy_agent.py` if you want to lock in its behavior.

### Step 4 — Restart the service

```bash
make down && make dev
```

That's it. Developers can now say "I need a MySQL database for team X, staging"
and the AI will extract `rds-mysql`, policy will approve it, plan will select
your new module, and the platform engineer will see the cost estimate in the
approval queue.

---

## How the type name must be written

The type name in `ALLOWED_RESOURCE_TYPES` must match what the LLM extracts.
Follow this convention:

| Pattern | Examples |
|---|---|
| Single-word AWS service | `ec2`, `s3`, `redis`, `lambda` |
| Service + variant (hyphen) | `rds-mysql`, `rds-postgres`, `iam-user` |
| No spaces, no underscores, lowercase | `kafka-topic` not `Kafka Topic` |

The LLM (Ollama or OpenAI) will naturally use these names when parsing requests.
If you're in **heuristic mode** (no LLM), also add the type to
`_KNOWN_NON_GOLDEN_PATH_RESOURCE_TYPES` in `orchestrator/app/agents/spec_agent.py`
so the keyword parser can find it.

---

## What happens when a type is NOT on the golden path

The `policy_agent` returns a single violation:

```
resource_type 'rds-mysql' is not on the golden path
```

The request is rejected cleanly, the run ends, and no approval is requested.
The developer sees this immediately in the portal or API response — no silent
failure, no wrong provisioning.

---

## Security considerations when adding a new resource type

**Guardrails are separate from the golden path.** The `guardrails` node
(`orchestrator/app/agents/guardrails.py`) blocks destructive intent and prompt
injection on every request before any agent runs. Adding a resource type to
`golden_paths.py` does not affect guardrails — they are always active.

**Scope the Terraform module's IAM permissions.** Each module runs under the
orchestrator pod's IRSA role (`infra/main.tf`). When you add a new module, also
add the minimum required permissions to `aws_iam_policy.orchestrator_secrets_read`
in `infra/main.tf`. For example, adding `rds-mysql` requires
`rds:CreateDBInstance`, `rds:DescribeDBInstances` — not `rds:DeleteDBInstance`.
Never add wildcard (`*`) actions.

**Quota defaults matter.** A quota of `0` means no one can create that resource
type — it will pass `policy_agent`'s golden-path check but fail the quota check.
Set a non-zero quota only for resource types whose Terraform module is ready and
whose blast radius you have reviewed.

---

## Wiring up the real Terraform apply

Currently `provisioning_agent` simulates the apply (logs a line, returns
`status: provisioned`). To make it real, replace the comment in
`orchestrator/app/agents/provisioning_agent.py` with:

```python
import subprocess, os

plan = state["plan"]
workspace = plan["workspace_key"]
module_path = f"infra/{plan['module']}"

subprocess.run([
    "terraform", f"-chdir={module_path}",
    "workspace", "new", workspace
], check=False)  # "new" fails if workspace already exists — that's fine

subprocess.run([
    "terraform", f"-chdir={module_path}",
    "workspace", "select", workspace
], check=True)

subprocess.run([
    "terraform", f"-chdir={module_path}",
    "apply", "-input=false", "-auto-approve",
    f"-var=name={workspace}",
    f"-var=environment={state['spec']['environment']}",
], check=True)
```

The `workspace_key` (e.g. `billing-staging-postgres`) is deterministic from the
request spec, so a resumed/replayed run targeting the same workspace is idempotent.
