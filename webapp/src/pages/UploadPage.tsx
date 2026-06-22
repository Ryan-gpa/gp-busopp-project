import React, { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Upload, FileText, ChevronDown, ChevronUp, Loader2, Globe, Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"
import type { FindingsJSON, CurrentUser } from "@/types"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import bundledCompanies from "@/data/asx_companies.json"

type Stage = "idle" | "uploading" | "reviewing" | "done" | "error"
type Mode = "file" | "asx"

const STAGE_LABELS: Record<Stage, string> = {
  idle: "",
  uploading: "Uploading PDF…",
  reviewing: "Running checklist & fetching ASX announcements…",
  done: "Complete",
  error: "Failed",
}

const STAGE_PROGRESS: Record<Stage, number> = {
  idle: 0,
  uploading: 15,
  reviewing: 70,
  done: 100,
  error: 0,
}

interface Company { code: string; name: string }

interface AuditEntry {
  id: string
  timestamp: string
  displayName: string
  userId: string
  ticker: string | null
  entity: string | null
  reportType: string
  source: string
  outcome: "pending" | "success" | "error"
  docxName: string | null
}

const OUTCOME_CLS: Record<string, string> = {
  success: "bg-[#C6E0B4] text-[#375623]",
  error:   "bg-[#FFC7CE] text-[#9C0006]",
  pending: "bg-muted text-muted-foreground",
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("en-AU", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  })
}

function TickerCombobox({
  value, onChange, onSelect, companies, required, inputClassName,
}: {
  value: string
  onChange: (v: string) => void
  onSelect?: (c: Company) => void
  companies: Company[]
  required?: boolean
  inputClassName?: string
}) {
  const [show, setShow] = useState(false)
  const [activeIdx, setActiveIdx] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)

  const suggestions = useMemo(() => {
    const q = value.trim().toLowerCase()
    if (!q) return []
    const codeHits = companies.filter(c => c.code.toLowerCase().startsWith(q))
    const nameHits = companies.filter(c => !c.code.toLowerCase().startsWith(q) && c.name.toLowerCase().includes(q))
    return [...codeHits, ...nameHits].slice(0, 8)
  }, [value, companies])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setShow(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const select = (c: Company) => { onChange(c.code); onSelect?.(c); setShow(false); setActiveIdx(-1) }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setShow(true); setActiveIdx(i => Math.min(i + 1, suggestions.length - 1)) }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActiveIdx(i => Math.max(i - 1, -1)) }
    else if (e.key === "Enter" && activeIdx >= 0 && suggestions.length > 0) { e.preventDefault(); select(suggestions[activeIdx]) }
    else if (e.key === "Escape") setShow(false)
  }

  return (
    <div ref={containerRef} className="relative">
      <input
        type="text" value={value} placeholder="e.g. NVU" required={required} autoComplete="off"
        onChange={e => { onChange(e.target.value.toUpperCase()); setShow(true); setActiveIdx(-1) }}
        onFocus={() => { if (value) setShow(true) }}
        onKeyDown={handleKeyDown}
        className={inputClassName}
      />
      {show && suggestions.length > 0 && (
        <div className="absolute z-50 top-full left-0 mt-1 bg-background border border-border rounded-sm shadow-lg overflow-hidden max-h-60 overflow-y-auto min-w-full w-max">
          {suggestions.map((c, i) => (
            <button key={c.code} type="button" onMouseDown={e => { e.preventDefault(); select(c) }}
              className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 transition-colors whitespace-nowrap ${i === activeIdx ? "bg-muted" : "hover:bg-muted/60"}`}>
              <span className="font-mono font-semibold text-foreground w-12 shrink-0">{c.code}</span>
              <span className="text-muted-foreground">— {c.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

interface Props {
  currentUser: CurrentUser | null
}

export default function UploadPage({ currentUser }: Props) {
  const navigate = useNavigate()
  const API_BASE = import.meta.env.VITE_API_URL || ""

  // Form state
  const [mode, setMode] = useState<Mode>("file")
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [stage, setStage] = useState<Stage>("idle")
  const [errorMsg, setErrorMsg] = useState("")
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [ticker, setTicker] = useState("")
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null)
  const [reportType, setReportType] = useState("auto")
  const [includeAsx, setIncludeAsx] = useState(true)
  const [downloadAsx, setDownloadAsx] = useState(false)
  const [asOfPeriod, setAsOfPeriod] = useState(false)
  const [allCompanies, setAllCompanies] = useState<Company[]>(bundledCompanies as Company[])

  // Recent reviews state
  const [recentEntries, setRecentEntries] = useState<AuditEntry[]>([])

  useEffect(() => {
    fetch("/api/asx/companies").then(r => r.json()).then(d => setAllCompanies(d.companies || [])).catch(() => {})
    fetch(`${API_BASE}/api/audit`).then(r => r.json()).then(d => {
      const all: AuditEntry[] = (d.entries || []).slice().reverse()
      setRecentEntries(all.slice(0, 12))
    }).catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f?.type === "application/pdf") setFile(f)
  }, [])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (f) setFile(f)
  }

  const handleSubmit = async (e: { preventDefault(): void }) => {
    e.preventDefault()
    if (mode === "file" && !file) return
    if (mode === "asx" && !ticker.trim()) return

    setStage(mode === "file" ? "uploading" : "reviewing")
    setErrorMsg("")

    const form = new FormData()
    if (mode === "file" && file) form.append("file", file)
    form.append("ticker", ticker)
    form.append("report_type", mode === "asx" && reportType === "auto" ? "annual" : reportType)
    form.append("no_asx", String(!includeAsx))
    form.append("download_asx", String(downloadAsx))
    form.append("as_of_period", String(asOfPeriod))
    if (currentUser) {
      form.append("user_id", currentUser.userId)
      form.append("display_name", currentUser.displayName)
    }

    try {
      setStage("reviewing")
      const res = await fetch(`${API_BASE}/api/review`, { method: "POST", body: form })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || `HTTP ${res.status}`)
      }
      setStage("done")
      const data = await res.json() as { findings: FindingsJSON; auditId?: string }
      navigate("/results", { state: { findings: data.findings, auditId: data.auditId ?? "" } })
    } catch (err: unknown) {
      setStage("error")
      setErrorMsg(err instanceof Error ? err.message : String(err))
    }
  }

  const isRunning = stage !== "idle" && stage !== "error" && stage !== "done"
  const canSubmit = mode === "file" ? !!file : !!ticker.trim()

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-[hsl(var(--navy-deep))] text-primary-foreground">
        <div className="max-w-6xl mx-auto px-6 py-5 flex items-baseline gap-3">
          <span className="font-heading text-2xl font-light tracking-tight">Growth Partners</span>
          <span className="text-sm text-primary-foreground/50 font-sans">Disclosure Review</span>
          <div className="ml-auto flex items-center gap-4">
            {currentUser && (
              <span className="text-xs text-primary-foreground/50">{currentUser.displayName}</span>
            )}
            <button type="button" onClick={() => navigate("/audit")}
              className="text-xs text-primary-foreground/60 hover:text-primary-foreground transition-colors">
              Full audit log
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10">
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-10 items-start">

          {/* ── Left: review form ── */}
          <div>
            <h1 className="font-heading text-3xl font-light text-foreground mb-1">New Review</h1>
            <p className="text-muted-foreground mb-7 text-sm">
              Screen an Appendix 4D or 4E report against AASB&nbsp;/&nbsp;IFRS disclosure requirements.
            </p>

            <form onSubmit={handleSubmit} className="space-y-5">
              <Tabs defaultValue="file" value={mode} onValueChange={val => setMode(val as Mode)} className="w-full">
                <TabsList className="grid grid-cols-2 mb-5 bg-muted/60 p-1 rounded-sm">
                  <TabsTrigger value="file" className="flex items-center gap-2 text-xs font-semibold py-2">
                    <Upload className="w-4 h-4" /> Upload PDF
                  </TabsTrigger>
                  <TabsTrigger value="asx" className="flex items-center gap-2 text-xs font-semibold py-2">
                    <Globe className="w-4 h-4" /> ASX Ticker
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="file" className="space-y-4 outline-none">
                  <div
                    onDragOver={e => { e.preventDefault(); setDragging(true) }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={handleDrop}
                    onClick={() => document.getElementById("pdf-input")?.click()}
                    className={cn(
                      "border-2 border-dashed rounded-sm p-8 text-center cursor-pointer transition-colors",
                      dragging ? "border-accent bg-accent/5" : "border-border hover:border-accent/50",
                      file && "border-accent/40 bg-accent/5"
                    )}
                  >
                    <input id="pdf-input" type="file" accept=".pdf" className="hidden" onChange={handleFileChange} />
                    {file ? (
                      <div className="flex items-center justify-center gap-3 text-accent">
                        <FileText className="w-5 h-5 shrink-0" />
                        <span className="text-sm font-medium truncate max-w-[220px]">{file.name}</span>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center gap-2 text-muted-foreground">
                        <Upload className="w-7 h-7" />
                        <p className="text-sm">Drop a PDF here, or click to browse</p>
                        <p className="text-xs">Text-based PDFs only</p>
                      </div>
                    )}
                  </div>
                </TabsContent>

                <TabsContent value="asx" className="space-y-4 outline-none">
                  <div className="border border-border rounded-sm p-5 bg-card space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider">ASX Ticker Code</label>
                        <TickerCombobox
                          value={ticker}
                          onChange={v => { setTicker(v); setSelectedCompany(null) }}
                          onSelect={c => setSelectedCompany(c)}
                          companies={allCompanies}
                          required={mode === "asx"}
                          inputClassName="w-full h-10 px-3 text-sm border border-input rounded-sm bg-background focus:outline-none focus:ring-1 focus:ring-accent font-semibold uppercase"
                        />
                        {selectedCompany && (
                          <p className="text-xs text-muted-foreground">
                            {selectedCompany.name} <span className="font-mono text-foreground">({selectedCompany.code})</span>
                          </p>
                        )}
                      </div>
                      <div className="space-y-1.5">
                        <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider">Report to Fetch</label>
                        <select value={reportType === "auto" ? "annual" : reportType} onChange={e => setReportType(e.target.value)}
                          className="w-full h-10 px-3 text-sm border border-input rounded-sm bg-background focus:outline-none focus:ring-1 focus:ring-accent">
                          <option value="annual">Annual (Appendix 4E)</option>
                          <option value="interim">Half-Year (Appendix 4D)</option>
                        </select>
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground">Fetches the latest matching report directly from the ASX announcements database.</p>
                  </div>
                </TabsContent>
              </Tabs>

              <button type="button"
                className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => setShowAdvanced(!showAdvanced)}>
                {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                Advanced options
              </button>

              {showAdvanced && (
                <div className="border border-border rounded-sm p-5 space-y-2 bg-card">
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={includeAsx} onChange={e => setIncludeAsx(e.target.checked)} className="rounded" />
                    Include ASX announcements (12-month history)
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={downloadAsx} onChange={e => setDownloadAsx(e.target.checked)} className="rounded" />
                    Download announcement PDFs locally
                    <span className="text-xs text-muted-foreground">(slow — 10 min timeout)</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={asOfPeriod} onChange={e => setAsOfPeriod(e.target.checked)} className="rounded" />
                    Anchor ASX window to report period-end
                  </label>
                </div>
              )}

              {isRunning && (
                <div className="space-y-2">
                  <Progress value={STAGE_PROGRESS[stage]} />
                  <p className="text-sm text-muted-foreground flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" /> {STAGE_LABELS[stage]}
                  </p>
                </div>
              )}

              {stage === "error" && (
                <div className="rounded-sm border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive whitespace-pre-wrap">
                  {errorMsg}
                </div>
              )}

              <Button type="submit" disabled={!canSubmit || isRunning} className="w-full" size="lg">
                {isRunning
                  ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Running review…</>
                  : "Run review"
                }
              </Button>
            </form>
          </div>

          {/* ── Right: recent reviews ── */}
          <div>
            <div className="flex items-baseline justify-between mb-5">
              <h2 className="font-heading text-xl font-light text-foreground">Recent reviews</h2>
              <button type="button" onClick={() => navigate("/audit")}
                className="text-xs text-accent hover:underline">
                Full log →
              </button>
            </div>

            {recentEntries.length === 0 ? (
              <div className="border border-border rounded-sm bg-card p-8 text-center text-sm text-muted-foreground">
                No reviews yet — run one to get started.
              </div>
            ) : (
              <div className="rounded-sm border border-border overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-muted/30 border-b border-border">
                      <th className="text-left px-3 py-2.5 font-medium text-muted-foreground">Company</th>
                      <th className="text-left px-3 py-2.5 font-medium text-muted-foreground whitespace-nowrap">Date</th>
                      <th className="text-left px-3 py-2.5 font-medium text-muted-foreground">By</th>
                      <th className="text-left px-3 py-2.5 font-medium text-muted-foreground">Status</th>
                      <th className="px-3 py-2.5 font-medium text-muted-foreground text-right">Report</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {recentEntries.map(e => (
                      <tr key={e.id} className="hover:bg-muted/20 transition-colors">
                        <td className="px-3 py-2.5">
                          <p className="font-medium text-foreground truncate max-w-[140px]">
                            {e.entity || e.ticker || "—"}
                          </p>
                          {e.ticker && e.entity && (
                            <p className="text-muted-foreground font-mono">{e.ticker}</p>
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-muted-foreground whitespace-nowrap">
                          {fmtDate(e.timestamp)}
                        </td>
                        <td className="px-3 py-2.5 text-muted-foreground truncate max-w-[100px]">
                          {e.displayName || e.userId || "—"}
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={`inline-block px-1.5 py-0.5 rounded-sm font-medium capitalize ${OUTCOME_CLS[e.outcome] || "bg-muted text-muted-foreground"}`}>
                            {e.outcome}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          {e.docxName ? (
                            <a href={`${API_BASE}/api/download/${encodeURIComponent(e.docxName)}`}
                              download={e.docxName}
                              className="inline-flex items-center gap-1 text-accent hover:underline whitespace-nowrap">
                              <Download className="w-3 h-3" /> .docx
                            </a>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
