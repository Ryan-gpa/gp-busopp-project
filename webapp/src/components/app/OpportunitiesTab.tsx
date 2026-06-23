import { useMemo } from "react"
import { formatDate, GP_SERVICES, type FindingsJSON, type AsxItem } from "@/types"
import { cn } from "@/lib/utils"
import { ExternalLink } from "lucide-react"

interface Props {
  findings: FindingsJSON
  onSelectAnnouncement: (item: AsxItem) => void
}

const RAG_CELL_CLASSES: Record<string, string> = {
  GREEN: "opp-green",
  AMBER: "opp-amber",
  RED:   "",
}

export function OpportunitiesTab({ findings, onSelectAnnouncement }: Props) {
  const { asx } = findings

  const sorted = useMemo(() => {
    return [...asx.items].sort((a, b) => {
      if (a.priority !== b.priority) return a.priority - b.priority
      return new Date(b.date).getTime() - new Date(a.date).getTime()
    })
  }, [asx.items])

  const counts = asx.oppCounts

  return (
    <div className="space-y-5">
      {/* Internal banner */}
      <div className="rounded-sm border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 font-medium">
        Internal use only — remove before sharing with client
      </div>

      {/* RAG summary */}
      <div className="flex gap-4 flex-wrap">
        {(["GREEN", "AMBER"] as const).map((rag) => (
          <div key={rag} className="flex items-center gap-2 text-sm">
            <span className={cn("inline-flex items-center rounded-sm px-2.5 py-1 font-medium text-xs",
              rag === "GREEN" ? "opp-green" : "opp-amber"
            )}>
              {rag}
            </span>
            <span className="font-semibold text-foreground">{counts[rag]}</span>
            <span className="text-muted-foreground text-xs">
              {asx.ragMeaning?.[rag] ?? ""}
            </span>
          </div>
        ))}
        <div className="flex items-center gap-2 text-sm">
          <span className="font-semibold text-muted-foreground">{counts["RED"]}</span>
          <span className="text-muted-foreground text-xs">
            {asx.ragMeaning?.["RED"] ?? "Routine, administrative or investor-relations disclosure — no direct service trigger"}
          </span>
        </div>
      </div>

      {/* Service matrix table */}
      <div className="overflow-x-auto rounded-sm border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[hsl(var(--navy-deep))] text-primary-foreground">
              <th className="text-left px-4 py-2.5 font-medium text-xs w-28">Date</th>
              <th className="text-left px-4 py-2.5 font-medium text-xs">Announcement</th>
              <th className="text-left px-4 py-2.5 font-medium text-xs w-40">Type</th>
              {GP_SERVICES.map((svc) => (
                <th key={svc} className="text-center px-2 py-2.5 font-medium text-xs w-24 leading-tight">{svc}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sorted.map((item, i) => (
              <tr key={i} className="hover:bg-muted/30">
                <td className="px-4 py-2.5 text-xs text-muted-foreground whitespace-nowrap">{formatDate(item.date)}</td>
                <td className="px-4 py-2.5 text-xs font-medium">
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
                <td className="px-4 py-2.5 text-xs text-muted-foreground">{item.type}</td>
                {GP_SERVICES.map((svc) => {
                  const matched = item.oppServices?.includes(svc)
                  return (
                    <td key={svc} className="px-2 py-2.5 text-center">
                      {matched ? (
                        <span className={cn("inline-flex items-center justify-center w-6 h-6 rounded-sm text-xs font-bold", RAG_CELL_CLASSES[item.rag])}>
                          ✓
                        </span>
                      ) : (
                        <span className="text-muted-foreground/30 text-xs">—</span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
