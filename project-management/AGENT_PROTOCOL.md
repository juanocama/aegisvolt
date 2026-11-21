# Agent Protocol

## 1. Purpose

Coordinate multiple coding/research agents without overlapping edits, silent
contract changes, or claims unsupported by tests. Repository-local guidance is
also in `AGENTS.md`.

## 2. Source precedence

1. User's explicit task and approval boundary.
2. Official course specification.
3. Approved contracts and decisions log.
4. Current source and tests.
5. Planning documents.
6. Reference archive, for inspiration only.

If these conflict, stop and document the conflict; do not infer permission to
change a higher-priority requirement.

## 3. Task assignment

Every agent/task must have:

- One bounded objective and named owning files/directories.
- Explicit out-of-scope paths.
- Prerequisites and contract version.
- Required tests/validation.
- A stop condition and handoff format.

Do not assign independent agents overlapping write ownership. The lead
integrates changes and checks cross-layer compatibility.

## 4. Coding and documentation rules

- Inspect existing files before editing; preserve unrelated/user changes.
- Make small, focused, reviewable edits; do not restart or wholesale-rewrite.
- Do not create speculative GraphQL fields, flags, states, URLs, credentials,
  or deployment resources.
- If an API capability is missing, report a blocker and update the contract
  gap; do not create a success-shaped mock.
- Update relevant tests/docs in the same task.
- Keep errors visible and typed; no broad silent catches.
- Do not copy substantial source from the reference archive until license
  permission is resolved. Track provenance for any adaptation.
- No real AWS apply, branch protection changes, secret handling, or cost
  generation without user approval.
- No code task may cross an explicit "wait for approval" boundary.

## 5. Frontend-specific rules

- Use `docs/FRONTEND_SPECIFICATION.md`,
  `docs/GRAPHQL_CONTRACTS.md`, and the frontend implementation prompt.
- Before coding, query or inspect the current checked-in schema; don't rely on
  memory or guessed SDL.
- Use only endpoint configuration explicitly supplied for that environment.
- Never fall back from test/prod to dev or to a REST service port.
- Preserve an idempotency key for retries of one user intent.
- Keep unsupported feature-flag writes, SAGA event details, pagination, and
  stop-session behavior unavailable/read-only until implemented and approved.
- Maintain keyboard accessibility, responsive behavior, and query/mutation
  error states.

## 6. Validation and reporting

Agents report:

1. Files changed.
2. Behaviors implemented and explicitly not implemented.
3. Commands/tests run and exact outcomes.
4. Contract or deployment assumptions.
5. Remaining blockers.
6. Handoff/next task recommendation.

Never report "complete" from a build alone. Distinguish source presence,
automated verification, and deployed runtime verification.

## 7. Handoff

Update `project-management/CURRENT_TASK.md`, `IMPLEMENTATION_STATUS.md`, and
`HANDOFF.md` when work materially changes project state. Record architecture
choices in `DECISIONS_LOG.md`. Do not overwrite another agent's active work;
coordinate ownership first.
