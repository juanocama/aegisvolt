# GraphQL Contracts

**Source of truth:** the current Strawberry schema in `gateway/app.py`,
confirmed by HTTP introspection and snapshotted at
[`graphql/schema.graphql`](./graphql/schema.graphql). The gateway is mounted at
`/graphql`; GraphQL names use Strawberry's default camel-case conversion.

**Verification scope:** Phase 0 introspection was run over temporary Uvicorn
with Moto. Phase 1 tests exercise GraphQL and all three FastAPI services
in-process with Moto-backed DynamoDB. They do not prove Docker networking,
Floci behavior, or live AWS DynamoDB behavior. Docker Compose remains
unavailable because the Docker Desktop Linux engine cannot be reached.
Phase 1 HTTP introspection returned 200 with no GraphQL errors; its SDL
definitions match the checked-in snapshot (declaration order ignored). No
GraphQL operation signatures or object fields changed in Phase 1.

## 1. Query contract currently implemented

### Dashboard health

```graphql
query Dashboard {
  dashboard {
    environment
    servicesOk
  }
}
```

`servicesOk` currently means only that the station service `/health` response
has status `ok`; it does not aggregate all three domain services.

### Stations and connectors

```graphql
query Stations {
  stations {
    id
    name
    status
    latitude
    longitude
    connectors {
      id
      type
      status
      powerKw
    }
  }
}
```

The query delegates to station service `/stations`. The service retains the
existing single demo station and connector catalog, but connector availability
now comes from a persisted conditional connector-lock item. Reservation and
lock records are no longer treated as station rows. The catalog itself is
still hard-coded; no station-inventory management API is implemented.

### Telemetry

```graphql
query Telemetry {
  telemetry {
    stationId
    connectorId
    powerKw
    energyKwh
    state
  }
}
```

The dispatch service currently returns a static sample with no timestamp,
history window, or subscription when no persisted telemetry exists. After an
activation, it returns the persisted simulated zero-power baseline; stopping
an activation updates its telemetry state to `stopped` and power to zero.
These are simulated state records, not hardware measurements.

### Wallet

```graphql
query Wallet($walletId: String!) {
  wallet(walletId: $walletId) {
    id
    balance
    currency
  }
}
```

The service creates a default wallet with balance `100.00` and currency `USD`
when the requested wallet does not exist. This is demo seeding, not an
authenticated account lifecycle. Positive charges atomically decrement the
balance and create the idempotency record in one DynamoDB transaction.
Insufficient balance returns HTTP 402 to the gateway, which releases the
reservation before reporting the SAGA as compensated.

### Flags

```graphql
query FeatureFlags {
  flags {
    name
    enabled
  }
}
```

Returns the official names `ENABLE_DYNAMIC_SURGE_PRICING`,
`ENABLE_FAST_CHARGE_BOOST`, and `SIMULATE_CHARGER_HARDWARE_FAULT` for the
gateway's own environment. In deployed environments (and Compose) the source is
the per-environment DynamoDB table `aegisvolt-<env>-flags` (`FLAGS_TABLE`), one
item `{id, enabled: BOOL}` per flag, re-read at most every `FLAG_CACHE_SECONDS`
(default 5). Operators change a flag at runtime with
`scripts/set_feature_flag.py` -- no redeploy -- and each environment's table is
isolated (a table name for another environment is rejected). A missing item, a
non-boolean value or an unreadable table is a GraphQL error, never a silent
default. Without `FLAGS_TABLE` (unit tests) values come from process
environment variables. There is no flag mutation in the GraphQL API.

While `SIMULATE_CHARGER_HARDWARE_FAULT` is enabled, every
`reserveAndActivateCharge` in that environment fails at physical activation
and compensates (refund, then release) -- spec 2.3. The `chargeFault` argument
is retained for schema compatibility only and cannot inject a fault by itself.
Surge-pricing and fast-charge flags are reported but have no pricing/boost
effect until their business rules are approved and implemented.

### SAGA summaries

```graphql
query Sagas {
  sagas {
    id
    correlationId
    state
    reservationStatus
    chargeStatus
    activationStatus
    error
  }
}
```

The resolver scans at most 100 records and does not return an explicit sort
order, cursor, or pagination metadata.

## 2. Mutation contract currently implemented

### Reserve, charge, and activate

```graphql
mutation ReserveAndActivateCharge(
  $walletId: String!
  $stationId: String!
  $connectorId: String!
  $amount: Float!
  $idempotencyKey: String!
  $chargeFault: Boolean! = false
) {
  reserveAndActivateCharge(
    walletId: $walletId
    stationId: $stationId
    connectorId: $connectorId
    amount: $amount
    idempotencyKey: $idempotencyKey
    chargeFault: $chargeFault
  ) {
    success
    sagaId
    correlationId
    state
    message
  }
}
```

`ChargeResult.state` is a string, not an enum. A resolved mutation may report
business failure in `success/state/message`; transport or GraphQL execution
errors are separate. A SAGA is conditionally created by idempotency key and
stores a canonical request fingerprint. A matching replay returns or resumes
the same SAGA without repeating effective service effects; reusing the key
with changed request data returns a GraphQL error. A 120-second conditional
execution lease serializes ordinary concurrent requests and permits recovery
after a worker stops; downstream operations are independently idempotent to
protect any overlap at lease expiry and to support retry after uncertain
transport outcomes.

The gateway persists SAGA step and compensation outcomes in an internal
`events` list and preserves pending compensation state. The existing
`retryCompensation(sagaId:)` operation only runs failed/incomplete
compensation; it does not expose the event history in GraphQL.

### Retry compensation

```graphql
mutation RetryCompensation($sagaId: String!) {
  retryCompensation(sagaId: $sagaId) {
    id
    correlationId
    state
    reservationStatus
    chargeStatus
    activationStatus
    error
  }
}
```

The gateway enforces retry eligibility and uses an execution lease. It resumes
only `COMPENSATION_FAILED` work or stale `COMPENSATING` work; an already
compensated SAGA is returned unchanged. Downstream refund and reservation
release must each confirm their final status before the SAGA can be marked
`COMPENSATED`.

### Stop and release a dev session

```graphql
mutation StopAndRelease($sagaId: String!) {
  stopAndRelease(sagaId: $sagaId) {
    id correlationId state reservationStatus chargeStatus activationStatus error
  }
}
```

This operation stops the dispatch activation and cancels the reservation for a
`COMPLETED` SAGA. It does not refund an already completed charge. It is
implemented for operator cleanup and local SAGA testing; it must not be
presented as a substitute for compensation. The mutation returns `STOPPED`,
`stopped` activation status, and `cancelled` reservation status when both
downstream operations succeed.

## 3. Current GraphQL object models

| Type | Fields |
|---|---|
| `Dashboard` | `environment: String!`, `servicesOk: Boolean!` |
| `Station` | `id: String!`, `name: String!`, `status: String!`, `latitude: Float!`, `longitude: Float!`, `connectors: [Connector!]` |
| `Connector` | `id: String!`, `type: String!`, `status: String!`, `powerKw: Float!` |
| `Telemetry` | `stationId: String!`, `connectorId: String!`, `powerKw: Float!`, `energyKwh: Float!`, `state: String!` |
| `Wallet` | `id: String!`, `balance: Float!`, `currency: String!` |
| `FeatureFlag` | `name: String!`, `enabled: Boolean!` |
| `Saga` | `id: String!`, `correlationId: String!`, `state: String!`, `reservationStatus: String!`, `chargeStatus: String!`, `activationStatus: String!`, `error: String` |
| `ChargeResult` | `success: Boolean!`, `sagaId: String!`, `correlationId: String!`, `state: String!`, `message: String!` |

Types above are inferred directly from the Python annotations and schema
construction. Check the live introspection result before generating typed
documents because list/null wrappers and library behavior are ultimately
defined by Strawberry.

## 4. Contract gaps vs official requirements

These are not implemented operations and must not be called by the frontend:

| Need | Current gap | Resolution owner |
|---|---|---|
| Official flags and independent values per `dev/test/prod` | Exact official names are read from each gateway's process environment. Local Compose is dev only; separately deployed test/prod processes and tables are not provisioned here | Backend + infrastructure |
| Change a feature flag | No mutation exists | Backend contract decision |
| Pricing/boost behavior | Flags are reported only; no approved surge formula or boost calculation is present | Product + backend |
| Broader connector inventory | Conditional connector locks enforce availability for the current single-station catalog; no inventory management or broader catalog exists | Station service + backend |
| SAGA detail and compensation timeline | Query exposes only summary and error | Gateway schema + SAGA persistence |
| Search, filter, stable ordering, cursor pagination | `sagas` has no args and scans max 100 | Gateway query + DynamoDB access pattern |
| Session end/stop | Dispatch REST stop exists; no GraphQL operation | Gateway contract |
| Live updates | No subscription/WebSocket/SSE | Gateway and infrastructure |
| Accurate multi-service environment health | dashboard only pings station service | Gateway |
| Runtime endpoint isolation | One gateway process has `ENVIRONMENT`; no separate gateway instances are set up in Compose | Deployment/configuration |
| Stable idempotency semantics | Gateway and service writes use conditional/idempotent records; operational recovery still depends on retrying the same key | Gateway and service owners |

Do not implement speculative names such as `setFeatureFlag`, `saga(id:)`,
`stopCharge`, or GraphQL subscriptions before backend approval and schema
implementation. When approved, document exact SDL, owner, error semantics, and
tests here first.

## 5. Frontend endpoint configuration

The helper in `frontend/src/graphql.ts` expects:

- `VITE_GRAPHQL_DEV_URL`
- `VITE_GRAPHQL_TEST_URL`
- `VITE_GRAPHQL_PROD_URL`

`frontend/.env.example` is aligned with the three named variables. The dev
helper defaults to relative `/graphql`, which Vite proxies to the host gateway
on `http://localhost:8010/graphql`; test and prod return unconfigured without
a real URL. Port 8002 is billing REST and port 8003 is dispatch REST, and the
helper rejects those ports if explicitly configured. Test/prod GraphQL
endpoints do not exist in the checked-in local setup. The gateway has no CORS
middleware, so remote/direct endpoints require explicit CORS configuration.
Frontend configuration fails closed for test/prod rather than using a REST
port
or silently fall back to dev.

## 6. Verified discrepancies

| Contract detail | Documentation/source assumption | Introspected schema or observed behavior |
|---|---|---|
| `reserveAndActivateCharge.chargeFault` nullability | Earlier operation example used `Boolean = false` | Argument is `Boolean! = false`; use a non-null Boolean variable with default false if declaring it |
| Main operation type wrappers | Earlier type table focused on fields | See the SDL snapshot for exact list/object nullability, including `stations: [Station!]!` and nullable `Station.connectors: [Connector!]` |
| Frontend current mutation | UI source appeared to supply `station` and `key` values | GraphQL validation reports `$station` and `$key` are not defined by the operation; this was verified against the actual Strawberry schema |
| Flags resolver | Earlier contract used `canaryCharge` and `chargerFaultSimulation` | Resolver returns the three official names from the gateway process environment; all default to false and malformed values cause a GraphQL error |

`flags` is read-only. Local Compose explicitly sets `ENVIRONMENT=dev` and
defaults all three official flags to false; shell overrides can set the
development values. Services derive their default table names from
`ENVIRONMENT`, and reject configured table names that do not contain the
active environment token. Independent test/prod deployments are not present
in this repository and must provide separate gateway processes, service
processes, tables, and flag tables. Flag changes do not require a restart; the
environment's `SIMULATE_CHARGER_HARDWARE_FAULT` value alone decides fault
injection (`chargeFault` is a deprecated no-op).
