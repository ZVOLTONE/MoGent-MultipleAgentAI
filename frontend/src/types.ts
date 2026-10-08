// Types mirroring the backend contract (PRD Web-Cards 9.1, 9.2).

export interface CardFact {
  label: string;
  value: string;
  as_of?: string;
  source?: string;
  evidence_id?: string | null;
  derived?: boolean;
  formula?: string | null;
}

export interface NewsItem {
  title: string;
  source?: string;
  date?: string;
  url?: string;
}

export interface GlossaryItem {
  term: string;
  definition: string;
}

export interface SeriesPoint {
  d: string;
  c: number;
}

export type CardType =
  | "summary"
  | "metrics"
  | "chart"
  | "news"
  | "risk"
  | "trace"
  | "glossary";

export interface Card {
  id: string;
  type: CardType;
  title: string;
  subtitle?: string;
  facts?: CardFact[];
  bullets?: string[];
  items?: (NewsItem | GlossaryItem)[];
  series?: SeriesPoint[];
}

export interface CardsMeta {
  agent: string;
  n_facts: number;
  profile: string;
  font_scale: number;
  density: string;
}

export interface CardsResponse {
  cards: Card[];
  meta: CardsMeta;
}

export interface QueryResult {
  status: string;
  answer: string;
  ticker?: string | null;
  intent?: string[];
  persona?: string[];
  agents_used?: string[];
  agent_factory?: Record<string, unknown>;
  facts?: unknown[];
  evidence?: unknown[];
  limitations?: unknown[];
  contradictions?: unknown[];
  tool_calls?: unknown[];
}
