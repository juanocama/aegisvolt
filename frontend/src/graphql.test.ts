import { describe, expect, it } from "vitest";
import { resolveGraphqlUrl } from "./graphql";

describe("environment GraphQL routing", () => {
  it("does not provide unsafe REST-port defaults", () => {
    expect(resolveGraphqlUrl("test")).toBeNull();
    expect(resolveGraphqlUrl("prod")).toBeNull();
  });

  it("rejects REST service ports even if configured", () => {
    const original = import.meta.env.VITE_GRAPHQL_TEST_URL;
    import.meta.env.VITE_GRAPHQL_TEST_URL = "http://localhost:8002/graphql";
    expect(resolveGraphqlUrl("test")).toBeNull();
    import.meta.env.VITE_GRAPHQL_TEST_URL = original;
  });
});
