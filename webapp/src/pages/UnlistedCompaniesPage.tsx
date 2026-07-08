import { useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { CheckCircle2, AlertCircle, Rocket, Landmark, ShieldAlert, Telescope, ChevronUp, ChevronDown, ChevronsUpDown, ExternalLink } from "lucide-react"
import type { UnlistedSearchResult, UnlistedCompany } from "@/types"
import StatusPage from "@/pages/StatusPage"

// Every field ASIC actually publishes for a matched company (see the
// dataset's help file on data.gov.au) — blank ones are omitted by the backend.
type AsicValidation = {
  status: string
  reason: string
  matchedName?: string
  acn?: string
  abn?: string
  asicType?: string
  asicClass?: string
  asicSubClass?: string
  dateOfRegistration?: string
  dateOfDeregistration?: string
  previousStateOfRegistration?: string
  stateRegistrationNumber?: string
  modifiedSinceLastReport?: string
  currentNameIndicator?: string
  currentName?: string
  currentNameStartDate?: string
}

const ASIC_FIELD_LABELS: [keyof AsicValidation, string][] = [
  ["acn", "ACN"],
  ["abn", "ABN"],
  ["asicType", "Type"],
  ["asicClass", "Class"],
  ["asicSubClass", "Sub Class"],
  ["dateOfRegistration", "Date of Registration"],
  ["dateOfDeregistration", "Date of Deregistration"],
  ["currentName", "Current Name"],
  ["currentNameStartDate", "Current Name Start Date"],
  ["previousStateOfRegistration", "Previous State of Registration"],
  ["stateRegistrationNumber", "State Registration Number"],
  ["modifiedSinceLastReport", "Modified Since Last Report"],
]

const API_BASE = import.meta.env.VITE_API_URL || ""
const PAGE_SIZE = 25

type SortKey = "name" | "revenue" | "employees"
type SortState = { key: SortKey; dir: "asc" | "desc" }

const getRevenueValue = (c: UnlistedCompany): number | null => {
  const v = c.organization_revenue ?? c.annual_revenue ?? c.estimated_revenue
  return v ?? null
}
const getEmployeeValue = (c: UnlistedCompany): number | null => {
  const v = c.linkedin_employee_count ?? c.estimated_num_employees
  return v ?? null
}

function sortCompanies(list: UnlistedCompany[], sort: SortState): UnlistedCompany[] {
  const dirMul = sort.dir === "asc" ? 1 : -1
  return [...list].sort((a, b) => {
    if (sort.key === "name") {
      return a.name.localeCompare(b.name) * dirMul
    }
    const av = sort.key === "revenue" ? getRevenueValue(a) : getEmployeeValue(a)
    const bv = sort.key === "revenue" ? getRevenueValue(b) : getEmployeeValue(b)
    if (av == null && bv == null) return 0
    if (av == null) return 1 // unknowns sort last regardless of direction
    if (bv == null) return -1
    return (av - bv) * dirMul
  })
}

import type { ContactFetchState } from "@/types"

export default function UnlistedCompaniesPage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [results, setResults] = useState<UnlistedSearchResult | null>(null)
  const [validationStatuses, setValidationStatuses] = useState<Record<string, AsicValidation>>({})
  const [expandedAsic, setExpandedAsic] = useState<Record<string, boolean>>({})
  const [expandedInfringements, setExpandedInfringements] = useState<Record<string, boolean>>({})
  const [onlyInfringements, setOnlyInfringements] = useState(false)
  const [onlyProprietary, setOnlyProprietary] = useState(false)
  const [onlyWithContacts, setOnlyWithContacts] = useState(false)
  const [asicStatusFilter, setAsicStatusFilter] = useState("all")
  const [contactFetches, setContactFetches] = useState<Record<string, ContactFetchState>>({})

  // Form state
  const [revenueMin, setRevenueMin] = useState("")
  const [revenueMax, setRevenueMax] = useState("")
  const [companyName, setCompanyName] = useState("")

  const [tier1Sort, setTier1Sort] = useState<SortState>({ key: "revenue", dir: "desc" })
  const [tier1Page, setTier1Page] = useState(1)
  const [tier2Sort, setTier2Sort] = useState<SortState>({ key: "revenue", dir: "desc" })
  const [tier2Page, setTier2Page] = useState(1)
  const [searchedMax, setSearchedMax] = useState<string>("")

  const resetResultState = () => {
    setError("")
    setResults(null)
    setValidationStatuses({})
    setContactFetches({})
    setExpandedInfringements({})
    setOnlyInfringements(false)
    setOnlyProprietary(false)
    setOnlyWithContacts(false)
    setAsicStatusFilter("all")
    setTier1Page(1)
    setTier2Page(1)
  }

  const ingestResults = (data: UnlistedSearchResult) => {
    setResults(data)
    const allCompanies = [...(data.tier1 || []), ...(data.tier2 || [])]

    const initialContactFetches: Record<string, ContactFetchState> = {}
    allCompanies.forEach((c: UnlistedCompany) => {
      if (c.prefetched_contact_fetch) {
        initialContactFetches[c.id] = c.prefetched_contact_fetch
      }
    })
    if (Object.keys(initialContactFetches).length > 0) {
      setContactFetches(initialContactFetches)
    }

    // The backend joins every result against the ASIC register server-side
    // and embeds it as company.asic — seed the badges from that. The
    // per-company /validate fetch survives only as a fallback for results
    // that arrived without a join (e.g. register index still building).
    const seededValidation: Record<string, AsicValidation> = {}
    allCompanies.forEach((c: UnlistedCompany) => {
      if (c.asic) seededValidation[c.id] = c.asic as AsicValidation
    })
    if (Object.keys(seededValidation).length > 0) {
      setValidationStatuses(seededValidation)
    }
    allCompanies.filter((c: UnlistedCompany) => !c.asic).forEach(async (company: UnlistedCompany) => {
      try {
        const vRes = await fetch(`${API_BASE}/api/unlisted/validate/${company.id}?name=${encodeURIComponent(company.name)}`)
        if (vRes.ok) {
          const vData = await vRes.json()
          setValidationStatuses(prev => ({
            ...prev,
            [company.id]: vData
          }))
        }
      } catch (e) {
        console.error("Validation error", e)
      }
    })
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    resetResultState()
    setSearchedMax(revenueMax)

    try {
      const payload: any = { 
        locations: ["Australia"],
        onlyProprietary,
        onlyInfringements,
        onlyWithContacts,
        asicStatusFilter
      }
      if (revenueMin) payload.revenueMin = Number(revenueMin)
      if (revenueMax) payload.revenueMax = Number(revenueMax)
      if (companyName.trim()) payload.companyName = companyName.trim()

      const res = await fetch(`${API_BASE}/api/unlisted/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Search failed")
      }

      ingestResults(await res.json())
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const loadAsicProspects = async () => {
    setLoading(true)
    resetResultState()
    setSearchedMax("") // Tier 1 is always reachable for this list

    try {
      const res = await fetch(`${API_BASE}/api/unlisted/asic-prospects`)
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || "Couldn't load ASIC prospects")
      }
      ingestResults(await res.json())
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const formatRecency = (fetchedAt?: number) => {
    if (!fetchedAt) return null
    const ageMs = Date.now() - fetchedAt * 1000
    const mins = Math.round(ageMs / 60000)
    if (mins < 1) return "just now"
    if (mins < 60) return `${mins} min ago`
    const hours = Math.round(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return new Date(fetchedAt * 1000).toLocaleString()
  }

  const SortableTh = ({ label, sortKey, sort, onSort, className }: {
    label: string
    sortKey: SortKey
    sort: SortState
    onSort: (key: SortKey) => void
    className?: string
  }) => {
    const active = sort.key === sortKey
    return (
      <th className={`p-4 select-none ${className ?? ""}`}>
        <button
          type="button"
          onClick={() => onSort(sortKey)}
          className="flex items-center gap-1 hover:text-foreground"
        >
          {label}
          {active ? (
            sort.dir === "asc" ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronsUpDown className="h-3.5 w-3.5 opacity-40" />
          )}
        </button>
      </th>
    )
  }

  const makeSortHandler = (setSort: React.Dispatch<React.SetStateAction<SortState>>, setPage: React.Dispatch<React.SetStateAction<number>>) =>
    (key: SortKey) => {
      setSort(prev => prev.key === key ? { key, dir: prev.dir === "asc" ? "desc" : "asc" } : { key, dir: key === "name" ? "asc" : "desc" })
      setPage(1)
    }

  const PaginationFooter = ({ page, setPage, total }: { page: number, setPage: (p: number) => void, total: number }) => {
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
    if (totalPages <= 1) return null
    return (
      <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50 text-sm text-muted-foreground">
        <span>Page {page} of {totalPages} &middot; {total} companies</span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</Button>
        </div>
      </div>
    )
  }

  // Every company in this tool currently comes from Apollo — there is no
  // live LinkedIn or web scraper. This used to branch on 'linkedin' / 'web'
  // values that nothing ever actually set (dead code left over from an
  // earlier design), so it's been removed rather than kept as a decoration
  // that implies capabilities that don't exist.
  const renderSourceIcon = (dataSource?: string) =>
    dataSource === "rocketreach" ? (
      <div title="Company discovered via RocketReach" className="inline-flex items-center justify-center p-1 bg-teal-50 text-teal-700 rounded-full mr-2">
        <Telescope className="h-3 w-3" />
      </div>
    ) : dataSource === "asic" ? (
      <div title="Company discovered from ASIC's own registers (infringement notices)" className="inline-flex items-center justify-center p-1 bg-violet-50 text-violet-700 rounded-full mr-2">
        <Landmark className="h-3 w-3" />
      </div>
    ) : (
      <div title="Company data from Apollo" className="inline-flex items-center justify-center p-1 bg-indigo-50 text-indigo-600 rounded-full mr-2">
        <Rocket className="h-3 w-3" />
      </div>
    )

  const renderAsicIcon = (status?: string) =>
    status === 'verified' ? (
      <div title="Independently confirmed active on ASIC's company register" className="inline-flex items-center justify-center p-1 bg-violet-50 text-violet-700 rounded-full mr-1">
        <Landmark className="h-3 w-3" />
      </div>
    ) : null

  const renderInfringementIcon = (count: number) =>
    count > 0 ? (
      <div title={`Sourced from ASIC's Infringement Notices Register — ${count} notice${count > 1 ? "s" : ""} on file`} className="inline-flex items-center justify-center p-1 bg-red-50 text-red-600 rounded-full mr-1">
        <ShieldAlert className="h-3 w-3" />
      </div>
    ) : null

  const renderRocketReachIcon = () => (
    <div title="Contact data sourced from RocketReach" className="inline-flex items-center justify-center p-1 bg-teal-50 text-teal-700 rounded-full mr-1">
      <Telescope className="h-3 w-3" />
    </div>
  )

  // Small per-contact source markers: Apollo rocket, RocketReach telescope,
  // or both for a merged record (e.g. name from Apollo, email filled by
  // RocketReach). Contacts saved before source-tagging existed default to
  // Apollo — everything predating RocketReach came from there.
  const renderContactSourceIcons = (source?: string) => {
    const s = source || "apollo"
    return (
      <span className="inline-flex items-center gap-0.5 ml-1.5 align-middle">
        {s.includes("apollo") && (
          <Rocket className="h-3 w-3 text-indigo-500" aria-label="Sourced from Apollo" />
        )}
        {s.includes("rocketreach") && (
          <Telescope className="h-3 w-3 text-teal-600" aria-label="Sourced from RocketReach" />
        )}
      </span>
    )
  }

  const renderValidationBadge = (status?: string) => {
    switch (status) {
      case 'verified':
        return <span className="text-green-600 flex items-center gap-1 text-xs" title="Active on ASIC company register"><CheckCircle2 className="h-4 w-4"/> ASIC verified</span>
      case 'deregistered':
        return <span className="text-red-600 flex items-center gap-1 text-xs" title="Found on ASIC register but not active"><AlertCircle className="h-4 w-4"/> Deregistered</span>
      case 'not_found':
        return <span className="text-amber-600 flex items-center gap-1 text-xs" title="No matching name on the ASIC register"><AlertCircle className="h-4 w-4"/> Not on ASIC register</span>
      case 'pending':
        return <span className="text-gray-400 flex items-center gap-1 text-xs" title="ASIC register index is still building"><AlertCircle className="h-4 w-4"/> Checking&hellip;</span>
      default:
        return <span className="text-amber-600 flex items-center gap-1 text-xs"><AlertCircle className="h-4 w-4"/> Unverified</span>
    }
  }

  const renderConfidenceBadge = () => {
      return <span className="text-gray-500 font-medium text-xs">Estimate only</span>
  }

  const findContacts = async (companyId: string) => {
    setContactFetches(prev => ({ ...prev, [companyId]: { status: "loading" } }))
    try {
      const res = await fetch(`${API_BASE}/api/unlisted/contacts/${companyId}`)
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || "Lookup failed")
      }
      const data = await res.json()
      setContactFetches(prev => ({ ...prev, [companyId]: { status: "done", contacts: data.contacts || [], fetchedAt: data.fetchedAt } }))
    } catch (e: any) {
      setContactFetches(prev => ({ ...prev, [companyId]: { status: "error", error: e.message } }))
    } finally {
      // done
    }
  }

  const renderCompanyRow = (company: UnlistedCompany, tier: number) => {
    const rev = company.organization_revenue || company.annual_revenue || company.estimated_revenue
    const valInfo = validationStatuses[company.id]
    const asicExpanded = !!expandedAsic[company.id]
    const asicDetailFields = valInfo ? ASIC_FIELD_LABELS.filter(([key]) => valInfo[key]) : []
    const hasRocketReachData = (contactFetches[company.id]?.contacts || []).some(
      (c: any) => (c.source || "").includes("rocketreach")
    )

    const employeeDisplay = company.linkedin_employee_count
      ? (
        <span className="flex items-center gap-1">
          {company.employeeCountSource === 'manual_research' && (
            <span className="w-2 h-2 rounded-full bg-blue-500" title="From manual research (Agent-Reach), not a live source"></span>
          )}
          {company.linkedin_employee_count}
        </span>
      )
      : (company.estimated_num_employees || "?")

    return (
      <tr key={company.id} className="border-b last:border-0 hover:bg-gray-50 transition-colors">
        <td className="p-4">
          <div className="font-medium text-gray-900 flex items-center">
            {renderSourceIcon(company.dataSource)}
            {hasRocketReachData && company.dataSource !== "rocketreach" && renderRocketReachIcon()}
            {company.dataSource !== "asic" && renderAsicIcon(valInfo?.status)}
            {renderInfringementIcon(company.infringementNotices?.length || 0)}
            {company.name}
          </div>
          <div className="text-sm text-gray-500">
            <a href={`https://${company.domain}`} target="_blank" rel="noreferrer" className="hover:underline">
              {company.domain}
            </a>
          </div>
        </td>
        <td className="p-4 text-gray-700">
          {rev ? `$${rev.toLocaleString()}` : company.revenueBand ? (
            <span title="RocketReach has no point estimate — the company matched this revenue band in the search filter">{company.revenueBand}</span>
          ) : 'Unknown'}
        </td>
        <td className="p-4 text-gray-700">
          {employeeDisplay}
        </td>
        <td className="p-4">
          <div>
            {tier === 1 ? renderValidationBadge(valInfo?.status) : renderConfidenceBadge()}
            {tier === 2 && valInfo && (
              <div className="mt-1">{renderValidationBadge(valInfo.status)}</div>
            )}
            {asicDetailFields.length > 0 && (
              <>
                <button
                  type="button"
                  className="text-xs text-muted-foreground hover:underline mt-1"
                  onClick={() => setExpandedAsic(prev => ({ ...prev, [company.id]: !prev[company.id] }))}
                >
                  {asicExpanded ? "Hide ASIC details" : "Show ASIC details"}
                </button>
                {asicExpanded && (
                  <div className="mt-2 border-t pt-2 space-y-3">
                    <dl className="text-xs space-y-1">
                      {asicDetailFields.map(([key, label]) => (
                        <div key={key} className="flex justify-between gap-3">
                          <dt className="text-muted-foreground">{label}</dt>
                          <dd className="text-gray-900 text-right">{valInfo![key]}</dd>
                        </div>
                      ))}
                    </dl>
                    {(valInfo?.acn || valInfo?.abn) && (
                      <a
                        href={`https://connectonline.asic.gov.au/RegistrySearch/faces/landing/bySearchId.jspx?searchId=${valInfo.acn || valInfo.abn}&searchIdType=${valInfo.acn ? 'ACN' : 'ABN'}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center justify-center gap-1.5 w-full text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 px-3 py-1.5 rounded transition-colors"
                        title="Click to search ASIC Connect for this ACN. Look for '388' in the document list to confirm Large Proprietary status."
                      >
                        <ExternalLink className="h-3 w-3" /> Check for Form 388
                      </a>
                    )}
                  </div>
                )}
              </>
            )}
            {company.infringementNotices && company.infringementNotices.length > 0 && (
              <>
                <button
                  type="button"
                  className="text-xs text-red-600 hover:underline mt-1 block"
                  onClick={() => setExpandedInfringements(prev => ({ ...prev, [company.id]: !prev[company.id] }))}
                >
                  {expandedInfringements[company.id] ? "Hide" : "Show"} {company.infringementNotices.length} infringement notice{company.infringementNotices.length > 1 ? "s" : ""}
                </button>
                {expandedInfringements[company.id] && (
                  <div className="mt-2 text-xs space-y-2 border-t pt-2">
                    {company.infringementNotices.map((n, i) => (
                      <div key={i} className="space-y-0.5">
                        <div className="flex justify-between gap-3">
                          <span className="text-muted-foreground">Date Paid</span>
                          <span className="text-gray-900">{n.datePaid}</span>
                        </div>
                        <div className="flex justify-between gap-3">
                          <span className="text-muted-foreground">Legislation</span>
                          <span className="text-gray-900 text-right">{n.legislation}</span>
                        </div>
                        <div className="flex gap-3">
                          {n.noticePdfUrl && (
                            <a href={n.noticePdfUrl} target="_blank" rel="noreferrer" className="text-accent hover:underline">Notice {n.noticeId}</a>
                          )}
                          {n.mediaReleaseUrl && (
                            <a href={n.mediaReleaseUrl} target="_blank" rel="noreferrer" className="text-accent hover:underline">{n.mediaReleaseId}</a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </td>
        <td className="p-4">
          {company.contacts && company.contacts.length > 0 && !contactFetches[company.id] ? (
            <div className="flex flex-col gap-1">
              {company.contacts.map((c, i) => (
                <div key={i} className="text-sm">
                  <span className="font-medium text-gray-900">{c.name}</span>
                  <span className="text-gray-500 ml-2">{c.title}</span>
                </div>
              ))}
              <Button
                size="sm"
                variant="outline"
                className="mt-2 w-max text-xs h-7"
                onClick={() => findContacts(company.id)}
              >
                Find Details
              </Button>
            </div>
          ) : (() => {
            const fetchState = contactFetches[company.id]
            if (fetchState?.status === "loading") {
              return <span className="text-xs text-muted-foreground">Searching Apollo&hellip;</span>
            }
            if (fetchState?.status === "error") {
              return (
                <div>
                  {fetchState.error && <p className="text-xs text-red-600 mb-1">{fetchState.error}</p>}
                  <Button size="sm" variant="outline" onClick={() => findContacts(company.id)}>Retry</Button>
                </div>
              )
            }
            if (fetchState?.status === "done") {
              if (!fetchState.contacts || fetchState.contacts.length === 0) {
                return <span className="text-sm text-gray-400">No CEO/CFO found</span>
              }
              return (
                <>
                  <div className="flex flex-col gap-1">
                    {fetchState.contacts.map((c, i) => (
                      <div key={i} className="text-sm">
                        <span className="font-medium text-gray-900">{c.name}</span>
                        {renderContactSourceIcons(c.source)}
                        <span className="text-gray-500 ml-2">{c.title}</span>
                        {c.email && (
                          <div className="text-xs text-gray-500">
                            <a href={`mailto:${c.email}`} className="hover:underline">{c.email}</a>
                            {c.emailStatus === "verified" && <CheckCircle2 className="inline h-3 w-3 ml-1 text-green-600" />}
                          </div>
                        )}
                        {c.phoneNumbers && c.phoneNumbers.length > 0 && (
                          <div className="text-xs text-gray-500 mt-0.5">
                            {c.phoneNumbers.map((phone: string, idx: number) => (
                              <span key={idx} className="block">{phone}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  {fetchState.fetchedAt && (
                    <div className="mt-2 text-[10px] text-muted-foreground italic">
                      Acquired {formatRecency(fetchState.fetchedAt)}
                    </div>
                  )}
                </>
              )
          }
            return (
              <Button
                size="sm"
                variant="outline"
                onClick={() => findContacts(company.id)}
                title="Spends real Apollo credits to reveal a verified email — only use for companies you're actually pursuing"
              >
                Find Contacts
              </Button>
            )
          })()}
        </td>
      </tr>
    )
  }

  const applyFilters = (list: UnlistedCompany[]) => {
    return list.filter(c => {
      if (onlyInfringements && !(c.infringementNotices?.length && c.infringementNotices.length > 0)) return false
      
      if (onlyWithContacts) {
        const hasFetched = contactFetches[c.id]?.contacts && contactFetches[c.id]!.contacts!.length > 0
        const hasLegacy = c.contacts && c.contacts.length > 0
        if (!hasLegacy && !hasFetched) return false
      }
      
      const v = validationStatuses[c.id]
      if (onlyProprietary) {
        if (!v || v.asicType !== "APTY" || v.asicClass !== "LMSH" || v.asicSubClass !== "PROP") return false
      }
      
      if (asicStatusFilter !== "all") {
        if (!v) {
          if (asicStatusFilter !== "pending") return false
        } else {
          if (v.status !== asicStatusFilter) return false
        }
      }
      
      return true
    })
  }

  const tier1Sorted = useMemo(
    () => results ? sortCompanies(applyFilters(results.tier1), tier1Sort) : [],
    [results, tier1Sort, onlyInfringements, onlyProprietary, onlyWithContacts, asicStatusFilter, validationStatuses, contactFetches]
  )
  const tier1PageItems = useMemo(
    () => tier1Sorted.slice((tier1Page - 1) * PAGE_SIZE, tier1Page * PAGE_SIZE),
    [tier1Sorted, tier1Page]
  )
  const tier2Sorted = useMemo(
    () => results ? sortCompanies(applyFilters(results.tier2), tier2Sort) : [],
    [results, tier2Sort, onlyInfringements, onlyProprietary, onlyWithContacts, asicStatusFilter, validationStatuses, contactFetches]
  )
  const tier2PageItems = useMemo(
    () => tier2Sorted.slice((tier2Page - 1) * PAGE_SIZE, tier2Page * PAGE_SIZE),
    [tier2Sorted, tier2Page]
  )
  const onSortTier1 = makeSortHandler(setTier1Sort, setTier1Page)
  const onSortTier2 = makeSortHandler(setTier2Sort, setTier2Page)

  const t1Min = results?.thresholds?.t1Min ?? 50000000
  // Tier 1 requires revenue >= t1Min. If the searched Revenue Max is below
  // that, Tier 1 can never have results — show why instead of an empty table.
  const t1Reachable = !searchedMax || Number(searchedMax) >= t1Min

  return (
    <div className="container mx-auto p-4 space-y-8 max-w-5xl py-8">
      <div>
        <h1 className="text-3xl font-heading font-semibold text-navy-deep">Unlisted Companies</h1>
        <p className="text-muted-foreground mt-2">Find large Australian proprietary companies as GP business-development prospects.</p>
      </div>

      <div className="mb-4">
        <StatusPage />
      </div>

      <div className="bg-card border rounded-md p-6">
        <form onSubmit={handleSearch} className="flex items-end gap-4">
          <div className="flex-1">
            <label className="text-sm font-medium mb-1 block">Company Name</label>
            <input
              type="text"
              className="w-full border rounded px-3 py-2 text-sm bg-background text-foreground"
              value={companyName}
              onChange={e => setCompanyName(e.target.value)}
              placeholder="e.g. Canva (optional)"
            />
          </div>
          <div className="flex-1">
            <label className="text-sm font-medium mb-1 block">Revenue Min (AUD)</label>
            <input 
              type="number" 
              className="w-full border rounded px-3 py-2 text-sm bg-background text-foreground"
              value={revenueMin}
              onChange={e => setRevenueMin(e.target.value)}
              placeholder="e.g. 20000000"
            />
          </div>
          <div className="flex-1">
            <label className="text-sm font-medium mb-1 block">Revenue Max (AUD)</label>
            <input 
              type="number" 
              className="w-full border rounded px-3 py-2 text-sm bg-background text-foreground"
              value={revenueMax}
              onChange={e => setRevenueMax(e.target.value)}
              placeholder="Leave empty for no max"
            />
          </div>
          <div className="flex-1">
            <label className="text-sm font-medium mb-1 block">Location</label>
            <input 
              type="text" 
              className="w-full border rounded px-3 py-2 text-sm bg-muted text-muted-foreground"
              value="Australia"
              disabled
            />
          </div>
          <Button type="submit" disabled={loading} className="w-32">
            {loading ? "Searching..." : "Search"}
          </Button>
        </form>
        <div className="mt-3 flex items-center justify-between gap-4 flex-wrap">
          <p className="text-xs text-muted-foreground">
            Tip: set a Revenue Max, not just a Min. This API is rate-limited to 200 calls/hour — a search with no
            upper bound has to page through far more results and burns through that limit much faster than a
            narrow band does.
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={loading}
            onClick={loadAsicProspects}
            title="Start from ASIC's own signals: every company on the infringement notices register had a financial-report lodgement obligation, making it a large proprietary company by legal definition"
          >
            <Landmark className="h-3.5 w-3.5 mr-1.5" /> ASIC-first prospects
          </Button>
        </div>
        {results && (
          <div className="mt-4 flex flex-wrap items-center gap-6 p-4 bg-muted/20 border rounded-md">
            <label 
              className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer"
              title="APTY = Australian Proprietary Company&#10;LMSH = Limited by Shares&#10;PROP = Proprietary"
            >
              <input
                type="checkbox"
                checked={onlyProprietary}
                onChange={e => {
                  setOnlyProprietary(e.target.checked)
                  setTier1Page(1)
                  setTier2Page(1)
                }}
                className="rounded border-gray-300"
              />
              Large Proprietary (APTY / LMSH / PROP)
            </label>

            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={onlyWithContacts}
                onChange={e => {
                  setOnlyWithContacts(e.target.checked)
                  setTier1Page(1)
                  setTier2Page(1)
                }}
                className="rounded border-gray-300"
              />
              Has known contacts
            </label>

            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-700 font-medium">ASIC Status:</label>
              <select
                className="border rounded px-2 py-1 text-sm bg-white"
                value={asicStatusFilter}
                onChange={e => {
                  setAsicStatusFilter(e.target.value)
                  setTier1Page(1)
                  setTier2Page(1)
                }}
              >
                <option value="all">All Statuses</option>
                <option value="verified">Verified (Active)</option>
                <option value="deregistered">Deregistered</option>
                <option value="not_found">Not on Register</option>
                <option value="pending">Checking...</option>
              </select>
            </div>

            {(() => {
              const infringedCount = [...results.tier1, ...results.tier2].filter(c => (c.infringementNotices?.length || 0) > 0).length
              if (infringedCount > 0) {
                return (
                  <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={onlyInfringements}
                      onChange={e => {
                        setOnlyInfringements(e.target.checked)
                        setTier1Page(1)
                        setTier2Page(1)
                      }}
                      className="rounded border-gray-300"
                    />
                    Only show companies with ASIC infringement notices ({infringedCount})
                  </label>
                )
              }
              return null
            })()}
          </div>
        )}
        {error && <div className="mt-4 text-destructive text-sm">{error}</div>}
      </div>

      {results && (
        <div className="space-y-8">
          {results.pagination?.discovery_source === "asic" && (
            <div className="bg-violet-50 border border-violet-200 text-violet-900 text-sm rounded-md p-4">
              <strong>ASIC-first seed list — this is the complete register, not a search.</strong> These{" "}
              {results.tier1.length} companies are every entity ASIC has penalised for failing to lodge financial
              reports (2012–present). A lodgement obligation makes each one a large proprietary company by legal
              definition, so they all sit in Tier 1 and there is no Tier 2. The revenue filters above don't apply
              here — use Search for revenue-based discovery.
            </div>
          )}
          {results.pagination?.served_from_local_fallback && (
            <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-md p-4">
              Apollo's API was unavailable (rate limit), so these are companies previously fetched and stored
              locally that match your filters — not a fresh search. Coverage may be incomplete; results may be
              stale as of {formatRecency(results.fetchedAt)}.
            </div>
          )}
          {results.pagination && (
            <div className="text-sm text-muted-foreground">
              <div>
                Found {results.pagination.fetched_entries ?? (results.tier1.length + results.tier2.length)} companies
                {results.pagination.total_entries != null && ` of ${results.pagination.total_entries} matching in Apollo`}
                {results.pagination.discovery_source === "asic" ? (
                  <span className="text-violet-700"> — ASIC-first: companies penalised for failing to lodge financial reports (large proprietary by legal definition)</span>
                ) : results.pagination.discovery_source === "rocketreach" ? (
                  <span className="text-teal-700"> — discovered via RocketReach (Apollo unavailable); revenue shown as the searched band</span>
                ) : results.pagination.served_from_local_fallback ? (
                  <span className="text-amber-600"> — served from local storage, not live Apollo</span>
                ) : results.pagination.rate_limited ? (
                  <span className="text-amber-600"> — stopped early: Apollo's hourly rate limit was hit mid-search. Try a narrower revenue range next time.</span>
                ) : results.pagination.truncated && (
                  <span className="text-amber-600"> — capped at {results.pagination.fetched_pages} pages; narrow revenue range to see more</span>
                )}
              </div>
              {results.fetchedAt && !results.pagination.served_from_local_fallback && (
                <div className="text-xs mt-0.5">
                  Data fetched {formatRecency(results.fetchedAt)}
                  {results.fromCache ? " (cached — served without calling Apollo)" : " (fresh from Apollo)"}
                </div>
              )}
              <div className="text-xs mt-1">
                &rarr; {results.tier1.length} in Tier 1, {results.tier2.length} in Tier 2
                {results.excludedUnderMin.length > 0 && ` · ${results.excludedUnderMin.length} below Revenue Min`}
                {results.excludedOverMax.length > 0 && ` · ${results.excludedOverMax.length} above Revenue Max`}
                {results.excludedIncompleteData.length > 0 && ` · ${results.excludedIncompleteData.length} no revenue/employee data`}
                {(results.excludedNotOnAsic?.length || 0) > 0 && ` · ${results.excludedNotOnAsic!.length} not on ASIC register`}
                {results.excludedAsxMatches.length > 0 && ` · ${results.excludedAsxMatches.length} ASX-listed`}
              </div>
            </div>
          )}

          <div className="bg-blue-50 border border-blue-200 text-blue-900 text-sm rounded-md p-4">
            <strong>Key Contacts costs real money.</strong> Clicking "Find Contacts" on a row spends actual Apollo
            credits to reveal a verified email (up to 2 people per company) — it does not run automatically for
            the whole list. Only click it for companies you've actually decided to pursue. Results are saved for
            30 days, so re-clicking the same company later is free.{" "}
            <a
              href={`${API_BASE}/api/unlisted/export/contacts.csv`}
              className="font-medium underline hover:no-underline"
              download
            >
              Export all saved contacts (HubSpot-ready CSV)
            </a>
          </div>
          {results.excludedAsxMatches && results.excludedAsxMatches.length > 0 && (
            <details className="bg-muted/30 border rounded-md p-4 group">
              <summary className="text-sm font-medium cursor-pointer flex justify-between items-center text-muted-foreground group-open:mb-4">
                {results.excludedAsxMatches.length} candidates excluded as ASX-listed
                <span className="text-xs border px-2 py-0.5 rounded">Expand</span>
              </summary>
              <div className="text-sm text-muted-foreground max-h-48 overflow-y-auto">
                <ul className="list-disc pl-5 space-y-1">
                  {results.excludedAsxMatches.map(c => (
                    <li key={c.id}>{c.name} ({c.domain})</li>
                  ))}
                </ul>
              </div>
            </details>
          )}

          {results.excludedOverMax && results.excludedOverMax.length > 0 && (
            <details className="bg-muted/30 border rounded-md p-4 group">
              <summary className="text-sm font-medium cursor-pointer flex justify-between items-center text-muted-foreground group-open:mb-4">
                {results.excludedOverMax.length} candidates excluded for exceeding Revenue Max
                <span className="text-xs border px-2 py-0.5 rounded">Expand</span>
              </summary>
              <div className="text-sm text-muted-foreground max-h-48 overflow-y-auto">
                <ul className="list-disc pl-5 space-y-1">
                  {results.excludedOverMax.map(c => (
                    <li key={c.id}>{c.name} ({c.domain})</li>
                  ))}
                </ul>
              </div>
            </details>
          )}

          {results.excludedUnderMin && results.excludedUnderMin.length > 0 && (
            <details className="bg-muted/30 border rounded-md p-4 group">
              <summary className="text-sm font-medium cursor-pointer flex justify-between items-center text-muted-foreground group-open:mb-4">
                {results.excludedUnderMin.length} candidates excluded for being below Revenue Min (or the $20M Tier 2 floor)
                <span className="text-xs border px-2 py-0.5 rounded">Expand</span>
              </summary>
              <div className="text-sm text-muted-foreground max-h-48 overflow-y-auto">
                <ul className="list-disc pl-5 space-y-1">
                  {results.excludedUnderMin.map(c => (
                    <li key={c.id}>{c.name} ({c.domain})</li>
                  ))}
                </ul>
              </div>
            </details>
          )}

          {results.excludedIncompleteData && results.excludedIncompleteData.length > 0 && (
            <details className="bg-muted/30 border rounded-md p-4 group">
              <summary className="text-sm font-medium cursor-pointer flex justify-between items-center text-muted-foreground group-open:mb-4">
                {results.excludedIncompleteData.length} candidates excluded for having no revenue or employee data at all
                <span className="text-xs border px-2 py-0.5 rounded">Expand</span>
              </summary>
              <div className="text-sm text-muted-foreground max-h-48 overflow-y-auto">
                <ul className="list-disc pl-5 space-y-1">
                  {results.excludedIncompleteData.map(c => (
                    <li key={c.id}>{c.name} ({c.domain})</li>
                  ))}
                </ul>
              </div>
            </details>
          )}

          {(results.excludedNotOnAsic?.length || 0) > 0 && (
            <details className="bg-muted/30 border rounded-md p-4 group">
              <summary className="text-sm font-medium cursor-pointer flex justify-between items-center text-muted-foreground group-open:mb-4">
                {results.excludedNotOnAsic!.length} candidates excluded — no match on the ASIC company register (foreign entities, brands, or trading names that differ from the legal name)
                <span className="text-xs border px-2 py-0.5 rounded">Expand</span>
              </summary>
              <div className="text-sm text-muted-foreground max-h-48 overflow-y-auto">
                <ul className="list-disc pl-5 space-y-1">
                  {results.excludedNotOnAsic!.map(c => (
                    <li key={c.id}>{c.name} ({c.domain})</li>
                  ))}
                </ul>
              </div>
            </details>
          )}

          <div>
            <h2 className="text-xl font-heading font-medium text-navy-deep mb-4 border-b pb-2">Tier 1 &mdash; $50M+ (ASIC-verifiable)</h2>
            {!t1Reachable ? (
              <div className="border rounded-md bg-muted/30 p-4 text-sm text-muted-foreground">
                Tier 1 requires $50M+ revenue, but your Revenue Max (${Number(searchedMax).toLocaleString()}) rules it out entirely —
                raise Revenue Max above ${t1Min.toLocaleString()} to see Tier 1 candidates.
              </div>
            ) : (
              <div className="border rounded-md overflow-hidden bg-card">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-gray-100 text-gray-600 text-sm font-semibold border-b">
                      <SortableTh label="Company" sortKey="name" sort={tier1Sort} onSort={onSortTier1} className="w-1/4" />
                      <SortableTh label="Est. Revenue" sortKey="revenue" sort={tier1Sort} onSort={onSortTier1} className="w-1/5" />
                      <SortableTh label="Employees" sortKey="employees" sort={tier1Sort} onSort={onSortTier1} className="w-1/5" />
                      <th className="p-4 w-1/5">ASIC Lodgement</th>
                      <th className="p-4 w-1/4">Key Contacts</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tier1PageItems.length > 0 ? (
                      tier1PageItems.map(c => renderCompanyRow(c, 1))
                    ) : (
                      <tr><td colSpan={5} className="py-8 text-center text-muted-foreground">No companies found in this tier.</td></tr>
                    )}
                  </tbody>
                </table>
                <PaginationFooter page={tier1Page} setPage={setTier1Page} total={tier1Sorted.length} />
              </div>
            )}
          </div>

          {results.pagination?.discovery_source !== "asic" && (
          <div>
            <h2 className="text-xl font-heading font-medium text-navy-deep border-b pb-2">Tier 2 &mdash; Unverified leads (est. $20&ndash;50M)</h2>
            <p className="text-xs text-muted-foreground mt-2 mb-4 max-w-3xl">
              Revenue figures here are Apollo estimates, not audited numbers — for private companies they are often
              crude round-number bands (many unrelated companies report exactly $20M). Below the $50M statutory line
              there is no ASIC lodgement to corroborate size, so treat this list as a shortlist to validate, not a
              finished target list.
            </p>
            <div className="border rounded-md overflow-hidden bg-card">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-gray-100 text-gray-600 text-sm font-semibold border-b">
                    <SortableTh label="Company" sortKey="name" sort={tier2Sort} onSort={onSortTier2} className="w-1/4" />
                    <SortableTh label="Est. Revenue" sortKey="revenue" sort={tier2Sort} onSort={onSortTier2} className="w-1/5" />
                    <SortableTh label="Employees" sortKey="employees" sort={tier2Sort} onSort={onSortTier2} className="w-1/5" />
                    <th className="p-4 w-1/5">Confidence</th>
                    <th className="p-4 w-1/4">Key Contacts</th>
                  </tr>
                </thead>
                <tbody>
                  {tier2PageItems.length > 0 ? (
                    tier2PageItems.map(c => renderCompanyRow(c, 2))
                  ) : (
                    <tr><td colSpan={4} className="py-8 text-center text-muted-foreground">No companies found in this tier.</td></tr>
                  )}
                </tbody>
              </table>
              <PaginationFooter page={tier2Page} setPage={setTier2Page} total={tier2Sorted.length} />
            </div>
          </div>
          )}
        </div>
      )}
    </div>
  )
}
