export type GraphQLErrorItem = { message: string };

export class NetworkError extends Error {
  override name = "NetworkError";
}

export class HttpError extends Error {
  override name = "HttpError";
  constructor(public status: number) {
    super(`HTTP ${status}`);
  }
}

export class GraphQLResponseError extends Error {
  override name = "GraphQLResponseError";
  constructor(public errors: GraphQLErrorItem[]) {
    super(errors.map((error) => error.message).join("; "));
  }
}

export async function graphqlRequest<T>(
  url: string,
  query: string,
  variables?: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, variables }),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new NetworkError(error instanceof Error ? error.message : "Network request failed");
  }

  if (!response.ok) throw new HttpError(response.status);
  const body = (await response.json()) as { data?: T; errors?: GraphQLErrorItem[] };
  if (body.errors?.length) throw new GraphQLResponseError(body.errors);
  if (!body.data) throw new GraphQLResponseError([{ message: "Empty GraphQL response" }]);
  return body.data;
}

export function describeError(error: unknown): string {
  if (error instanceof NetworkError) return `Network error: ${error.message}`;
  if (error instanceof HttpError) return `Server responded with HTTP ${error.status}`;
  if (error instanceof GraphQLResponseError) return `GraphQL error: ${error.message}`;
  return error instanceof Error ? error.message : "Unknown error";
}
