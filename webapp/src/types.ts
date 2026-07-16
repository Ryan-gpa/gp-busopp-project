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

export interface MaterialityBenchmark {
  basis: string
  figure: number
  pct: number
  amount: number
  note: string
}

export interface Financials {
  totalAssets: number | null
  totalLiab: number | null
  netAssets: number | null
  revenue: number | null
  profitBeforeTax: number | null
  totalExpenditure: number | null
}

export interface ForeignSignal {
  exchange: string
  type: string
  headline: string
  date: string
}

export interface DomicileInfo {
  domicile: "AU" | "NZ" | "FOREIGN" | "UNKNOWN"
  registeredCountry?: string
  isForeignExempt?: boolean
  isin?: string
  listingDate?: string
  companyName?: string
  domicileSource?: string
}

export interface Officer {
  name: string
  role: string
  roleNorm: string
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
  domicile?: "AU" | "NZ" | "FOREIGN" | "UNKNOWN"
  domicileInfo?: DomicileInfo
  foreignSignals?: ForeignSignal[]
  officers?: Officer[]
  financials?: Financials
  materialityBenchmarks?: MaterialityBenchmark[]
  results: ResultItem[]
  asx: AsxBlock
}

export type RenderStatus =
  | "Addressed"
  | "Represented differently"
  | "Not detected"
  | "Below materiality"
  | "N/A"
  | "Unverified"

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
  "Unverified"
]

export type ContactFetchState = {
  status: "loading" | "done" | "error"
  contacts?: any[]
  error?: string
  fetchedAt?: number
  source?: string
}

export interface CompanyNews {
  url: string;
  title: string;
  summary: string;
  source: string;
  fetchedAt: number;
  publishedAt?: string | null;
}

export interface UnlistedCompany {
  id: string;
  name: string;
  domain: string;
  organization_revenue?: number;
  annual_revenue?: number;
  estimated_revenue?: number;
  estimated_num_employees?: number;
  linkedin_employee_count?: number; // despite the name, this is org["estimated_num_employees"] unless employeeCountSource says otherwise
  employeeCountSource?: 'manual_research' | 'apollo_estimate';
  dataSource?: 'apollo' | 'rocketreach' | 'hunter' | 'asic' | 'linkedin' | 'web' | 'other';
  revenueBand?: string; // band/obligation label when no point estimate exists (RocketReach filter or ASIC lodgement signal)
  asic?: Record<string, string>; // server-side ASIC register join, same shape as /api/unlisted/validate
  contacts?: { name: string; title: string; linkedin_url?: string; linkedinUrl?: string; email?: string | null; emailStatus?: string; source?: string; phoneNumbers?: string[] }[];
  has_cached_contacts?: boolean;
  prefetched_contact_fetch?: ContactFetchState;
  _asx_exclusion_reason?: string
  infringementNotices?: InfringementNotice[];
  news?: CompanyNews[];
}

export interface InfringementNotice {
  year: string;
  name: string;
  licenceOrAcn: string;
  datePaid: string;
  noticeId: string | null;
  noticePdfUrl: string | null;
  mediaReleaseId: string | null;
  mediaReleaseTitle: string | null;
  mediaReleaseUrl: string | null;
  legislation: string;
}

export interface UnlistedSearchResult {
  tier1: UnlistedCompany[]
  tier2: UnlistedCompany[]
  excludedAsxMatches: UnlistedCompany[]
  excludedOverMax: UnlistedCompany[]
  excludedUnderMin: UnlistedCompany[]
  excludedIncompleteData: UnlistedCompany[]
  excludedNotOnAsic?: UnlistedCompany[]
  asicJoinAvailable?: boolean
  thresholds?: { t1Min: number; t2Min: number }
  pagination: {
    total_entries?: number | null
    total_pages?: number | null
    fetched_entries?: number
    fetched_pages?: number
    rate_limited?: boolean
    served_from_local_fallback?: boolean
    discovery_source?: string
    truncated?: boolean
  } | null
  fetchedAt?: number // unix seconds
  fromCache?: boolean
}

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

export interface CurrentUser {
  userId: string
  displayName: string
}

export interface VoteEntry {
  userId: string
  displayName: string
  vote: "up" | "down"
  votedAt: string
}

export interface VotePhrase {
  id: string
  text: string
  documentKey: string
  headline: string
  announcementType: string
  createdAt: string
  votes: VoteEntry[]
  score: number
  upvotes: number
  downvotes: number
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
