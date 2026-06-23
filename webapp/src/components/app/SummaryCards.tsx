import { Card, CardContent } from "@/components/ui/card"
import type { FindingsJSON } from "@/types"
import { formatCurrency } from "@/types"

function fmt(n: number) {
  return new Intl.NumberFormat("en-AU", { style: "currency", currency: "AUD", maximumFractionDigits: 0 }).format(n)
}

interface Props {
  findings: FindingsJSON
}

const DOMICILE_LABEL: Record<string, { label: string; cls: string }> = {
  AU:      { label: "Australian entity",        cls: "bg-[#C6E0B4] text-[#375623]" },
  NZ:      { label: "NZ-domiciled (ASX listed)", cls: "bg-[#FFE699] text-[#806000]" },
  FOREIGN: { label: "Foreign-domiciled",         cls: "bg-[#FFC7CE] text-[#9C0006]" },
  UNKNOWN: { label: "Domicile unconfirmed",       cls: "bg-muted text-muted-foreground" },
}

export function SummaryCards({ findings }: Props) {
  const { entity, ticker, reportType, summary, materiality, materialityBasis, detectionNote, asx } = findings
  const domicile = findings.domicile ?? "UNKNOWN"
  const domicileMeta = DOMICILE_LABEL[domicile] ?? DOMICILE_LABEL.UNKNOWN
  const foreignSignals = findings.foreignSignals ?? []
  const auOnlyNa = findings.results.filter(r => (r as any).naReason === "foreign-domiciled")

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
        <span className={`text-xs font-medium px-2 py-0.5 rounded-sm ${domicileMeta.cls}`}>{domicileMeta.label}</span>
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

      {/* Materiality analysis */}
      <div className="rounded-sm border border-border bg-card overflow-hidden">
        <div className="px-4 py-3 border-b border-border bg-muted/20">
          <p className="text-sm font-medium text-foreground">Materiality analysis</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Working materiality applied to this review: <span className="font-medium text-foreground">{formatCurrency(materiality)}</span>
            {" "}— {materialityBasis}
          </p>
        </div>
        {findings.materialityBenchmarks && findings.materialityBenchmarks.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-muted/30 border-b border-border">
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">Benchmark</th>
                  <th className="text-right px-4 py-2 font-medium text-muted-foreground">Base figure</th>
                  <th className="text-right px-4 py-2 font-medium text-muted-foreground">%</th>
                  <th className="text-right px-4 py-2 font-medium text-muted-foreground">Materiality</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground hidden lg:table-cell">Typical use</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {findings.materialityBenchmarks.map((b, i) => {
                  const isWorking = b.amount === materiality
                  return (
                    <tr key={i} className={isWorking ? "bg-[#C6E0B4]/20" : "hover:bg-muted/20"}>
                      <td className="px-4 py-2 text-foreground">
                        {b.basis}
                        {isWorking && <span className="ml-2 text-[10px] font-semibold text-[#375623] uppercase tracking-wide">applied</span>}
                      </td>
                      <td className="px-4 py-2 text-right font-mono text-muted-foreground">{fmt(b.figure)}</td>
                      <td className="px-4 py-2 text-right text-muted-foreground">{b.pct}%</td>
                      <td className="px-4 py-2 text-right font-mono font-medium text-foreground">{fmt(b.amount)}</td>
                      <td className="px-4 py-2 text-muted-foreground hidden lg:table-cell">{b.note}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="px-4 py-3 text-xs text-muted-foreground">{materialityBasis}</p>
        )}
        <div className="px-4 py-2.5 border-t border-border bg-muted/10">
          <p className="text-[11px] text-muted-foreground">{findings.basis}</p>
        </div>
      </div>

      {/* Foreign domicile notice */}
      {domicile !== "AU" && (
        <div className={`rounded-sm border p-4 text-sm space-y-2 ${
          domicile === "FOREIGN" || domicile === "NZ"
            ? "border-[#806000]/30 bg-[#FFE699]/20"
            : "border-border bg-muted/30"
        }`}>
          <p className="font-medium text-foreground">
            {domicile === "NZ" && "New Zealand domiciled entity — Corporations Act items not applicable"}
            {domicile === "FOREIGN" && "Foreign-domiciled entity — Corporations Act items not applicable"}
            {domicile === "UNKNOWN" && "Entity domicile could not be confirmed — Corporations Act applicability unverified"}
          </p>
          {auOnlyNa.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {auOnlyNa.length} standard{auOnlyNa.length !== 1 ? "s" : ""} auto-marked N/A:{" "}
              {auOnlyNa.map(r => r.standard).join(" · ")}
            </p>
          )}
          {foreignSignals.length > 0 && (
            <div className="text-xs text-muted-foreground space-y-0.5 pt-1 border-t border-[#806000]/20">
              <p className="font-medium text-foreground">Foreign listing signals detected:</p>
              {foreignSignals.map((s, i) => (
                <p key={i}>
                  <span className="font-mono font-bold">{s.exchange}</span>
                  {" — "}{s.headline} ({s.date})
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Board and management */}
      {findings.officers && findings.officers.length > 0 && (
        <div className="rounded-sm border border-border bg-card overflow-hidden">
          <div className="px-4 py-3 border-b border-border bg-muted/20">
            <p className="text-sm font-medium text-foreground">Board and management</p>
            <p className="text-xs text-muted-foreground mt-0.5">Extracted from Directors' Report</p>
          </div>
          <div className="divide-y divide-border">
            {findings.officers.map((o, i) => (
              <div key={i} className="px-4 py-2.5 flex items-center gap-4">
                <span className="text-sm font-medium text-foreground w-52 shrink-0">{o.name}</span>
                <span className="text-xs px-2 py-0.5 rounded-sm bg-muted text-muted-foreground">{o.roleNorm || o.role}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Detection note (collapsible) */}
      <details className="text-xs text-muted-foreground border border-border rounded-sm">
        <summary className="cursor-pointer px-3 py-2 font-medium text-foreground">Detection methodology</summary>
        <p className="px-3 pb-3 pt-1">{detectionNote}</p>
      </details>
    </div>
  )
}
