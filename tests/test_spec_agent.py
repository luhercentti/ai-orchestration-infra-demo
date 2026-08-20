from app.agents.spec_agent import spec_agent


def test_parses_resource_type_environment_and_team():
    state = {
        "request": {"raw_text": "I need a new postgres database for team billing, staging", "requester": "alice"},
        "history": [],
    }
    result = spec_agent(state)
    spec = result["spec"]
    assert spec["resource_type"] == "postgres"
    assert spec["environment"] == "staging"
    assert spec["team"] == "billing"
    assert spec["name"] == "billing-staging-postgres"


def test_defaults_when_fields_are_missing():
    state = {"request": {"raw_text": "spin something up please", "requester": "bob"}, "history": []}
    spec = spec_agent(state)["spec"]
    assert spec["resource_type"] == "postgres"
    assert spec["environment"] == "dev"
    assert spec["team"] == "unknown"
