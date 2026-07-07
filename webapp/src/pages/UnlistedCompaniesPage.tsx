import { useState } from "react"
import { Button } from "@/components/ui/button"
import { StatusChip } from "@/components/app/StatusChip"
import type { UnlistedSearchResult, UnlistedCompany } from "@/types"

const API_BASE = import.meta.env.VITE_API_URL || ""

export default function UnlistedCompaniesPage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [results, setResults] = useState<UnlistedSearchResult | null>(null)
  const [validationStatuses, setValidationStatuses] = useState<Record<string, { status: string, reason: string }>>({})

  // Form state
  const [revenueMin, setRevenueMin] = useState("20000000")
  const [revenueMax, setRevenueMax] = useState("")

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError("")
    setResults(null)
    setValidationStatuses({})

    try {
      const payload: any = { locations: ["Australia"] }
      if (revenueMin) payload.revenueMin = Number(revenueMin)
      if (revenueMax) payload.revenueMax = Number(revenueMax)

      const res = await fetch(`${API_BASE}/api/unlisted/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Search failed")
      }

      const data = await res.json()
      setResults(data)

      // Automatically try to validate Tier 1 (stub hits)
      if (data.tier1) {
        data.tier1.forEach(async (company: UnlistedCompany) => {
          try {
            const vRes = await fetch(`${API_BASE}/api/unlisted/validate/${company.id}`)
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
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const formatRevenue = (rev?: number) => {
    if (!rev) return "Unknown"
    return new Intl.NumberFormat("en-AU", {
      style: "currency",
      currency: "AUD",
      maximumFractionDigits: 0
    }).format(rev)
  }

  const renderCompanyRow = (company: UnlistedCompany, tier: number) => {
    const rev = company.organization_revenue || company.annual_revenue || company.estimated_revenue
    const valInfo = validationStatuses[company.id]
    
    // Show LinkedIn verified employees if available, otherwise fallback to estimate
    const employees = company.linkedin_employee_count 
      ? <span className="flex items-center justify-end gap-1"><span className="w-2 h-2 rounded-full bg-blue-500 mr-1" title="Verified by LinkedIn"></span>{company.linkedin_employee_count}</span>
      : company.estimated_num_employees || "?"

    return (
      <tr key={company.id} className="border-b last:border-0 hover:bg-muted/50">
        <td className="py-3 px-4">
          <div className="font-medium text-navy-deep">{company.name}</div>
          <div className="text-xs text-muted-foreground">{company.domain}</div>
        </td>
        <td className="py-3 px-4 text-right tabular-nums">{formatRevenue(rev)}</td>
        <td className="py-3 px-4 text-right tabular-nums">{employees}</td>
        <td className="py-3 px-4">
          {tier === 1 ? (
            valInfo ? (
              <StatusChip status="Unverified" />
            ) : (
              <span className="text-xs text-muted-foreground">Checking...</span>
            )
          ) : (
            <span className="text-xs text-muted-foreground">Estimate only</span>
          )}
        </td>
      </tr>
    )
  }

  return (
    <div className="container mx-auto p-4 space-y-8 max-w-5xl py-8">
      <div>
        <h1 className="text-3xl font-heading font-semibold text-navy-deep">Unlisted Companies</h1>
        <p className="text-muted-foreground mt-2">Find large Australian proprietary companies as GP business-development prospects.</p>
      </div>

      <div className="bg-card border rounded-md p-6">
        <form onSubmit={handleSearch} className="flex items-end gap-4">
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
        {error && <div className="mt-4 text-destructive text-sm">{error}</div>}
      </div>

      {results && (
        <div className="space-y-8">
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

          <div>
            <h2 className="text-xl font-heading font-medium text-navy-deep mb-4 border-b pb-2">Tier 1 &mdash; $50M+ (ASIC-verifiable)</h2>
            <div className="border rounded-md overflow-hidden bg-card">
              <table className="w-full text-sm text-left">
                <thead className="bg-muted text-muted-foreground font-medium border-b">
                  <tr>
                    <th className="py-2 px-4 font-medium">Company</th>
                    <th className="py-2 px-4 font-medium text-right">Est. Revenue</th>
                    <th className="py-2 px-4 font-medium text-right">Employees</th>
                    <th className="py-2 px-4 font-medium">ASIC Lodgement</th>
                  </tr>
                </thead>
                <tbody>
                  {results.tier1.length > 0 ? (
                    results.tier1.map(c => renderCompanyRow(c, 1))
                  ) : (
                    <tr><td colSpan={4} className="py-8 text-center text-muted-foreground">No companies found in this tier.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h2 className="text-xl font-heading font-medium text-navy-deep mb-4 border-b pb-2">Tier 2 &mdash; $20-50M (estimate only)</h2>
            <div className="border rounded-md overflow-hidden bg-card">
              <table className="w-full text-sm text-left">
                <thead className="bg-muted text-muted-foreground font-medium border-b">
                  <tr>
                    <th className="py-2 px-4 font-medium">Company</th>
                    <th className="py-2 px-4 font-medium text-right">Est. Revenue</th>
                    <th className="py-2 px-4 font-medium text-right">Employees</th>
                    <th className="py-2 px-4 font-medium">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {results.tier2.length > 0 ? (
                    results.tier2.map(c => renderCompanyRow(c, 2))
                  ) : (
                    <tr><td colSpan={4} className="py-8 text-center text-muted-foreground">No companies found in this tier.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
