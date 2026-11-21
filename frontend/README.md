# AegisVolt Frontend

React/TypeScript/Vite operations console for the AegisVolt GraphQL gateway.

## Install and run

```powershell
cd C:\Users\iamju\Desktop\patrones\aegisvolt\frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

The local Vite proxy forwards `/graphql` to `http://localhost:8010/graphql`.
No backend service REST ports are used by browser code.

## Environment configuration

Copy `.env.example` and configure:

- `VITE_ENVIRONMENT=dev`
- `VITE_GRAPHQL_DEV_URL=/graphql`
- Test and prod URLs may be added only when real isolated GraphQL gateways exist.

Test and prod intentionally fail closed when no endpoint is configured.
The UI does not fall back to dev or to billing/dispatch REST ports.

## Commands

```powershell
npm run build
npm test
npm run lint
npm run dev
```

## Contract and limits

The UI uses only the checked-in GraphQL operations in `src/operations.ts`.
It polls every 4 seconds while visible. This is polling, not live streaming.
SAGA details, pagination, flag mutations, stop-session, and subscriptions are
not invented because the current backend contract does not expose them.
