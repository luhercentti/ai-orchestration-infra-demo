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
    assert spec["environment"] == "dev"
    assert spec["team"] == "unknown"
    # no known resource type in text — returns "unknown" not a silent postgres default
    assert spec["resource_type"] == "unknown"


def test_extracts_ec2_as_resource_type():
    state = {"request": {"raw_text": "I need an ec2 instance for team ops, dev", "requester": "bob"}, "history": []}
    # ec2 is a known non-golden-path type — spec extracts it, policy rejects it
    assert spec_agent(state)["spec"]["resource_type"] == "ec2"
