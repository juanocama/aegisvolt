# Decisions

- FastAPI/Strawberry keeps the gateway deployable with one Python runtime.
- Each service receives its own DynamoDB table and Docker process.
- Floci first, moto fallback in tests, and AWS endpoint variables make emulator use explicit.
- SAGA state is persisted in DynamoDB and compensation is retriable.
- API Gateway, EKS/ECR, network, and observability Terraform modules are intentionally feasible foundations, not fabricated deployed resources.
- Frontend polling is sufficient for a local 14-day demo and avoids extra transport infrastructure.
