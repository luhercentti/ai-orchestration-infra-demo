from app.agents.supervisor import route, supervisor


def test_routes_to_spec_agent_when_no_spec():
    result = supervisor({"history": []})
    assert result["next"] == "spec_agent"


def test_routes_to_policy_agent_when_spec_present():
    state = {"spec": {"resource_type": "postgres"}, "history": []}
    assert supervisor(state)["next"] == "policy_agent"


def test_ends_when_policy_rejected():
    state = {"spec": {}, "policy": {"approved": False, "violations": ["quota exceeded"]}, "history": []}
    result = supervisor(state)
    assert result["next"] == "end"
    assert result["status"] == "policy_rejected"


def test_routes_to_plan_agent_when_policy_approved():
    state = {"spec": {}, "policy": {"approved": True, "violations": []}, "history": []}
    assert supervisor(state)["next"] == "plan_agent"


def test_routes_to_human_approval_when_plan_present():
    state = {
        "spec": {},
        "policy": {"approved": True, "violations": []},
        "plan": {"module": "modules/rds-postgres"},
        "history": [],
    }
    assert supervisor(state)["next"] == "human_approval"


def test_routes_to_provisioning_when_approved():
    state = {
        "spec": {},
        "policy": {"approved": True, "violations": []},
        "plan": {"module": "modules/rds-postgres"},
        "approval": "approved",
        "history": [],
    }
    assert supervisor(state)["next"] == "provisioning_agent"


def test_sets_rejected_status_when_approval_is_rejected():
    state = {
        "spec": {},
        "policy": {"approved": True, "violations": []},
        "plan": {"module": "modules/rds-postgres"},
        "approval": "rejected",
        "history": [],
    }
    result = supervisor(state)
    assert result["next"] == "end"
    assert result["status"] == "rejected"


def test_ends_after_provisioned():
    state = {
        "spec": {},
        "policy": {"approved": True, "violations": []},
        "plan": {"module": "modules/rds-postgres"},
        "approval": "approved",
        "status": "provisioned",
        "history": [],
    }
    assert supervisor(state)["next"] == "end"


def test_route_reads_next_field():
    assert route({"next": "plan_agent"}) == "plan_agent"
