# Frontend Implementation Prompt — AegisVolt

Copy and paste everything below into a coding agent task. This prompt is
self-contained and does not rely on prior conversation memory.

---

## Role and task

You are a senior React/TypeScript engineer working in an existing AegisVolt
repository at `C:\Users\iamju\Desktop\patrones\aegisvolt`.

Implement the AegisVolt operations-console frontend incrementally in the
existing `frontend/` folder. This is **not** a greenfield rewrite. Preserve the
current implementation and adapt it. Do not alter backend, infrastructure,
Terraform, Kubernetes, or CI files in this frontend task. If a desired UI
action needs an API that does not exist below, document the blocker and render
that capability as read-only/unavailable; do not invent a GraphQL operation,
mock production data, or call a service REST endpoint from the browser.

Before editing, read:

- `docs/FRONTEND_SPECIFICATION.md`
- `docs/GRAPHQL_CONTRACTS.md`
- `docs/SAGA_DESIGN.md`
- `frontend/src/main.tsx`
- `frontend/src/styles.css`
- `frontend/src/graphql.ts`
- `frontend/package.json`

Use the **actual current contract** in this prompt and
`docs/GRAPHQL_CONTRACTS.md` as the limit of supported behavior. If the running
schema differs, stop and report the exact mismatch rather than guessing.

## Product and visual direction

Build a polished EV fleet charging operations console for an operator. Retain
the existing dark navy/teal appearance as a starting point, with clear
electric-teal primary actions, restrained success/warning/error colors, strong
typography, consistent spacing, reusable status cards, and text labels in
addition to color. Use CSS custom properties and the project's existing React,
TypeScript, and Vite stack. Do not add a component library or chart/map
dependency without approval.

The interface must be usable and visually coherent at desktop, tablet, and
mobile sizes. No page-level horizontal overflow. Respect reduced motion,
keyboard navigation, visible focus, readable contrast, and screen-reader
semantics.

## Exact screens and navigation

Implement these four navigable screens. Use the existing app; a local state
router is sufficient, and a new routing dependency is not required.

### 1. Overview

Show:

- Application name and selected environment (`dev`, `test`, `prod`).
- Connection state and backend-reported environment. A mismatch is an error,
  not a silently relabeled environment.
- Aggregate `dashboard` service status, with a note that current backend only
  checks the station service.
- Counts derived from returned stations/connectors only.
- Current demo wallet balance and currency.
- Latest telemetry snapshot, clearly labeled as the current snapshot; it has
  no timestamp/history contract.
- Recent SAGA summary states and navigation to SAGA history.

Never invent map locations, trends, timestamps, additional services, or
availability numbers.

### 2. Stations & charging

Show station list and connectors from `stations`. Selecting a station must
allow selecting one of its actual connectors by connector id. Show station
name/status/location only when returned, and connector id/type/power/status.
Disable the request action unless a concrete returned connector is selected
and its returned status is available. If data is stale or unavailable, disable
the action and explain why.

Provide a charge request form using only the actual mutation arguments:
wallet id, station id, connector id, amount, idempotency key, optional
`chargeFault`. Do not invent energy pricing, kWh estimate, fleet chooser,
reservation-only flow, or stop-session control. The current demo wallet id may
default to `wallet-1`, but label it as demo configuration. Validate amount as
positive and show currency from the returned wallet.

Generate one `crypto.randomUUID()` idempotency key per new user intent. Keep
that same key if the user retries after a timeout/unknown result. Do not
generate a new key just to retry the same intent. Block duplicate submissions
while one is in progress.

The current `chargeFault` argument is a per-request demonstration hook, not a
stored feature flag. It can only trigger a simulated fault when
`SIMULATE_CHARGER_HARDWARE_FAULT` is enabled in the gateway process. Keep it
as a clearly labeled developer/demo control for local `dev`; never submit it
to `prod`. The local stack has no separate test gateway.

### 3. SAGA history

Render the available records from `sagas` with id, correlation id, state,
reservation status, charge status, activation status, and optional error.
Support retry only for `COMPENSATION_FAILED`, and call
`retryCompensation`. Show returned state afterward.

Do not create a detail/timeline view, event history, pagination, filtering,
sorting, compensation-attempt counts, or retry for other states: the current
GraphQL contract does not provide these. Show an explicit explanatory
read-only note for those unavailable features if needed.

### 4. Feature flags

Render `flags { name enabled }` in a read-only list. The backend returns
`ENABLE_DYNAMIC_SURGE_PRICING`, `ENABLE_FAST_CHARGE_BOOST`, and
`SIMULATE_CHARGER_HARDWARE_FAULT`, read from process environment and defaulting
to false.

Do not show toggles, optimistic flag updates, or call a guessed
`setFeatureFlag` mutation. Values are read-only and process-level; local
Compose provides only `dev`, and there is no persistent flag store or
management API. The surge-pricing and fast-charge flags are visible but have
no business effect until their rules are approved. Do not represent a selected
frontend environment as isolated unless a real separate endpoint is configured.

## Exact supported GraphQL operations

Each configured environment URL must be the full GraphQL endpoint URL,
including `/graphql`; pass it to `fetch` as-is and do not append the path a
second time. Current local Compose exposes one GraphQL gateway at
`http://localhost:8000/graphql`.
No separate local test/prod gateways exist.

### Dashboard

```graphql
query Dashboard {
  dashboard { environment servicesOk }
}
```

### Stations

```graphql
query Stations {
  stations {
    id name status latitude longitude
    connectors { id type status powerKw }
  }
}
```

### Telemetry

```graphql
query Telemetry {
  telemetry { stationId connectorId powerKw energyKwh state }
}
```

### Wallet

```graphql
query Wallet($walletId: String!) {
  wallet(walletId: $walletId) { id balance currency }
}
```

### Flags

```graphql
query FeatureFlags {
  flags { name enabled }
}
```

### SAGA summaries

```graphql
query Sagas {
  sagas {
    id correlationId state reservationStatus chargeStatus activationStatus error
  }
}
```

### Reserve / charge / activate

Use declared variables exactly as follows. In particular, do not repeat the
current bug where `$station`/`$key` are used but not declared.

```graphql
mutation ReserveAndActivateCharge(
  $walletId: String!
  $stationId: String!
  $connectorId: String!
  $amount: Float!
  $idempotencyKey: String!
  $chargeFault: Boolean = false
) {
  reserveAndActivateCharge(
    walletId: $walletId
    stationId: $stationId
    connectorId: $connectorId
    amount: $amount
    idempotencyKey: $idempotencyKey
    chargeFault: $chargeFault
  ) {
    success sagaId correlationId state message
  }
}
```

### Retry compensation

```graphql
mutation RetryCompensation($sagaId: String!) {
  retryCompensation(sagaId: $sagaId) {
    id correlationId state reservationStatus chargeStatus activationStatus error
  }
}
```

Do not assume `state` is an enum: it is a string in the current schema. A
business failure can be returned as a successful GraphQL response with
`success: false` and a state/message. Treat HTTP/network failures, top-level
GraphQL errors, and business outcomes separately.

## Current typed data models

Use types matching the API and preserve nullability:

```ts
type Environment = "dev" | "test" | "prod";
type Connector = { id: string; type: string; status: string; powerKw: number };
type Station = {
  id: string; name: string; status: string;
  latitude: number; longitude: number;
  connectors: Connector[] | null;
};
type Telemetry = {
  stationId: string; connectorId: string;
  powerKw: number; energyKwh: number; state: string;
};
type Wallet = { id: string; balance: number; currency: string };
type FeatureFlag = { name: string; enabled: boolean };
type Saga = {
  id: string; correlationId: string; state: string;
  reservationStatus: string; chargeStatus: string;
  activationStatus: string; error: string | null;
};
type ChargeResult = {
  success: boolean; sagaId: string; correlationId: string;
  state: string; message: string;
};
```

Verify actual introspection nullability if the local service is available.
Never add fields to these types unless the backend schema has changed and the
contract docs are updated.

## Environment isolation and endpoint behavior

`frontend/src/graphql.ts` currently reads:

- `VITE_GRAPHQL_DEV_URL`
- `VITE_GRAPHQL_TEST_URL`
- `VITE_GRAPHQL_PROD_URL`

`frontend/.env.example` is stale and lists only `VITE_GRAPHQL_URL`. Align it
with the current helper. Remove unsafe defaults to ports `8002` and `8003`:
those are the billing-wallet and energy-dispatch REST services, not GraphQL.
If test/prod URL is absent, show “Environment endpoint not configured”; do not
fall back to dev, another URL, or REST. Do not reuse query results when
switching environments. Clear or namespace in-memory data by environment and
make the backend-reported environment mismatch visible.

The single local gateway is built with one `ENVIRONMENT`; the selector cannot
make that backend truly isolated. Do not claim otherwise. Configure CORS for
the Vite origin or add a deliberate same-origin Vite proxy only if the existing
backend/local setup can support it; document the choice and do not modify
backend files in this task.

## Real-time updates

There is no GraphQL subscription/WebSocket/SSE contract. Poll the active
environment's queries every 3-5 seconds while the document is visible:
`dashboard`, `stations`, `telemetry`, `wallet`, `flags`, and `sagas`, using
separate or combined valid queries. Prevent overlapping polls; clean up timer
on unmount; pause/reduce polling in a hidden tab; avoid stale response races.
Provide manual refresh and a visible stale/error state. Do not describe this as
push/live streaming.

After reserve or retry, immediately refresh the affected query set. If a
network timeout occurs after mutation submission, the server outcome is
unknown: retain the idempotency key and offer a retry with that same key.

## Component responsibilities

- `AppShell`: global header, navigation, environment selector, page container.
- `EnvironmentSelector`: configured endpoint selection, safe unavailable state.
- `ConnectionBanner`: loading, disconnected, stale, and environment mismatch.
- `OverviewPage`: health, derived counts, wallet, telemetry, recent SAGA states.
- `StationList`: list stations and choose station.
- `ConnectorList`: choose a connector from the chosen station and show status.
- `ChargeRequestForm`: validation, idempotency, mutation pending/result states.
- `FeatureFlagList`: read-only current flags and pending official flag notice.
- `SagaHistoryPage`: available SAGA summary and guarded compensation retry.
- `TelemetrySnapshot`: display only fields returned, no fake timestamp/chart.
- `SagaStatusBadge`: accessible text and color for arbitrary state strings.
- Shared `LoadingState`, `EmptyState`, `ErrorState`, `ConfirmActionDialog` as
  needed.

Keep GraphQL transport/client code separate from view components. Add no
unnecessary state-management abstraction.

## UI state requirements

Queries/screens must support initial loading, loaded, empty, network/HTTP error,
GraphQL error, stale-but-preserved data, manual retry, and unconfigured
environment states. Never silently replace an error with an empty list.

Mutation flow must support:

- Invalid form values with field-level errors.
- Ready state and selected available connector summary.
- Submitting, with duplicate submit disabled.
- Completed, showing SAGA and correlation ids.
- Business rejection/failure/compensated result from returned fields.
- Compensation failed with retry only when eligible.
- Unknown result after network failure, keeping the same idempotency key.

Announce action outcomes using `role="status"` and actionable errors with
`role="alert"`. Keep existing data labeled stale if refreshing fails; disable
availability-sensitive actions until fresh data returns.

## Responsive layout

- >=1200 px: multi-column overview cards, persistent navigation, readable
  history table.
- 768-1199 px: two-column cards, compact/collapsible navigation.
- <768 px: one column, stacked form, full-width primary action, touch-friendly
  controls, environment selector remains accessible, history table scrolls
  within its own container.
- All sizes: no body horizontal overflow, no clipped dialogs or focus, content
  order remains logical.

## Accessibility

- Semantic `header`, `nav`, `main`, `section`, one `h1` per screen, nested
  headings, real labels, table captions/headers.
- Keyboard-operable navigation, selector, forms, and actions; visible focus.
- Use `aria-current`/`aria-pressed` appropriately.
- Status conveyed in words/icons as well as color.
- WCAG AA contrast, zoom/reflow, reduced-motion support.
- No rapidly polling whole-page live region; announce user-triggered outcomes
  and important connection changes only.
- Preserve focus across refresh and show errors beside the affected control.

## Tests and verification

Use existing `frontend/package.json` commands (`npm run build`, `npm test`,
`npm run lint`). Add focused React component/interaction tests using the
existing test stack; add a testing library only if absent and necessary, and
keep dependency additions minimal. Do not test mocked invented GraphQL fields.

Required cases:

1. Exact documents and variables used for every supported operation.
2. Station selection and connector-specific request payload.
3. Required values validation and amount boundary (positive only; do not invent
   an undocumented maximum).
4. Mutation pending disables duplicate submit.
5. Success state shows returned ids/state and refreshes.
6. Business failure vs. GraphQL/network error render distinct outcomes.
7. Same idempotency key survives a retry/unknown result.
8. Retry appears only for `COMPENSATION_FAILED`; retry errors are surfaced.
9. Environment switch clears/isolates prior data; unconfigured env fails closed;
   never request ports 8002/8003 as GraphQL.
10. Polling timer cleanup, no overlapping requests, and stale response handling.
11. Flags are read-only; no unsupported mutation sent.
12. Responsive and accessibility behavior for navigation, form, table, and
    errors (automated checks plus manual keyboard/viewport review).

Run build, lint, and tests; report exact commands/results. Do not fix backend
failures in this task. Document them as blockers.

## Acceptance criteria

- Four screens and navigation are implemented with typed, reusable components.
- The current GraphQL operations work exactly as declared above; no undefined
  variables or direct browser-to-service REST calls.
- Connector selection uses a real connector id from the selected station.
- All data states and SAGA compensation outcomes returned by current API are
  understandable and accessible.
- Environment routing is fail-closed and does not claim data isolation where
  only one gateway exists.
- Unsupported feature-flag edits, SAGA details/paging, and session stop are
  visibly unavailable rather than faked.
- Desktop/tablet/mobile layouts and required accessibility checks pass.
- Frontend tests, lint, and production build pass.
- Backend/infra files remain unchanged; remaining API blockers are listed
  clearly in the handoff.

## Completion report format

Report:

1. Files changed.
2. Screens/components implemented.
3. Current API operations used.
4. Unsupported features left blocked and why.
5. Tests/lint/build commands and exact results.
6. Manual viewport/accessibility checks performed.
7. Any backend contract issues found.

Do not state the overall academic UI requirement is fully met if required
backend contracts remain unavailable.
