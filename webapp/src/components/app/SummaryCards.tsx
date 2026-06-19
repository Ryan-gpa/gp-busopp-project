import { Card, CardContent } from "@/components/ui/card"
import type { FindingsJSON } from "@/types"
import { formatCurrency } from "@/types"

interface Props {
  findings: FindingsJSON
}

export function SummaryCards({ findings }: Props) {
  const { entity, ticker, reportType, summary, materiality, materialityBasis, detectionNote, asx } = findings

  const cards = [
    { label: "Addressed / Present", value: summary.present, className: "status-addressed" },
    { label: "Not detected", value: summary.not_found, className: "status-notfound" },
    { label: "Below materiality", value: summary.below_materiality, className: "status-below" },
    { label: "Not applicable", value: summary.na, className: "bg-muted text-muted-foreground" },
  ]

  const periodLabel = asx.periodEnd
    ? new Date(asx.periodEnd).toLocaleDateString("en-AU", { day: "numeric", month: "long", year: "numeric" })
    : ""

  return (
    <div className="space-y-6">
      {/* Entity header */}
      <div className="flex flex-wrap items-baseline gap-3">
        <h2 className="font-heading text-3xl font-light text-foreground">{entity}</h2>
        <span className="text-sm font-medium px-2 py-0.5 rounded-sm bg-secondary text-secondary-foreground">{ticker}</span>
        <span className="text-sm px-2 py-0.5 rounded-sm bg-muted text-muted-foreground capitalize">{reportType}</span>
        {periodLabel && <span className="text-sm text-muted-foreground">period to {periodLabel}</span>}
      </div>

      {/* Checklist summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {cards.map(({ label, value, className }) => (
          <Card key={label} className="border-border">
            <CardContent className="p-4 flex flex-col gap-1">
              <span className={`text-2xl font-semibold ${className} inline-block px-2 py-0.5 rounded-sm w-fit`}>{value}</span>
              <span className="text-xs text-muted-foreground">{label}</span>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Materiality notice */}
      <div className="rounded-sm border border-border bg-card p-4 text-sm space-y-1">
        <p><span className="font-medium">Materiality threshold:</span> {formatCurrency(materiality)} — {materialityBasis}</p>
        <p className="text-muted-foreground text-xs">{findings.basis}</p>
      </div>

      {/* Detection note (collapsible) */}
      <details className="text-xs text-muted-foreground border border-border rounded-sm">
        <summary className="cursor-pointer px-3 py-2 font-medium text-foreground">Detection methodology</summary>
        <p className="px-3 pb-3 pt-1">{detectionNote}</p>
      </details>
    </div>
  )
}
