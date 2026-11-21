# Current Task

**Status:** Phase 0 baseline verification complete to the extent the
environment allowed; full Compose startup is blocked. Phase 1 is paused
pending explicit user approval.  
**Last updated:** 2026-11-20.

## Completed in this task

- Inventoried repository source and documentation, excluding generated
  dependencies/caches.
- Inspected current frontend and actual Strawberry schema/resolvers plus domain
  services, tests, Compose, workflows, Terraform, Kubernetes, Prefect, and
  existing docs.
- Compared requirements against actual implementation and documented
  discrepancies.
- Added the requested planning, contract, coordination, traceability, and
  copy-ready frontend-agent documents.
- Ran `python -m pytest -q`: 5 passed, 22 warnings.
- Validated Compose syntax with `docker compose config --quiet`.
- Docker engine was unavailable; Compose stack startup and readiness could not
  be tested.
- `docker compose up --build -d` was attempted and failed because Docker could
  not connect to `//./pipe/dockerDesktopLinuxEngine`; no containers started.
- Queried actual gateway GraphQL introspection over HTTP using temporary
  Uvicorn + Moto; saved SDL to `docs/graphql/schema.graphql`.
- Verified flags query output and validated the current frontend mutation
  against the schema.
- Did not modify application/frontend code or start Phase 1.

## Baseline limitations

- This directory is not a Git worktree (`.git` absent); Git cannot report a
  clean/dirty status or distinguish earlier edits.
- The temporary gateway test did not call Docker, Floci, or downstream
  services. Full-stack startup remains unverified.
- Only `dev` is available in local Compose. Test/prod isolation is absent.
- Introspection identified one documentation correction:
  `chargeFault` is `Boolean! = false`, not nullable Boolean. Current SDL is in
  `docs/graphql/schema.graphql`.
- The existing frontend mutation uses undeclared `$station` and `$key`
  variables.

## Current user-facing decision

Wait for user approval before implementing the next task. The next recommended
task is:

> Stabilize the backend/GraphQL contract and correctness before frontend
> implementation: fix SAGA/service invariants, decide environment isolation,
> implement the required official feature-flag model, and version/test the
> GraphQL schema. Keep work scoped to backend and tests.

The frontend prompt is ready at
`prompts/frontend/FRONTEND_IMPLEMENTATION_PROMPT.md`. Do not launch it or begin
frontend coding before approval and resolution of the critical contract
decisions.

## Blockers to frontend work

1. Compose has one GraphQL gateway; frontend test/prod URLs are not configured.
2. Frontend `.env.example` and GraphQL helper use different variable names.
3. The current charge mutation in the UI is malformed and picks station rather
   than connector id.
4. Official flags are not exposed by the current backend contract.
5. No flag update mutation, SAGA detail/event history, history pagination, or
   GraphQL stop-session operation exists.
6. Vite has a `/graphql` development proxy, but the client uses absolute
   defaults that bypass it; gateway CORS is not configured for remote origins.
7. Station service scans reservation items as stations and does not update
   connector availability.

## Verification boundary

Phase 0 made documentation-only changes and a versioned SDL snapshot. It did
not alter application behavior. The five passing tests do not establish that
the Docker stack starts or that the current UI mutation works. No Terraform
command/apply, AWS operation, Kubernetes deployment, or frontend change was
performed.
