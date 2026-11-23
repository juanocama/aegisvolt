#!/bin/sh
# Fail closed: never start without an explicit private GraphQL upstream.
set -eu
: "${GRAPHQL_UPSTREAM_HOST:?GRAPHQL_UPSTREAM_HOST is required}"
: "${GRAPHQL_UPSTREAM_PATH:?GRAPHQL_UPSTREAM_PATH is required}"
