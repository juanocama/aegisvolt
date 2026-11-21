# 14-Day Defense Guide

1. Start the stack and show the GraphQL endpoint.
2. Demonstrate a successful reserve/charge/activate mutation.
3. Repeat the mutation with the same idempotency key and explain stable SAGA lookup.
4. Set `amount: 101` to show insufficient-funds compensation.
5. In a dev-only gateway process, set
   `SIMULATE_CHARGER_HARDWARE_FAULT=true`, pass `chargeFault: true`, and show
   refund plus reservation cancellation. Keep the environment variable false
   in environments where fault injection is not authorized.
6. Show persisted SAGA state and the compensation retry mutation.
7. Open the frontend polling stations, flags, wallet, and history.
8. Show Docker/Floci fallback, not AWS.
9. Show Terraform workspace and state bootstrap; explain modules are demonstrative and do not imply provisioned resources.
10. Show Kubernetes stable/canary manifests and the health/restart canary script.

Known limits: in-cluster DynamoDB credentials/IAM wiring, full API Gateway integration, and node groups depend on real AWS configuration. Floci/moto behavior is intentionally local.
