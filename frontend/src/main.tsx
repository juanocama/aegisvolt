import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { environment as initialEnvironment, resolveGraphqlUrl } from "./graphql";
import type { Environment } from "./graphql";
import { describeError, graphqlRequest } from "./graphql-client";
import {
  DASHBOARD_QUERY,
  FLAGS_QUERY,
  RESERVE_MUTATION,
  RETRY_COMPENSATION_MUTATION,
  STOP_AND_RELEASE_MUTATION,
  SAGAS_QUERY,
  STATIONS_QUERY,
  TELEMETRY_QUERY,
  WALLET_QUERY,
} from "./operations";
import "./styles.css";

type Connector = { id: string; type: string; status: string; powerKw: number };
type Station = { id: string; name: string; status: string; latitude: number; longitude: number; connectors: Connector[] | null };
type Telemetry = { stationId: string; connectorId: string; powerKw: number; energyKwh: number; state: string };
type Wallet = { id: string; balance: number; currency: string };
type FeatureFlag = { name: string; enabled: boolean };
type Saga = { id: string; correlationId: string; state: string; reservationStatus: string; chargeStatus: string; activationStatus: string; error: string | null };
type ChargeResult = { success: boolean; sagaId: string; correlationId: string; state: string; message: string };
type Page = "overview" | "stations" | "sagas" | "flags";

const DEMO_WALLET_ID = "wallet-1";

function StatusBadge({ state }: { state: string }) {
  const normalized = state.toLowerCase();
  const tone = normalized.includes("failed") || normalized.includes("reject") || normalized.includes("compensation_failed")
    ? "danger"
    : normalized.includes("complete") || normalized.includes("available") || normalized.includes("active")
      ? "success"
      : normalized.includes("uncertain") || normalized.includes("pending") || normalized.includes("occupied")
        ? "warning"
        : "neutral";
  return <span className={`status status-${tone}`}><span aria-hidden="true" />{state}</span>;
}

function LoadingState({ label }: { label: string }) {
  return <div className="state state-loading" role="status"><span className="spinner" />{label}</div>;
}

function EmptyState({ label }: { label: string }) {
  return <div className="state state-empty">{label}</div>;
}

export function App() {
  const [selectedEnvironment, setSelectedEnvironment] = useState<Environment>(initialEnvironment);
  const [page, setPage] = useState<Page>("overview");
  const [dashboard, setDashboard] = useState<{ environment: string; servicesOk: boolean } | null>(null);
  const [stations, setStations] = useState<Station[]>([]);
  const [telemetry, setTelemetry] = useState<Telemetry[]>([]);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [flags, setFlags] = useState<FeatureFlag[]>([]);
  const [sagas, setSagas] = useState<Saga[]>([]);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const inFlight = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const endpoint = resolveGraphqlUrl(selectedEnvironment);

  const clearData = useCallback(() => {
    setDashboard(null);
    setStations([]);
    setTelemetry([]);
    setWallet(null);
    setFlags([]);
    setSagas([]);
    setErrors({});
    setLastUpdated(null);
  }, []);

  const changeEnvironment = (nextEnvironment: Environment) => {
    clearData();
    setRefreshing(false);
    setLoading(Boolean(resolveGraphqlUrl(nextEnvironment)));
    setSelectedEnvironment(nextEnvironment);
  };

  const refresh = useCallback(async () => {
    const url = resolveGraphqlUrl(selectedEnvironment);
    if (!url || inFlight.current) return;

    inFlight.current = true;
    setRefreshing(true);
    setLoading(true);
    const results = await Promise.allSettled([
      graphqlRequest<{ dashboard: { environment: string; servicesOk: boolean } }>(url, DASHBOARD_QUERY).then((d) => d.dashboard),
      graphqlRequest<{ stations: Station[] }>(url, STATIONS_QUERY).then((d) => d.stations),
      graphqlRequest<{ telemetry: Telemetry[] }>(url, TELEMETRY_QUERY).then((d) => d.telemetry),
      graphqlRequest<{ wallet: Wallet }>(url, WALLET_QUERY, { walletId: DEMO_WALLET_ID }).then((d) => d.wallet),
      graphqlRequest<{ flags: FeatureFlag[] }>(url, FLAGS_QUERY).then((d) => d.flags),
      graphqlRequest<{ sagas: Saga[] }>(url, SAGAS_QUERY).then((d) => d.sagas),
    ]);
    inFlight.current = false;

    const keys = ["dashboard", "stations", "telemetry", "wallet", "flags", "sagas"];
    const nextErrors: Record<string, string> = {};
    results.forEach((result, index) => {
      if (result.status === "rejected") nextErrors[keys[index]] = describeError(result.reason);
    });
    setErrors(nextErrors);
    setLoading(false);
    setRefreshing(false);

    if (results.some((result) => result.status === "fulfilled")) setLastUpdated(Date.now());
    const [dashboardResult, stationsResult, telemetryResult, walletResult, flagsResult, sagasResult] = results;
    if (dashboardResult.status === "fulfilled") setDashboard(dashboardResult.value);
    if (stationsResult.status === "fulfilled") setStations(stationsResult.value);
    if (telemetryResult.status === "fulfilled") setTelemetry(telemetryResult.value);
    if (walletResult.status === "fulfilled") setWallet(walletResult.value);
    if (flagsResult.status === "fulfilled") setFlags(flagsResult.value);
    if (sagasResult.status === "fulfilled") setSagas(sagasResult.value);
  }, [selectedEnvironment]);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (!resolveGraphqlUrl(selectedEnvironment)) {
      return;
    }

    let cancelled = false;
    const loop = async () => {
      if (cancelled) return;
      if (document.visibilityState === "visible") await refresh();
      if (!cancelled) timer.current = setTimeout(loop, 4000);
    };
    void loop();
    const onVisible = () => {
      if (document.visibilityState === "visible" && !inFlight.current) void refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [selectedEnvironment, refresh, clearData]);

  const mismatch = dashboard?.environment !== undefined && dashboard.environment !== selectedEnvironment;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-row">
          <button className="brand" type="button" onClick={() => setPage("overview")} aria-label="AegisVolt overview">
            <span className="brand-mark" aria-hidden="true">AV</span>
            <span><strong>AegisVolt</strong><small>Operations console</small></span>
          </button>
          <nav className="environment-switch" aria-label="Environment">
            {(["dev", "test", "prod"] as Environment[]).map((env) => (
              <button
                type="button"
                key={env}
                aria-pressed={selectedEnvironment === env}
                className={selectedEnvironment === env ? "active" : ""}
                onClick={() => changeEnvironment(env)}
              >
                {env}
              </button>
            ))}
          </nav>
        </div>
        <nav className="primary-nav" aria-label="Primary navigation">
          {([
            ["overview", "Overview"],
            ["stations", "Stations & charging"],
            ["sagas", "SAGA history"],
            ["flags", "Feature flags"],
          ] as [Page, string][]).map(([key, label]) => (
            <button
              type="button"
              key={key}
              aria-current={page === key ? "page" : undefined}
              className={page === key ? "active" : ""}
              onClick={() => setPage(key)}
            >
              {label}
            </button>
          ))}
        </nav>
      </header>

      <main>
        {!endpoint ? (
          <div className="connection-banner danger" role="alert">
            <strong>Environment endpoint not configured.</strong>
            <span>No requests are sent for {selectedEnvironment}. Test/prod do not fall back to dev.</span>
          </div>
        ) : (
          <div className="connection-banner">
            <span className="endpoint">{endpoint}</span>
            <span className={mismatch ? "text-danger" : "connection-state"}>
              {mismatch ? "Environment mismatch" : loading ? "Connecting…" : lastUpdated ? `Updated ${new Date(lastUpdated).toLocaleTimeString()}` : "Disconnected"}
            </span>
            <button type="button" className="secondary-button" onClick={() => void refresh()} disabled={refreshing}>Refresh</button>
          </div>
        )}
        {mismatch && (
          <div className="connection-banner danger" role="alert">
            Selected <strong>{selectedEnvironment}</strong>, but the backend reports <strong>{dashboard?.environment}</strong>.
          </div>
        )}

        {page === "overview" && (
          <OverviewPage
            dashboard={dashboard}
            stations={stations}
            telemetry={telemetry}
            wallet={wallet}
            sagas={sagas}
            loading={loading}
            errors={errors}
            selectedEnvironment={selectedEnvironment}
            onNavigate={setPage}
          />
        )}
        {page === "stations" && (
          <StationsPage
            stations={stations}
            sagas={sagas}
            wallet={wallet}
            loading={loading}
            error={errors.stations}
            selectedEnvironment={selectedEnvironment}
            onComplete={refresh}
          />
        )}
        {page === "sagas" && (
          <SagasPage
            sagas={sagas}
            loading={loading}
            error={errors.sagas}
            selectedEnvironment={selectedEnvironment}
            onComplete={refresh}
          />
        )}
        {page === "flags" && (
          <FlagsPage flags={flags} loading={loading} error={errors.flags} />
        )}
      </main>
      <footer>AegisVolt data refreshes by polling every few seconds while this tab is visible. This is not a live stream.</footer>
    </div>
  );
}

function SagasPage({
  sagas,
  loading,
  error,
  selectedEnvironment,
  onComplete,
}: {
  sagas: Saga[];
  loading: boolean;
  error?: string;
  selectedEnvironment: Environment;
  onComplete: () => Promise<void>;
}) {
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [retryOutcome, setRetryOutcome] = useState<{ kind: "success" | "error"; message: string } | null>(null);

  const retry = async (sagaId: string) => {
    setRetryOutcome(null);
    setRetryingId(sagaId);
    const url = resolveGraphqlUrl(selectedEnvironment);
    if (!url) {
      setRetryOutcome({ kind: "error", message: "Environment endpoint not configured." });
      setRetryingId(null);
      return;
    }
    try {
      const data = await graphqlRequest<{ retryCompensation: Saga }>(url, RETRY_COMPENSATION_MUTATION, { sagaId });
      setRetryOutcome({ kind: "success", message: `SAGA ${data.retryCompensation.id} is now ${data.retryCompensation.state}.` });
      await onComplete();
    } catch (requestError) {
      setRetryOutcome({ kind: "error", message: describeError(requestError) });
    } finally {
      setRetryingId(null);
    }
  };

  return (
    <>
      <div className="page-heading"><div><p className="eyebrow">AegisVolt · {selectedEnvironment}</p><h1>SAGA history</h1></div></div>
      {loading && sagas.length === 0 && <LoadingState label="Loading SAGA summaries…" />}
      {error && <div role="alert" className="inline-error">{error}</div>}
      {retryOutcome && <div role={retryOutcome.kind === "error" ? "alert" : "status"} className={`outcome outcome-${retryOutcome.kind}`}>{retryOutcome.message}</div>}
      {sagas.length === 0 ? <EmptyState label="No SAGA records returned." /> : (
        <Panel title="Transaction summaries">
          <div className="table-scroll">
            <table>
              <caption>SAGA summaries and current step states</caption>
              <thead><tr><th>SAGA</th><th>Correlation</th><th>State</th><th>Reservation</th><th>Charge</th><th>Activation</th><th>Error</th><th>Action</th></tr></thead>
              <tbody>
                {sagas.map((saga) => (
                  <tr key={saga.id}>
                    <td><code>{saga.id}</code></td>
                    <td><code>{saga.correlationId}</code></td>
                    <td><StatusBadge state={saga.state} /></td>
                    <td><StatusBadge state={saga.reservationStatus} /></td>
                    <td><StatusBadge state={saga.chargeStatus} /></td>
                    <td><StatusBadge state={saga.activationStatus} /></td>
                    <td>{saga.error ?? "—"}</td>
                    <td>{saga.state === "COMPENSATION_FAILED" ? (
                      <button type="button" className="secondary-button" disabled={retryingId === saga.id} onClick={() => void retry(saga.id)}>
                        {retryingId === saga.id ? "Retrying…" : "Retry compensation"}
                      </button>
                    ) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted">Detail timelines, compensation attempt counts, filtering, sorting, and pagination are unavailable in the current GraphQL contract.</p>
        </Panel>
      )}
    </>
  );
}

function FlagsPage({ flags, loading, error }: { flags: FeatureFlag[]; loading: boolean; error?: string }) {
  return (
    <>
      <div className="page-heading"><div><p className="eyebrow">Read-only process configuration</p><h1>Feature flags</h1></div></div>
      {loading && flags.length === 0 && <LoadingState label="Loading feature flags…" />}
      {error && <div role="alert" className="inline-error">{error}</div>}
      {flags.length === 0 ? <EmptyState label="No feature flags returned." /> : (
        <div className="flags-grid">
          {flags.map((flag) => (
            <article className="panel flag-card" key={flag.name}>
              <div><strong>{flag.name}</strong><StatusBadge state={flag.enabled ? "ENABLED" : "DISABLED"} /></div>
            </article>
          ))}
        </div>
      )}
      <div className="notice">Feature flags are process-level and read-only. No flag editing mutation exists. Surge pricing and fast-charge boost have no implemented behavior until rules are approved.</div>
    </>
  );
}

const rootElement = document.getElementById("root");
if (rootElement) {
  createRoot(rootElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

function Panel({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-heading"><h2>{title}</h2>{action}</div>
      {children}
    </section>
  );
}

function OverviewPage({
  dashboard,
  stations,
  telemetry,
  wallet,
  sagas,
  loading,
  errors,
  selectedEnvironment,
  onNavigate,
}: {
  dashboard: { environment: string; servicesOk: boolean } | null;
  stations: Station[];
  telemetry: Telemetry[];
  wallet: Wallet | null;
  sagas: Saga[];
  loading: boolean;
  errors: Record<string, string>;
  selectedEnvironment: Environment;
  onNavigate: (page: Page) => void;
}) {
  const connectors = stations.flatMap((station) => station.connectors ?? []);
  const counts = connectors.reduce<Record<string, number>>((result, connector) => {
    result[connector.status] = (result[connector.status] ?? 0) + 1;
    return result;
  }, {});

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">AegisVolt · {selectedEnvironment}</p>
          <h1>Overview</h1>
        </div>
      </div>
      {loading && !dashboard && <LoadingState label="Loading environment data…" />}
      <div className="overview-grid">
        <Panel title="Service status">
          {errors.dashboard ? <div role="alert" className="inline-error">{errors.dashboard}</div> : dashboard ? (
            <>
              <StatusBadge state={dashboard.servicesOk ? "SERVICES OK" : "SERVICES DEGRADED"} />
              <dl className="metadata"><dt>Backend environment</dt><dd>{dashboard.environment}</dd></dl>
              <p className="muted">The current backend only checks the station service for this status.</p>
            </>
          ) : <EmptyState label="No dashboard status returned." />}
        </Panel>
        <Panel title="Stations & connectors">
          {errors.stations ? <div role="alert" className="inline-error">{errors.stations}</div> : stations.length === 0 ? <EmptyState label="No stations returned." /> : (
            <>
              <div className="kpi-row"><div><strong>{stations.length}</strong><span>Stations</span></div><div><strong>{connectors.length}</strong><span>Connectors</span></div></div>
              <div className="status-list">{Object.entries(counts).map(([status, count]) => <div key={status}><StatusBadge state={status} /><strong>{count}</strong></div>)}</div>
              <p className="muted">Counted from returned data only.</p>
            </>
          )}
        </Panel>
        <Panel title="Demo wallet">
          {errors.wallet ? <div role="alert" className="inline-error">{errors.wallet}</div> : wallet ? (
            <>
              <div className="wallet-value">{wallet.balance.toFixed(2)} <span>{wallet.currency}</span></div>
              <dl className="metadata"><dt>Wallet</dt><dd>{wallet.id}</dd></dl>
              <p className="muted">Wallet-1 is demo configuration.</p>
            </>
          ) : <EmptyState label="Wallet wallet-1 not returned." />}
        </Panel>
        <Panel title="Telemetry snapshot">
          {errors.telemetry ? <div role="alert" className="inline-error">{errors.telemetry}</div> : telemetry.length === 0 ? <EmptyState label="No telemetry snapshot returned." /> : (
            <div className="telemetry-list">
              {telemetry.map((item) => (
                <div className="telemetry-item" key={`${item.stationId}-${item.connectorId}`}>
                  <dl><dt>Station</dt><dd>{item.stationId}</dd><dt>Connector</dt><dd>{item.connectorId}</dd><dt>Power</dt><dd>{item.powerKw} kW</dd><dt>Energy</dt><dd>{item.energyKwh} kWh</dd><dt>State</dt><dd><StatusBadge state={item.state} /></dd></dl>
                </div>
              ))}
            </div>
          )}
          <p className="muted">Current snapshot only; no timestamp or history is provided.</p>
        </Panel>
        <Panel title="Recent SAGAs" action={<button type="button" className="text-button" onClick={() => onNavigate("sagas")}>View history →</button>}>
          {errors.sagas ? <div role="alert" className="inline-error">{errors.sagas}</div> : sagas.length === 0 ? <EmptyState label="No SAGAs returned." /> : (
            <ul className="saga-summary">{sagas.slice(0, 5).map((saga) => <li key={saga.id}><code>{saga.id}</code><StatusBadge state={saga.state} /></li>)}</ul>
          )}
        </Panel>
      </div>
    </>
  );
}

function StationsPage({
  stations,
  sagas,
  wallet,
  loading,
  error,
  selectedEnvironment,
  onComplete,
}: {
  stations: Station[];
  sagas: Saga[];
  wallet: Wallet | null;
  loading: boolean;
  error?: string;
  selectedEnvironment: Environment;
  onComplete: () => Promise<void>;
}) {
  const [selectedStationId, setSelectedStationId] = useState("");
  const [selectedConnectorId, setSelectedConnectorId] = useState("");
  const [amount, setAmount] = useState("25");
  const [walletId, setWalletId] = useState(DEMO_WALLET_ID);
  const [fault, setFault] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());
  const [submitting, setSubmitting] = useState(false);
  const [fieldError, setFieldError] = useState("");
  const [outcome, setOutcome] = useState<{ kind: "success" | "business" | "unknown" | "error"; message: string } | null>(null);
  const [stopping, setStopping] = useState(false);
  const stoppableSaga = sagas.find((saga) => saga.state === "COMPLETED");

  const effectiveStationId = selectedStationId || stations[0]?.id || "";
  const selectedStation = stations.find((station) => station.id === effectiveStationId);
  const selectedConnector = selectedStation?.connectors?.find((connector) => connector.id === selectedConnectorId);

  const stopAndRelease = async () => {
    if (!stoppableSaga) return;
    const url = resolveGraphqlUrl(selectedEnvironment);
    if (!url) {
      setOutcome({ kind: "error", message: "Environment endpoint not configured." });
      return;
    }
    setStopping(true);
    setOutcome(null);
    try {
      const data = await graphqlRequest<{ stopAndRelease: Saga }>(
        url,
        STOP_AND_RELEASE_MUTATION,
        { sagaId: stoppableSaga.id },
      );
      setOutcome({
        kind: "success",
        message: `Session stopped and reservation released: ${data.stopAndRelease.state}.`,
      });
      await onComplete();
    } catch (requestError) {
      setOutcome({ kind: "error", message: describeError(requestError) });
    } finally {
      setStopping(false);
    }
  };

  const submit = async () => {
    setFieldError("");
    setOutcome(null);
    if (!selectedStation || !selectedConnector) {
      setFieldError("Select a station and concrete connector.");
      return;
    }
    if (selectedConnector.status !== "available") {
      setFieldError("The selected connector is not available.");
      return;
    }
    const numericAmount = Number(amount);
    if (!walletId.trim()) {
      setFieldError("Wallet ID is required.");
      return;
    }
    if (!amount.trim() || !Number.isFinite(numericAmount) || numericAmount <= 0) {
      setFieldError("Amount must be a positive number.");
      return;
    }
    const url = resolveGraphqlUrl(selectedEnvironment);
    if (!url) {
      setOutcome({ kind: "error", message: "Environment endpoint not configured." });
      return;
    }

    setSubmitting(true);
    try {
      const data = await graphqlRequest<{ reserveAndActivateCharge: ChargeResult }>(url, RESERVE_MUTATION, {
        walletId: walletId.trim(),
        stationId: selectedStation.id,
        connectorId: selectedConnector.id,
        amount: numericAmount,
        idempotencyKey,
        chargeFault: fault,
      });
      const result = data.reserveAndActivateCharge;
      setOutcome({
        kind: result.success ? "success" : "business",
        message: `${result.state}: ${result.message} (SAGA ${result.sagaId}, correlation ${result.correlationId})`,
      });
      await onComplete();
    } catch (requestError) {
      const message = describeError(requestError);
      if (message.startsWith("Network error")) {
        setOutcome({ kind: "unknown", message: `${message}. The server outcome is unknown; retry uses the same idempotency key.` });
      } else {
        setOutcome({ kind: "error", message });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const newIntent = () => {
    setIdempotencyKey(crypto.randomUUID());
    setOutcome(null);
  };

  return (
    <>
      <div className="page-heading"><div><p className="eyebrow">AegisVolt · {selectedEnvironment}</p><h1>Stations & charging</h1></div></div>
      {loading && stations.length === 0 && <LoadingState label="Loading stations…" />}
      {error && <div role="alert" className="inline-error">{error}</div>}
      <div className="charging-layout">
        <Panel title="Stations & connectors">
          {stations.length === 0 ? <EmptyState label="No stations returned." /> : (
            <div className="station-list">
              {stations.map((station) => (
                <div className="station-group" key={station.id}>
                  <button
                    type="button"
                    className={`station-card ${effectiveStationId === station.id ? "selected" : ""}`}
                    aria-pressed={effectiveStationId === station.id}
                    onClick={() => {
                      setSelectedStationId(station.id);
                      setSelectedConnectorId("");
                      newIntent();
                    }}
                  >
                    <div><strong>{station.name}</strong><small>{station.id} · {station.status}</small></div>
                    <small>{station.latitude}, {station.longitude}</small>
                  </button>
                  {effectiveStationId === station.id && (
                    <div className="connector-list" aria-label={`Connectors at ${station.name}`}>
                      {(station.connectors ?? []).map((connector) => (
                        <button
                          type="button"
                          key={connector.id}
                          className={`connector-card ${selectedConnectorId === connector.id ? "selected" : ""}`}
                          aria-pressed={selectedConnectorId === connector.id}
                          onClick={() => { setSelectedConnectorId(connector.id); newIntent(); }}
                        >
                          <div><strong>{connector.id}</strong><StatusBadge state={connector.status} /></div>
                          <small>{connector.type} · {connector.powerKw} kW</small>
                        </button>
                      ))}
                      {(station.connectors ?? []).length === 0 && <EmptyState label="No connectors returned." />}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Panel>
        <Panel title="Charge request">
          <div className="charge-form">
            <label>Wallet ID<input value={walletId} onChange={(event) => setWalletId(event.target.value)} /></label>
            <small className="muted">Demo wallet: {DEMO_WALLET_ID}</small>
            <label>Amount <span className="field-meta">{wallet?.currency ?? "currency unavailable"}</span><input type="number" min="0" step="any" value={amount} onChange={(event) => setAmount(event.target.value)} /></label>
            <label className="checkbox-row"><input type="checkbox" checked={fault} disabled={selectedEnvironment !== "dev"} onChange={(event) => setFault(event.target.checked)} />Simulate charger fault <small>dev demo control only</small></label>
            <div className="selected-summary"><span>Selected</span><strong>{selectedStation?.name ?? "No station"} · {selectedConnector?.id ?? "No connector"}</strong></div>
            {fieldError && <div className="inline-error" role="alert">{fieldError}</div>}
            {outcome && (
              <div role={outcome.kind === "error" ? "alert" : "status"} className={`outcome outcome-${outcome.kind}`}>
                {outcome.message}
              </div>
            )}
            <button
              type="button"
              className="primary-button"
              disabled={submitting || !selectedStation || !selectedConnector || selectedConnector.status !== "available"}
              onClick={() => void submit()}
            >
              {submitting ? "Submitting…" : outcome?.kind === "unknown" ? "Retry with same idempotency key" : "Reserve & activate charge"}
            </button>
            {outcome?.kind === "unknown" && <button type="button" className="secondary-button" onClick={newIntent}>Start new intent</button>}
            {selectedEnvironment === "dev" && stoppableSaga && (
              <button type="button" className="secondary-button" disabled={stopping} onClick={() => void stopAndRelease()}>
                {stopping ? "Stopping…" : "Stop & release demo session"}
              </button>
            )}
          </div>
        </Panel>
      </div>
    </>
  );
}
