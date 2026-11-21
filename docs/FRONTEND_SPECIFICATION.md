# AegisVolt Frontend Specification

**Status:** approved planning baseline; frontend implementation remains
incomplete. **Audit date:** 2026-11-20.

## 1. Scope and authority

The assignment's minimum presentation requirements are:

1. A panel showing charging-station status and connector availability in
   real-time.
2. A reservation and charge-activation flow that starts the distributed SAGA.
3. A view of feature-flag status for the selected environment.
4. A transaction-history view including SAGA state and compensation outcomes.

This specification expands those requirements into implementable screens, but
does not invent API capabilities. The actual contract is documented in
[GRAPHQL_CONTRACTS.md](./GRAPHQL_CONTRACTS.md). Where that contract is
insufficient, the UI must be explicit, read-only, or disabled; it must not
fabricate data or send guessed GraphQL operations.

## 2. Current implementation audit

`frontend/src/main.tsx` is one React component containing all state, queries,
mutations, and markup. It currently renders:

- AegisVolt heading and `dev`/`test`/`prod` buttons.
- A station list with connector labels and selection by **station ID**.
- A hard-coded wallet (`wallet-1`) balance.
- A "Simulate charger fault" checkbox.
- A reserve/activate button and a basic status message.
- A read-only list of flags.
- A SAGA table with a retry button for selected failure states.
- A 3-second polling interval.

The current frontend is not complete and does not currently have working
environment isolation or a reliable reservation flow. The mutation does not
declare `$station` or `$key` in its GraphQL operation, uses a station id where
the gateway expects a connector id, hard-codes `c-1`, and sends `chargeFault`
only as an undeclared variable. The handler also lacks a user-visible error
path. The frontend GraphQL helper now reads
`VITE_GRAPHQL_DEV_URL`, `VITE_GRAPHQL_TEST_URL`, and `VITE_GRAPHQL_PROD_URL`,
while `.env.example` still documents the obsolete `VITE_GRAPHQL_URL`.
Defaults for test/prod point at ports 8002/8003, which Compose uses for REST
services, not GraphQL gateways. The gateway has no CORS middleware. Vite
already proxies relative `/graphql` requests to `http://localhost:8000`, but
the current GraphQL helper's absolute default URLs bypass that proxy.

`styles.css` has a three-column desktop grid but no media queries, focus
styles, reduced-motion handling, or narrow-screen layout.

## 3. Product roles and navigation

The frontend is an operations console for a fleet/operator user demonstrating
station availability and the charging lifecycle. It is not an end-user map,
payments portal, or administrative flag editor unless the backend adds those
contracts.

Use a persistent application header with:

- AegisVolt wordmark.
- An accessible environment selector: `dev`, `test`, `prod`.
- A visible selected-environment badge and environment connection state.
- Primary navigation with four destinations:
  1. **Overview**
  2. **Stations & charging**
  3. **SAGA history**
  4. **Feature flags**
- A shared global error/connection banner when appropriate.

Navigation can be implemented with local React state and semantic links or
buttons; adding a routing dependency is not required for this scope. The
selected destination must be keyboard operable and announce the current page.

## 4. Screens and requirements

### 4.1 Overview

Purpose: communicate overall environment health and current charging state.

Include:

- Selected environment, backend-reported environment, and API connection
  status. Show a mismatch as an error; do not silently label dev data as prod.
- Service health summary from `dashboard { environment servicesOk }`.
- Station and connector availability summary computed only from the returned
  `stations` response. Do not count unreturned/unknown connectors.
- Wallet balance for the configured demo wallet.
- Latest telemetry snapshot from `telemetry`; label it as latest/current
  snapshot, not historical live streaming, because there is no timestamp or
  subscription in the contract.
- Recent SAGA statuses from `sagas`, with a link to history.

Do not invent KPI values, map coordinates, trends, timestamps, or service-level
health details not returned by the API.

### 4.2 Stations & charging

Purpose: inspect station/connectors and initiate the supported charge flow.

Station list/detail:

- Display station name, status, and coordinates only where present.
- Display each connector's id, connector type, power (kW), and status.
- Selection must be by a **specific connector** belonging to a selected station.
- Do not enable start unless the selected station/connector is present and
  currently available according to returned data.
- The current query has no connector inventory mutation, station detail
  endpoint, location search, or pagination. Do not simulate one.

Reservation flow:

- Show selected station and connector before confirmation.
- Collect a wallet ID (default can use existing demo value `wallet-1`, clearly
  labeled as demo configuration) and a positive charge amount in the backend's
  supported currency. Current GraphQL accepts `amount` as a number and returns
  wallet currency; no price-estimation or energy-kWh contract exists.
- Generate one UUID idempotency key per user intent. Keep that key for retries
  of the *same* intent; generate a new key only for a new intent.
- Submit `reserveAndActivateCharge`; show SAGA id, correlation id, state, and
  message when returned.
- Disable duplicate submission while in flight. Handle transport failure
  separately from a business failure returned as a successful GraphQL result.
- Provide an explicit, guarded demonstration control for the existing
  `chargeFault` mutation argument only in non-production. Do not describe it as
  a persisted environment Feature Flag; the backend currently accepts a
  per-request boolean and does not link it to `flags`.
- On success, refresh stations, telemetry, wallet, and SAGA history.

No separate reservation-only or charge-stop operation exists in GraphQL.
Do not render those actions as functional.

### 4.3 SAGA history

Purpose: inspect the transaction outcome and retry failed compensation when
available.

Show the fields returned by the current `sagas` query:

- SAGA id and correlation id.
- Overall state.
- Reservation, charge, and activation statuses.
- Error message when present.
- Retry-compensation action for `COMPENSATION_FAILED` (and only other states
  that the backend explicitly documents as retryable).

The current contract does not expose a SAGA detail query, event timeline,
timestamps, completed-step list, compensation results, filters, sorting,
pagination, or limit argument. Show a compact list/table of returned records;
do not manufacture event detail or claim the server returns more than its
current 100-record scan. Keep the retry control available only when the record
is retryable. After retry, refresh the list and show its returned state.

### 4.4 Feature flags

Purpose: inspect runtime feature-flag status in the selected environment.

Display each returned `{ name, enabled }` pair using the official names
`ENABLE_DYNAMIC_SURGE_PRICING`, `ENABLE_FAST_CHARGE_BOOST`, and
`SIMULATE_CHARGER_HARDWARE_FAULT`, with clear enabled/disabled labels.
The backend reads read-only process environment values (false by default);
there is no flag mutation or persistent flag store. Local Compose provides
only `dev`. The hardware-fault flag gates the existing per-request
`chargeFault` test input. Surge pricing and fast-charge boost are reported but
do not alter charging behavior until their business rules are approved.
Environment values are isolated only when separate gateway and service
processes use separate environment configuration and tables; a frontend
selector alone does not provide isolation.

## 5. GraphQL operations allowed by the current backend

Only operations in [GRAPHQL_CONTRACTS.md](./GRAPHQL_CONTRACTS.md) may be sent.
They are:

- Query `dashboard`.
- Query `stations`.
- Query `telemetry`.
- Query `wallet(walletId: ...)`.
- Query `flags`.
- Query `sagas`.
- Mutation `reserveAndActivateCharge(...)`.
- Mutation `retryCompensation(sagaId: ...)`.

Do not call station/billing/dispatch REST endpoints directly from the browser.
Do not add GraphQL subscriptions: none are implemented.

## 6. Data freshness and environment isolation

Until a real subscription or server-sent event contract exists, poll the
selected GraphQL endpoint every 3-5 seconds while the document is visible.
Prevent overlapping polls, stop timers on unmount, pause or reduce polling when
the tab is hidden, and do not overwrite newer data with an older response.
Expose a manual refresh action and last-success time only if the client can
truthfully record it.

The selected environment must determine exactly one configured endpoint. Do
not route `test` to the billing REST service or `prod` to the dispatch REST
service. If the selected endpoint is not configured, show a clear
"environment endpoint not configured" state and do not fall back to another
environment. The backend must report the same environment as selected before
data is presented as belonging to it. Never reuse cached records across
environments.

The current local stack only supplies `http://localhost:8000/graphql`; local
test/prod gateways are not present. Vite's current environment variables are
`VITE_GRAPHQL_DEV_URL`, `VITE_GRAPHQL_TEST_URL`, and
`VITE_GRAPHQL_PROD_URL`; `.env.example` must be aligned by the future frontend
implementer. For local dev, the existing `/graphql` Vite proxy can be reused
by setting the dev URL to `/graphql`. Remote/direct endpoints require gateway
CORS configuration; do not assume the current API allows cross-origin calls.

## 7. Visual design

- Calm, modern operations-console aesthetic. Retain the existing dark
  navy/teal base as a starting point, with a high-contrast electric-teal
  primary accent and restrained status colors.
- Use a clear typographic hierarchy: page title, section headings, concise
  metadata, then tables/cards. Numeric measurements should align and include
  units.
- Use reusable cards for health, station/connectors, wallet, telemetry, and
  SAGA status. Status must never rely on color alone; include text and an
  accessible icon/label.
- Make primary action visually distinct; destructive or retry actions require
  clear labels and confirmation where duplicate action could have effects.
- Provide readable skeleton/loading placeholders, empty-state illustrations
  using CSS or simple icons (no unapproved external image dependency), and
  non-blocking refresh indication.
- Avoid decorative charts unless backed by real timestamped points.
- Keep design tokens in CSS custom properties; do not add a component library
  without approval.

## 8. Responsive behavior

- Wide desktop (>= 1200 px): persistent side navigation or compact top
  navigation; overview cards in a balanced multi-column grid; history table.
- Tablet (768-1199 px): two-column cards, collapsible or horizontal navigation;
  no clipped controls.
- Mobile (< 768 px): single-column content, compact header with environment
  selector accessible, stacked form controls, full-width primary action, and
  horizontally scrollable history table with clear row labels.
- At all widths: no page-level horizontal overflow, no controls smaller than
  accessible touch targets, and station/connector selection remains visible.

## 9. Accessibility and interaction

- Use landmarks, one `h1` per screen, nested headings, semantic buttons, links,
  form labels, and table headers.
- All interactions work with keyboard; show a visible focus ring.
- Use `aria-current`/`aria-pressed` appropriately for navigation/environment
  controls. Use `role="status"` for successful asynchronous outcomes and
  `role="alert"` for actionable errors.
- Announce polling updates sparingly; do not place a rapidly updated full
  dashboard in a live region.
- Maintain WCAG AA contrast, support browser zoom/reflow, and honor
  `prefers-reduced-motion`.
- Validate form values before mutation, associate errors with fields, and
  prevent keyboard focus from being lost during refresh.

## 10. Component responsibilities

| Component | Responsibility |
|---|---|
| `AppShell` | Persistent header, navigation, environment selection, page layout |
| `EnvironmentSelector` | Select one endpoint; show configured/unconfigured and mismatch states |
| `ConnectionBanner` | Display initial loading, offline, stale, and environment mismatch |
| `OverviewPage` | Compose service health, counts, wallet, latest telemetry, recent SAGA summary |
| `ServiceHealthCard` | Render only the aggregate `dashboard` health contract |
| `StationList` | Render returned stations and allow station selection |
| `ConnectorList` | Render connectors and select a connector, not merely a station |
| `ChargeRequestForm` | Validate request, maintain intent idempotency key, submit supported mutation |
| `FeatureFlagList` | Read-only display of actual flags; explain unsupported edit requirements |
| `SagaHistoryPage` | Render available SAGA summary fields and retry eligible records |
| `SagaStatusBadge` | Text + status styling for backend state |
| `TelemetrySnapshot` | Render current telemetry fields without fabricated timestamp/history |
| `LoadingState`, `EmptyState`, `ErrorState` | Consistent page/section-level asynchronous states |
| `ConfirmActionDialog` | Guard costly or retry actions if UX requires confirmation |

Components should be small and typed. A GraphQL client can remain a thin
`fetch` wrapper, but it must validate GraphQL errors and endpoint configuration.
No global state library is required for the present size.

## 11. Required UI states

For each query-backed screen/section:

- **Initial loading:** skeleton or progress with a label; disable dependent
  actions.
- **Loaded:** show current values and freshness/connection state.
- **Empty:** explain that no records were returned and preserve refresh.
- **Error:** distinguish network/HTTP/GraphQL errors; preserve last good data as
  stale only with a visible stale indicator; offer retry.
- **Stale:** avoid presenting old data as current. Disable actions requiring
  authoritative availability.

For the request flow:

- **Ready:** valid wallet id, positive amount, selected available connector.
- **Submitting:** one request only; retain the idempotency key.
- **Completed:** show SAGA id/correlation and success status; refresh relevant
  queries.
- **Business failure / compensated:** display returned state and backend
  message, including wallet/charger failure without claiming success.
- **Compensation failed:** prominent warning and retry action only when the
  SAGA record is eligible.
- **Unknown outcome / network failure:** explain that server outcome is unknown;
  offer safe retry with the same idempotency key, not a new transaction.

## 12. Acceptance criteria

The frontend implementation is acceptable when:

1. The four screens/nav areas above work at desktop, tablet, and mobile widths.
2. Every operation exactly matches `GRAPHQL_CONTRACTS.md`; no unsupported
   operation or response field is referenced.
3. The current mutation is corrected: declared variables are actually declared,
   selected station and connector ids are distinct and consistent, and all
   required arguments are sent.
4. A success and each backend-returned failure/compensation state are rendered
   accurately; transport failures are not mislabeled as business success.
5. Refreshing does not cause overlapping polls, stale response races, or
   environment data crossover.
6. Unconfigured environment endpoints fail closed; dev never masquerades as
   test or prod.
7. Unsupported official feature-flag edits, SAGA detail, history pagination,
   and charge-stop operations are documented and shown as unavailable/read-only,
   not fabricated.
8. Keyboard, screen-reader semantics, focus, contrast, and reduced-motion
   requirements are met.
9. Unit/component tests cover the interactive contract and error states; build,
   lint, and test commands pass.
10. No backend, infrastructure, or existing working behavior is changed as a
    side effect of the frontend task unless explicitly re-scoped.
