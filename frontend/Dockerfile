# syntax=docker/dockerfile:1
# Private SPA image: built once, served by unprivileged nginx on :8080.
# /graphql is reverse-proxied to the private API Gateway (same origin, no CORS);
# the upstream is injected at container start and the container fails closed
# when GRAPHQL_UPSTREAM_HOST/GRAPHQL_UPSTREAM_PATH are missing.
FROM node:24-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ENV VITE_ENVIRONMENT=dev
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --chmod=755 nginx/10-require-upstream.sh /docker-entrypoint.d/10-require-upstream.sh
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 8080
