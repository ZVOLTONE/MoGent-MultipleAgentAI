import type { CardsResponse, QueryResult } from "@/types";

const BASE = (import.meta.env.VITE_API as string) || "http://localhost:8000";

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${path} ${res.status}: ${detail.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export function runQuery(query: string): Promise<QueryResult> {
  return postJSON<QueryResult>("/query", { query, debug: true });
}

export function buildCards(queryResult: QueryResult): Promise<CardsResponse> {
  return postJSON<CardsResponse>("/cards", queryResult);
}

export { BASE as API_BASE };
