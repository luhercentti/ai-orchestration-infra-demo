from app.agents.policy_agent import policy_agent


def test_approves_valid_spec():
    state = {"spec": {"resource_type": "postgres", "team": "billing", "environment": "staging"}, "history": []}
    policy = policy_agent(state)["policy"]
    assert policy["approved"] is True
    assert policy["violations"] == []


def test_rejects_unknown_resource_type():
    state = {"spec": {"resource_type": "mongodb", "team": "billing", "environment": "staging"}, "history": []}
    policy = policy_agent(state)["policy"]
    assert policy["approved"] is False
    assert any("not on the golden path" in v for v in policy["violations"])


def test_rejects_unknown_environment():
    state = {"spec": {"resource_type": "postgres", "team": "billing", "environment": "sandbox"}, "history": []}
    policy = policy_agent(state)["policy"]
    assert policy["approved"] is False
    assert any("not allowed" in v for v in policy["violations"])
