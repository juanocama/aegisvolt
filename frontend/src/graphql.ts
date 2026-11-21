export type Environment = "dev" | "test" | "prod";

export const environment: Environment =
  (import.meta.env.VITE_ENVIRONMENT as Environment) || "dev";

export function resolveGraphqlUrl(selected: Environment): string | null {
  const url =
    selected === "dev"
      ? import.meta.env.VITE_GRAPHQL_DEV_URL || "/graphql"
      : selected === "test"
        ? import.meta.env.VITE_GRAPHQL_TEST_URL
        : import.meta.env.VITE_GRAPHQL_PROD_URL;

  if (!url || !url.trim()) return null;
  const raw = url.trim();
  if (raw.includes(":8002") || raw.includes(":8003")) return null;
  return raw;
}
