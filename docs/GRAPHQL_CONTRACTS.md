# GraphQL Contracts

**Source of truth:** the current Strawberry schema in `gateway/app.py`,
confirmed by HTTP introspection and snapshotted at
[`graphql/schema.graphql`](./graphql/schema.graphql). The gateway is mounted at
`/graphql`; GraphQL names use Strawberry's default camel-case conversion.

**Verification scope (2026-11-20):** a temporary Uvicorn server served the
gateway on `127.0.0.1:8000` with Moto backing its startup DynamoDB table. An
HTTP POST to `/graphql` with the standard introspection query returned status
200, `Query` and `Mutation` roots, and no GraphQL errors. The test did not call
station, billing, or dispatch services. Docker Compose could not be started
because the Docker Desktop Linux engine was unavailable.

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

The query delegates to station service `/stations`. In an empty table that
service returns one hard-coded station. Reservation creation does not update
that listing's connector status. More seriously, `/stations` scans the same
table used for reservation records and returns all scanned items as stations.
Reservation items do not contain station fields, so after a reservation the
resolver can fail or return invalid station data. The backend must separate or
filter entity records before frontend availability can be trusted.

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
history window, or subscription.

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

The service creates a default wallet with balance `100.0` and currency `USD`
when the requested wallet does not exist. This is demo seeding, not an
authenticated account lifecycle.

### Flags

```graphql
query FeatureFlags {
  flags {
    name
    enabled
  }
}
```

Currently returns `canaryCharge` from `FLAG_CANARY` and
`chargerFaultSimulation` from `FLAG_FAULT`. There is no environment argument;
values come from the gateway process environment.

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
errors are separate. `idempotencyKey` is prefixed into a SAGA id but is not
conditionally inserted and is not fingerprinted against request arguments.
The same key with changed request data can return the prior SAGA.

`chargeFault` is a direct per-request test hook. It is not backed by the
`flags` query and must not be presented as an official persisted feature flag.

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

No retryability guard is enforced by the schema; frontend must only offer this
to a record whose state is `COMPENSATION_FAILED`. Backend implementation should
be hardened to validate eligibility before this action is considered safe.

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
| Official flags and independent values per `dev/test/prod` | Current names are `canaryCharge` / `chargerFaultSimulation`; process env values, no environment isolation or persistence | Backend + infrastructure |
| Change a feature flag | No mutation exists | Backend contract decision |
| Valid connector availability | Reservation does not mutate connector inventory/state | Station service + backend |
| SAGA detail and compensation timeline | Query exposes only summary and error | Gateway schema + SAGA persistence |
| Search, filter, stable ordering, cursor pagination | `sagas` has no args and scans max 100 | Gateway query + DynamoDB access pattern |
| Session end/stop | Dispatch REST stop exists; no GraphQL operation | Gateway contract |
| Live updates | No subscription/WebSocket/SSE | Gateway and infrastructure |
| Accurate multi-service environment health | dashboard only pings station service | Gateway |
| Runtime endpoint isolation | One gateway process has `ENVIRONMENT`; no separate gateway instances are set up in Compose | Deployment/configuration |
| Stable idempotency semantics | No conditional create or payload fingerprint/conflict response | Gateway and service owners |

Do not implement speculative names such as `setFeatureFlag`, `saga(id:)`,
`stopCharge`, or GraphQL subscriptions before backend approval and schema
implementation. When approved, document exact SDL, owner, error semantics, and
tests here first.

## 5. Frontend endpoint configuration

The helper in `frontend/src/graphql.ts` expects:

- `VITE_GRAPHQL_DEV_URL`
- `VITE_GRAPHQL_TEST_URL`
- `VITE_GRAPHQL_PROD_URL`

`frontend/.env.example` currently contains `VITE_GRAPHQL_URL=/graphql`, which
the helper does not read. The helper's compiled defaults are
`http://localhost:8000/graphql`, `http://localhost:8002/graphql`, and
`http://localhost:8003/graphql`. Only port 8000 is a GraphQL gateway in
Compose; 8002 is billing REST and 8003 is dispatch REST. Test/prod GraphQL
endpoints do not exist in the checked-in local setup and those defaults are
unsafe. The current local dev endpoint is `http://localhost:8000/graphql`.
Vite proxies relative `/graphql` to that gateway, but the helper's absolute
default bypasses the proxy. The gateway has no CORS middleware, so direct
remote endpoints require explicit CORS configuration. Future frontend
configuration must fail closed for test/prod rather than use either REST port
or silently fall back to dev.

## 6. Verified discrepancies

| Contract detail | Documentation/source assumption | Introspected schema or observed behavior |
|---|---|---|
| `reserveAndActivateCharge.chargeFault` nullability | Earlier operation example used `Boolean = false` | Argument is `Boolean! = false`; use a non-null Boolean variable with default false if declaring it |
| Main operation type wrappers | Earlier type table focused on fields | See the SDL snapshot for exact list/object nullability, including `stations: [Station!]!` and nullable `Station.connectors: [Connector!]` |
| Frontend current mutation | UI source appeared to supply `station` and `key` values | GraphQL validation reports `$station` and `$key` are not defined by the operation; this was verified against the actual Strawberry schema |
| Flags resolver | Planning mentioned environment feature flags | HTTP query returns `canaryCharge=true` and `chargerFaultSimulation=false` with the gateway defaults; changing process env values changes the next query result |

`flags` is a read-only query. No mutation persists a flag. The current Compose
configuration does not set `FLAG_CANARY` or `FLAG_FAULT`; the gateway defaults
are therefore used. `chargeFault` is a separate per-mutation input and is
forwarded to dispatch; it is not read from `chargerFaultSimulation`. The
resolver reads the process environment when queried, but the GraphQL API has
no way to change it; in normal operation a changed deployment environment
requires restarting/replacing the gateway process.
