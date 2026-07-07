import { useState } from "react"
import { Button } from "@/components/ui/button"
import { CheckCircle2, AlertCircle, Rocket, Globe } from "lucide-react"
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

  const renderSourceIcon = (source?: string) => {
    switch (source) {
      case 'apollo':
        return <div title="Data from Apollo" className="inline-flex items-center justify-center p-1 bg-indigo-50 text-indigo-600 rounded-full mr-2"><Rocket className="h-3 w-3" /></div>
      case 'linkedin':
        return <div title="Data from LinkedIn" className="inline-flex items-center justify-center p-1 bg-blue-50 text-blue-600 rounded-full mr-2"><Globe className="h-3 w-3" /></div>
      case 'web':
        return <div title="Data from Web" className="inline-flex items-center justify-center p-1 bg-green-50 text-green-600 rounded-full mr-2"><Globe className="h-3 w-3" /></div>
      default:
        return <div title="Data from Apollo" className="inline-flex items-center justify-center p-1 bg-indigo-50 text-indigo-600 rounded-full mr-2"><Rocket className="h-3 w-3" /></div>
    }
  }

  const renderValidationBadge = (status?: string) => {
      return status === 'verified' ? <span className="text-green-600 flex items-center gap-1 text-xs"><CheckCircle2 className="h-4 w-4"/> Verified</span> : <span className="text-amber-600 flex items-center gap-1 text-xs"><AlertCircle className="h-4 w-4"/> Unverified</span>
  }

  const renderConfidenceBadge = () => {
      return <span className="text-gray-500 font-medium text-xs">Estimate only</span>
  }

  const renderCompanyRow = (company: UnlistedCompany, tier: number) => {
    const rev = company.organization_revenue || company.annual_revenue || company.estimated_revenue
    const valInfo = validationStatuses[company.id]
    
    const employeeDisplay = company.linkedin_employee_count 
      ? <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" title="Verified by LinkedIn"></span>{company.linkedin_employee_count}</span>
      : (company.estimated_num_employees || "?")

    return (
      <tr key={company.id} className="border-b last:border-0 hover:bg-gray-50 transition-colors">
        <td className="p-4">
          <div className="font-medium text-gray-900 flex items-center">
            {renderSourceIcon(company.dataSource)}
            {company.name}
          </div>
          <div className="text-sm text-gray-500">
            <a href={`https://${company.domain}`} target="_blank" rel="noreferrer" className="hover:underline">
              {company.domain}
            </a>
          </div>
        </td>
        <td className="p-4 text-gray-700">
          {rev ? `$${rev.toLocaleString()}` : 'Unknown'}
        </td>
        <td className="p-4 text-gray-700">
          {employeeDisplay}
        </td>
        <td className="p-4">
          {tier === 1 ? renderValidationBadge(valInfo?.status) : renderConfidenceBadge()}
        </td>
        <td className="p-4">
          {company.contacts && company.contacts.length > 0 ? (
            <div className="flex flex-col gap-1">
              {company.contacts.map((c, i) => (
                <div key={i} className="text-sm">
                  <span className="font-medium text-gray-900">{c.name}</span>
                  <span className="text-gray-500 ml-2">{c.title}</span>
                </div>
              ))}
            </div>
          ) : (
            <span className="text-sm text-gray-400">N/A</span>
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
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-gray-100 text-gray-600 text-sm font-semibold border-b">
                    <th className="p-4 w-1/4">Company</th>
                    <th className="p-4 w-1/5">Est. Revenue</th>
                    <th className="p-4 w-1/5">Employees</th>
                    <th className="p-4 w-1/5">ASIC Lodgement</th>
                    <th className="p-4 w-1/4">Key Contacts</th>
                  </tr>
                </thead>
                <tbody>
                  {results.tier1.length > 0 ? (
                    results.tier1.map(c => renderCompanyRow(c, 1))
                  ) : (
                    <tr><td colSpan={5} className="py-8 text-center text-muted-foreground">No companies found in this tier.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h2 className="text-xl font-heading font-medium text-navy-deep mb-4 border-b pb-2">Tier 2 &mdash; $20-50M (estimate only)</h2>
            <div className="border rounded-md overflow-hidden bg-card">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-gray-100 text-gray-600 text-sm font-semibold border-b">
                    <th className="p-4 w-1/4">Company</th>
                    <th className="p-4 w-1/5">Est. Revenue</th>
                    <th className="p-4 w-1/5">Employees</th>
                    <th className="p-4 w-1/5">Confidence</th>
                    <th className="p-4 w-1/4">Key Contacts</th>
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
