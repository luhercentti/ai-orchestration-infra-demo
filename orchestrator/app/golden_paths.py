"""Golden-path templates the spec/policy/plan agents are validated against.

In a real deployment this would live in a separate config repo or a service
(the "platform catalog"), not hardcoded here — kept inline for the demo.
"""

ALLOWED_RESOURCE_TYPES = {"postgres", "redis", "s3", "kafka-topic"}
ALLOWED_ENVIRONMENTS = {"dev", "staging", "prod"}

# team -> max number of resources of a given type allowed per environment
QUOTAS = {
    "default": {"postgres": 3, "redis": 3, "s3": 10, "kafka-topic": 20},
}

# module used to render the Terraform plan per resource type
TERRAFORM_MODULES = {
    "postgres": "modules/rds-postgres",
    "redis": "modules/elasticache-redis",
    "s3": "modules/s3-bucket",
    "kafka-topic": "modules/msk-topic",
}

ESTIMATED_MONTHLY_COST_USD = {
    "postgres": {"dev": 25, "staging": 60, "prod": 400},
    "redis": {"dev": 15, "staging": 40, "prod": 250},
    "s3": {"dev": 1, "staging": 2, "prod": 10},
    "kafka-topic": {"dev": 0, "staging": 0, "prod": 5},
}
