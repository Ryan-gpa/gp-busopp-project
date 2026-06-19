export interface Summary {
  present: number
  not_found: number
  below_materiality: number
  na: number
}

export interface ResultItem {
  id: string
  standard: string
  clause: string
  title: string
  category: "B" | "conditional" | "presentation"
  materiality: "high" | "medium" | "low"
  assessment: "qualitative" | "quantitative"
  balance: number | null
  materialityThreshold: number | null
  status: "PRESENT" | "NOT FOUND" | "N/A" | "BELOW MATERIALITY"
  recommendation: string
  representationNote: string
  divergent: boolean
}

export interface AsxItem {
  date: string
  headline: string
  type: string
  priceSensitive: boolean
  importance: string
  theme: string
  rag: "GREEN" | "AMBER" | "RED"
  oppServices: string[]
  priority: number
  source: string
  localFile: string | null
  documentKey?: string
  relevant?: boolean
}

export interface AsxBlock {
  ticker: string
  entityXid?: number
  online?: boolean
  method?: string
  periodStart: string
  periodEnd: string
  months?: number
  apiCapped?: boolean
  count: number
  priceSensitive: number
  relevant?: number
  fromApi?: number
  fromLocal?: number
  items: AsxItem[]
  oppCounts: { GREEN: number; AMBER: number; RED: number }
  ragMeaning?: { GREEN: string; AMBER: string; RED: string }
}

export interface FindingsJSON {
  entity: string
  ticker: string
  reportType: "interim" | "annual"
  reportFile: string
  basis: string
  detectionNote: string
  checklistVersion: string
  summary: Summary
  materiality: number
  materialityBasis: string
  totalAssets: number
  results: ResultItem[]
  asx: AsxBlock
}

export type RenderStatus =
  | "Addressed"
  | "Represented differently"
  | "Not detected"
  | "Below materiality"
  | "N/A"

export function renderStatus(item: ResultItem): RenderStatus {
  if (item.status === "N/A") return "N/A"
  if (item.status === "BELOW MATERIALITY") return "Below materiality"
  if (item.status === "PRESENT") {
    return item.divergent ? "Represented differently" : "Addressed"
  }
  return "Not detected"
}

export const RENDER_STATUS_ORDER: RenderStatus[] = [
  "Not detected",
  "Represented differently",
  "Addressed",
  "Below materiality",
  "N/A",
]

export const GP_SERVICES = [
  "Transaction Readiness",
  "Financial Reporting",
  "Business Process Redesign",
  "Commercial Opportunities",
  "Audit Readiness",
] as const

export function formatCurrency(n: number): string {
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
    maximumFractionDigits: 0,
  }).format(n)
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-AU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}

export interface TypeHistory {
  included: number
  excluded: number
  mixed: number
}

export interface UserPrefs {
  version: string
  excludedTypes: string[]
  typeHistory: Record<string, TypeHistory>
}
