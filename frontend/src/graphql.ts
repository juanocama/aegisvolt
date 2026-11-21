export type Environment = "dev"|"test"|"prod";
export const environment: Environment = (import.meta.env.VITE_ENVIRONMENT as Environment) || "dev";
export const graphqlUrls: Record<Environment,string> = {
  dev: import.meta.env.VITE_GRAPHQL_DEV_URL || "http://localhost:8000/graphql",
  test: import.meta.env.VITE_GRAPHQL_TEST_URL || "http://localhost:8002/graphql",
  prod: import.meta.env.VITE_GRAPHQL_PROD_URL || "http://localhost:8003/graphql",
};

export async function gql<T>(selectedEnvironment:Environment,query:string,variables?:Record<string,unknown>):Promise<T>{
  const response=await fetch(graphqlUrls[selectedEnvironment],{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({query,variables})});
  if(!response.ok) throw new Error(`GraphQL HTTP ${response.status}`);
  const body=await response.json();
  if(body.errors) throw new Error(body.errors[0].message);
  return body.data as T;
}
