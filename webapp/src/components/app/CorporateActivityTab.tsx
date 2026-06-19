import { useState, useMemo } from "react"
import { formatDate, type FindingsJSON, type AsxItem } from "@/types"
import { ExternalLink, Settings } from "lucide-react"

interface Props {
  findings: FindingsJSON
  selectedKeys: Set<string>
  onToggleKey: (key: string) => void
  onSelectAll: () => void
  onDeselectAll: () => void
  onOpenConfig: () => void
  onSelectAnnouncement: (item: AsxItem) => void
}

const IMPORTANCE_CLASSES: Record<string, string> = {
  High:   "bg-primary text-primary-foreground",
  Medium: "bg-secondary text-secondary-foreground",
  Low:    "bg-muted text-muted-foreground",
  None:   "bg-muted text-muted-foreground",
}

export function CorporateActivityTab({ findings, selectedKeys, onToggleKey, onSelectAll, onDeselectAll, onOpenConfig, onSelectAnnouncement }: Props) {
  const { asx } = findings
  const [priceSensOnly, setPriceSensOnly] = useState(false)
  const [sigFilter, setSigFilter] = useState<string>("all")

  const periodStart = asx.periodStart
    ? new Date(asx.periodStart).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" })
    : ""
  const periodEnd = asx.periodEnd
    ? new Date(asx.periodEnd).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" })
    : ""

  const rows = useMemo(() => {
    return asx.items.filter((item) => {
      if (priceSensOnly && !item.priceSensitive) return false
      if (sigFilter !== "all" && item.importance !== sigFilter) return false
      return true
    })
  }, [asx.items, priceSensOnly, sigFilter])

  const allVisibleKeys = rows.map(i => i.documentKey).filter(Boolean) as string[]
  const allVisibleSelected = allVisibleKeys.length > 0 && allVisibleKeys.every(k => selectedKeys.has(k))
  const someVisibleSelected = allVisibleKeys.some(k => selectedKeys.has(k))

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="text-sm text-muted-foreground">
        <span className="font-medium text-foreground">{asx.count}</span> announcements between {periodStart} and {periodEnd}
        {" · "}
        <span className="font-medium text-foreground">{asx.priceSensitive}</span> market-sensitive
        {" · "}
        <span className="font-medium text-foreground">{selectedKeys.size}</span> selected for report
      </div>

      {/* Filters + select controls */}
      <div className="flex flex-wrap gap-3 items-end justify-between">
        <div className="flex flex-wrap gap-3 items-end">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={priceSensOnly} onChange={(e) => setPriceSensOnly(e.target.checked)} />
            Market-sensitive only
          </label>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Significance</label>
            <select
              value={sigFilter}
              onChange={(e) => setSigFilter(e.target.value)}
              className="h-8 px-2 text-xs border border-input rounded-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="all">All</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>
          <span className="text-xs text-muted-foreground self-end pb-1">{rows.length} shown</span>
        </div>

        {/* Select / deselect controls */}
        <div className="flex items-center gap-2 text-sm">
          <button
            onClick={onSelectAll}
            className="px-3 py-1.5 text-xs border border-input rounded-sm hover:bg-muted transition-colors"
          >
            Select all
          </button>
          <button
            onClick={onDeselectAll}
            className="px-3 py-1.5 text-xs border border-input rounded-sm hover:bg-muted transition-colors"
          >
            Deselect all
          </button>
          <button
            onClick={onOpenConfig}
            className="px-3 py-1.5 text-xs border border-input rounded-sm hover:bg-muted transition-colors flex items-center gap-1.5"
            title="Configure announcement types"
          >
            <Settings className="w-3 h-3" />
            Configure types
          </button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-sm border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[hsl(var(--navy-deep))] text-primary-foreground">
              <th className="px-3 py-2.5 w-10">
                <input
                  type="checkbox"
                  checked={allVisibleSelected}
                  ref={el => { if (el) el.indeterminate = !allVisibleSelected && someVisibleSelected }}
                  onChange={() => allVisibleSelected
                    ? allVisibleKeys.forEach(k => selectedKeys.has(k) && onToggleKey(k))
                    : allVisibleKeys.forEach(k => !selectedKeys.has(k) && onToggleKey(k))
                  }
                  className="cursor-pointer"
                  title="Toggle all visible"
                />
              </th>
              <th className="text-left px-4 py-2.5 font-medium text-xs w-28">Date</th>
              <th className="text-left px-4 py-2.5 font-medium text-xs">Announcement</th>
              <th className="text-left px-4 py-2.5 font-medium text-xs w-44">Type</th>
              <th className="text-left px-4 py-2.5 font-medium text-xs w-20">Mkt-sens</th>
              <th className="text-left px-4 py-2.5 font-medium text-xs w-24">Significance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((item, i) => {
              const key = item.documentKey ?? `idx-${i}`
              const isSelected = selectedKeys.has(key)
              return (
                <tr
                  key={i}
                  className={`hover:bg-muted/40 ${!isSelected ? "opacity-50" : ""}`}
                >
                  <td className="px-3 py-3 text-center">
                    {item.documentKey && (
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => onToggleKey(key)}
                        className="cursor-pointer"
                      />
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">{formatDate(item.date)}</td>
                  <td className="px-4 py-3 text-xs font-medium">
                    {item.documentKey ? (
                      <button
                        onClick={() => onSelectAnnouncement(item)}
                        className="text-accent hover:underline inline-flex items-start text-left gap-1 group"
                      >
                        {item.headline}
                        <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-60 shrink-0 mt-0.5" />
                      </button>
                    ) : (
                      item.headline
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{item.type}</td>
                  <td className="px-4 py-3 text-xs">
                    {item.priceSensitive
                      ? <span className="inline-block px-1.5 py-0.5 rounded-sm bg-destructive/10 text-destructive text-xs">Yes</span>
                      : <span className="text-muted-foreground">—</span>
                    }
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium ${IMPORTANCE_CLASSES[item.importance] ?? IMPORTANCE_CLASSES.Low}`}>
                      {item.importance}
                    </span>
                  </td>
                </tr>
              )
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground text-sm">No announcements match.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
