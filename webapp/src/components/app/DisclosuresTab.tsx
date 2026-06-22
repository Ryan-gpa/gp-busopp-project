import { useState, useMemo } from "react"
import { StatusChip } from "./StatusChip"
import { renderStatus, RENDER_STATUS_ORDER, type FindingsJSON, type RenderStatus } from "@/types"

interface Props {
  findings: FindingsJSON
}

const MATERIALITY_LABELS = { high: "High", medium: "Medium", low: "Low" }

export function DisclosuresTab({ findings }: Props) {
  const [statusFilter, setStatusFilter] = useState<RenderStatus | "all">("all")
  const [standardFilter, setStandardFilter] = useState("")
  const [matFilter, setMatFilter] = useState<"all" | "high" | "medium" | "low">("all")
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const rows = useMemo(() => {
    const sorted = [...findings.results].sort((a, b) => {
      const ai = RENDER_STATUS_ORDER.indexOf(renderStatus(a))
      const bi = RENDER_STATUS_ORDER.indexOf(renderStatus(b))
      return ai - bi
    })
    return sorted.filter((item) => {
      const rs = renderStatus(item)
      if (statusFilter !== "all" && rs !== statusFilter) return false
      if (standardFilter && !item.standard.toLowerCase().includes(standardFilter.toLowerCase()) &&
          !item.title.toLowerCase().includes(standardFilter.toLowerCase())) return false
      if (matFilter !== "all" && item.materiality !== matFilter) return false
      return true
    })
  }, [findings.results, statusFilter, standardFilter, matFilter])

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Status</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as RenderStatus | "all")}
            className="h-8 px-2 text-xs border border-input rounded-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="all">All statuses</option>
            {RENDER_STATUS_ORDER.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Standard / keyword</label>
          <input
            type="text"
            value={standardFilter}
            onChange={(e) => setStandardFilter(e.target.value)}
            placeholder="e.g. AASB 15"
            className="h-8 px-2 text-xs border border-input rounded-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring w-36"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Materiality level</label>
          <select
            value={matFilter}
            onChange={(e) => setMatFilter(e.target.value as typeof matFilter)}
            className="h-8 px-2 text-xs border border-input rounded-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="all">All levels</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
        <span className="text-xs text-muted-foreground self-end pb-1">{rows.length} item{rows.length !== 1 ? "s" : ""}</span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-sm border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[hsl(var(--navy-deep))] text-primary-foreground">
              <th className="text-left px-4 py-2.5 font-medium text-xs w-44">Standard</th>
              <th className="text-left px-4 py-2.5 font-medium text-xs w-36">Clause</th>
              <th className="text-left px-4 py-2.5 font-medium text-xs">Disclosure</th>
              <th className="text-left px-4 py-2.5 font-medium text-xs w-44">Status</th>
              <th className="text-left px-4 py-2.5 font-medium text-xs w-8">Sig.</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((item) => {
              const rs = renderStatus(item)
              const isExpanded = expandedId === item.id
              return (
                <tr
                  key={item.id}
                  className="hover:bg-muted/40 cursor-pointer"
                  onClick={() => setExpandedId(isExpanded ? null : item.id)}
                >
                  <td className="px-4 py-3 text-xs text-muted-foreground align-top">{item.standard}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground align-top font-mono">{item.clause?.replace(/¶/g, "")}</td>
                  <td className="px-4 py-3 align-top">
                    <p className="font-medium text-xs">{item.title}</p>
                    {isExpanded && (
                      <div className="mt-2 space-y-1.5">
                        {item.recommendation && (
                          <p className="text-xs text-muted-foreground">{item.recommendation}</p>
                        )}
                        {item.representationNote && (
                          <p className="text-xs text-accent italic">Note: {item.representationNote}</p>
                        )}
                        {item.balance !== null && (
                          <p className="text-xs text-muted-foreground">Balance: ${item.balance?.toLocaleString()}</p>
                        )}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 align-top">
                    <StatusChip status={rs} />
                  </td>
                  <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                    {MATERIALITY_LABELS[item.materiality as keyof typeof MATERIALITY_LABELS] ?? item.materiality}
                  </td>
                </tr>
              )
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground text-sm">
                  No items match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
