import { useState, useMemo } from "react"
import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { FindingsJSON, UserPrefs } from "@/types"

interface Props {
  findings: FindingsJSON
  prefs: UserPrefs
  onClose: () => void
  onSave: (excludedTypes: string[]) => void
}

type RAG = "GREEN" | "AMBER" | "RED"

const RAG_CONFIG: Record<RAG, { label: string; description: string; dotClass: string }> = {
  GREEN: {
    label: "Opportunity",
    description: "Clear signal for a GP service",
    dotClass: "bg-[#375623]",
  },
  AMBER: {
    label: "Monitor",
    description: "Possible opportunity — review case by case",
    dotClass: "bg-[#806000]",
  },
  RED: {
    label: "Routine / administrative",
    description: "No direct service trigger",
    dotClass: "bg-[#9C0006]",
  },
}

function historyBadge(entry: { included: number; excluded: number; mixed: number } | undefined) {
  if (!entry) return null
  const total = entry.included + entry.excluded + entry.mixed
  if (total < 2) return null
  const excludedRatio = entry.excluded / total
  const includedRatio = entry.included / total
  if (entry.excluded === total && total >= 3)
    return { label: "Always excluded", cls: "bg-red-100 text-red-700" }
  if (excludedRatio >= 0.8)
    return { label: "Usually excluded", cls: "bg-orange-100 text-orange-700" }
  if (includedRatio >= 0.8)
    return { label: "Usually included", cls: "bg-green-100 text-green-700" }
  return null
}

export function TypeConfigPanel({ findings, prefs, onClose, onSave }: Props) {
  const [localExcluded, setLocalExcluded] = useState<Set<string>>(
    () => new Set(prefs.excludedTypes)
  )

  // Derive unique types + their RAG from findings items
  const typeMap = useMemo(() => {
    const map = new Map<string, { rag: RAG; count: number }>()
    for (const item of findings.asx.items) {
      if (!item.type) continue
      const existing = map.get(item.type)
      if (existing) {
        existing.count++
      } else {
        map.set(item.type, { rag: item.rag as RAG, count: 1 })
      }
    }
    return map
  }, [findings.asx.items])

  // Group by RAG, sorted alphabetically within each group
  const grouped = useMemo(() => {
    const groups: Record<RAG, string[]> = { GREEN: [], AMBER: [], RED: [] }
    for (const [type, { rag }] of typeMap) {
      groups[rag].push(type)
    }
    for (const rag of Object.keys(groups) as RAG[]) {
      groups[rag].sort()
    }
    return groups
  }, [typeMap])

  const toggleType = (type: string) => {
    setLocalExcluded(prev => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  const renderSection = (rag: RAG) => {
    const types = grouped[rag]
    if (types.length === 0) return null
    const { label, description, dotClass } = RAG_CONFIG[rag]
    return (
      <div key={rag} className="space-y-0.5">
        <div className="flex items-center gap-2 pt-3 pb-1.5 border-b border-border sticky top-0 bg-background z-10">
          <span className={`w-2 h-2 rounded-full shrink-0 ${dotClass}`} />
          <span className="text-xs font-semibold text-foreground uppercase tracking-wide">{label}</span>
          <span className="text-xs text-muted-foreground">— {description}</span>
        </div>
        {types.map(type => {
          const data = typeMap.get(type)!
          const badge = historyBadge(prefs.typeHistory?.[type])
          const excluded = localExcluded.has(type)
          return (
            <label
              key={type}
              className={`flex items-center gap-3 px-2 py-1.5 rounded-sm cursor-pointer hover:bg-muted/50 transition-colors ${excluded ? "opacity-50" : ""}`}
            >
              <input
                type="checkbox"
                checked={!excluded}
                onChange={() => toggleType(type)}
                className="cursor-pointer shrink-0"
              />
              <span className="text-sm flex-1 leading-snug">{type}</span>
              <span className="text-xs text-muted-foreground shrink-0 tabular-nums">{data.count}×</span>
              {badge && (
                <span className={`text-xs px-1.5 py-0.5 rounded-sm font-medium shrink-0 ${badge.cls}`}>
                  {badge.label}
                </span>
              )}
            </label>
          )
        })}
      </div>
    )
  }

  const excludedCount = localExcluded.size

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="fixed right-0 top-0 bottom-0 z-50 w-[420px] max-w-full bg-background border-l border-border shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-card shrink-0">
          <div>
            <h2 className="font-heading text-lg font-medium text-foreground">Announcement Types</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Saved as defaults — auto-applied on next upload
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-sm hover:bg-muted transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-4 pb-4">
          <p className="text-xs text-muted-foreground py-3 border-b border-border mb-1">
            Uncheck a type to exclude it from the Corporate Activity section of the report.
            The number (e.g. <span className="font-mono font-medium">4×</span>) shows how many times
            that type appeared in this company's 12-month announcement history. History badges reflect
            your team's past include/exclude decisions across previous reviews.
          </p>
          {(["GREEN", "AMBER", "RED"] as RAG[]).map(rag => renderSection(rag))}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-border bg-card flex items-center justify-between gap-3 shrink-0">
          <div className="text-xs text-muted-foreground">
            {excludedCount === 0
              ? "All types included"
              : `${excludedCount} type${excludedCount !== 1 ? "s" : ""} excluded`}
          </div>
          <div className="flex items-center gap-2">
            {excludedCount > 0 && (
              <button
                onClick={() => setLocalExcluded(new Set())}
                className="text-xs text-muted-foreground hover:text-foreground underline-offset-2 hover:underline transition-colors"
              >
                Include all
              </button>
            )}
            <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
            <Button size="sm" onClick={() => onSave(Array.from(localExcluded))}>
              Save & Apply
            </Button>
          </div>
        </div>
      </div>
    </>
  )
}
