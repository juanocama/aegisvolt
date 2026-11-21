# Repository Agent Guidance

## Project context

AegisVolt is an existing student project, not a greenfield scaffold. Preserve
the current implementation and make incremental changes. The official course
DOCX is the requirements authority; the actual source/live GraphQL schema is
the current behavior contract. The reference ZIP is not the submission and
has no clear license file.

## Before changing code

1. Read the relevant existing source, tests, and current docs.
2. Check `project-management/CURRENT_TASK.md` for the active scope and approval
   boundary.
3. Check `docs/REQUIREMENTS_TRACEABILITY.md` and relevant contract/design docs.
4. Confirm the exact GraphQL/backend operation exists before using it.
5. Ask for user approval when project guidance or the task says to pause.

## Scope and safety

- Do not restart, delete, or overwrite working code.
- Do not include generated `node_modules`, `dist`, cache, bytecode, Terraform
  state, credentials, or local configuration as application source.
- Do not invent backend operations, feature-flag names, endpoint URLs,
  credentials, states, or fake data. Document blockers instead.
- Do not apply Terraform to real AWS or make cost-incurring changes without
  explicit approval.
- Do not alter branch protection or secrets without explicit approval.
- Do not copy substantial code from the reference archive until reuse rights
  are confirmed; record provenance when adapting.
- Keep errors visible. Avoid broad catches, silent defaults, or success-shaped
  fallbacks.

## Engineering

- Follow existing Python/TypeScript conventions and dependency manifests.
- Prefer precise, small edits and focused tests.
- Keep service ownership and database-per-service boundaries.
- Update directly related docs and tests.
- Run the smallest relevant test/build/lint command and report exact outcomes.
- Do not claim a declared resource is deployed or a feature is complete without
  runtime/test evidence.

## Frontend authority

For frontend work read:

- `docs/FRONTEND_SPECIFICATION.md`
- `docs/GRAPHQL_CONTRACTS.md`
- `prompts/frontend/FRONTEND_IMPLEMENTATION_PROMPT.md`

Only current documented GraphQL operations can be used. Test/prod endpoints
must fail closed when unconfigured. Don't fall back to dev or call domain REST
services from the browser.
