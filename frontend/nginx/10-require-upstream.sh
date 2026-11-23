#!/bin/sh
# Fail closed: never start without an explicit private GraphQL upstream.
set -eu
: "${GRAPHQL_UPSTREAM_HOST:?GRAPHQL_UPSTREAM_HOST is required}"
: "${GRAPHQL_UPSTREAM_PATH:?GRAPHQL_UPSTREAM_PATH is required}"
case "${GRAPHQL_UPSTREAM_SCHEME:-}" in
  https) ;;
  http)
    # Plain HTTP is only for the local Compose stack (gateway on the same host network).
    [ "${ALLOW_INSECURE_LOCAL_UPSTREAM:-false}" = "true" ] || { echo "GRAPHQL_UPSTREAM_SCHEME=http requires ALLOW_INSECURE_LOCAL_UPSTREAM=true" >&2; exit 1; } ;;
  *) echo "GRAPHQL_UPSTREAM_SCHEME must be https or http" >&2; exit 1 ;;
esac
