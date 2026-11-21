export const DASHBOARD_QUERY = `query Dashboard {
  dashboard { environment servicesOk }
}`;

export const STATIONS_QUERY = `query Stations {
  stations {
    id name status latitude longitude
    connectors { id type status powerKw }
  }
}`;

export const TELEMETRY_QUERY = `query Telemetry {
  telemetry { stationId connectorId powerKw energyKwh state }
}`;

export const WALLET_QUERY = `query Wallet($walletId: String!) {
  wallet(walletId: $walletId) { id balance currency }
}`;

export const FLAGS_QUERY = `query FeatureFlags {
  flags { name enabled }
}`;

export const SAGAS_QUERY = `query Sagas {
  sagas {
    id correlationId state reservationStatus chargeStatus activationStatus error
  }
}`;

export const RESERVE_MUTATION = `mutation ReserveAndActivateCharge(
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
}`;

export const RETRY_COMPENSATION_MUTATION = `mutation RetryCompensation($sagaId: String!) {
  retryCompensation(sagaId: $sagaId) {
    id correlationId state reservationStatus chargeStatus activationStatus error
  }
}`;

export const STOP_AND_RELEASE_MUTATION = `mutation StopAndRelease($sagaId: String!) {
  stopAndRelease(sagaId: $sagaId) {
    id correlationId state reservationStatus chargeStatus activationStatus error
  }
}`;
