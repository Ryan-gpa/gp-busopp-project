import { useState, useEffect, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { ArrowLeft, FileText, FolderOpen, ChevronDown, ChevronUp, Loader2 } from "lucide-react"

interface BoxReport {
  id: string
  name: string
  size: number | null
  modifiedAt: string
  parentName: string | null
}

interface AuditEntry {
  id: string
  timestamp: string
  userId: string
  displayName: string
  ticker: string | null
  entity: string | null
  reportType: string
  source: "upload" | "asx" | "box"
  reportFile: string | null
  asxEnabled: boolean
  downloadAsx: boolean
  outcome: "pending" | "success" | "error"
  errorMessage: string | null
  docxName: string | null
  docxGeneratedAt: string | null
}

const SOURCE_LABEL: Record<string, string> = {
  upload: "Uploaded PDF",
  asx: "ASX fetch",
  box: "Box",
}

const OUTCOME_CLS: Record<string, string> = {
  success: "bg-[#C6E0B4] text-[#375623]",
  error: "bg-[#FFC7CE] text-[#9C0006]",
  pending: "bg-muted text-muted-foreground",
}

function fmt(iso: string) {
  return new Date(iso).toLocaleString("en-AU", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  })
}

function fmtSize(bytes: number | null) {
  if (!bytes) return ""
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function AuditPage() {
  const navigate = useNavigate()
  const API_BASE = import.meta.env.VITE_API_URL || ""
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [dateRange, setDateRange] = useState<"7" | "30" | "90" | "all">("30")
  const [boxReports, setBoxReports] = useState<BoxReport[] | null>(null)
  const [boxLoading, setBoxLoading] = useState(false)
  const [boxOpen, setBoxOpen] = useState(false)
  const [defaultFolder, setDefaultFolder] = useState<{ id: string; name: string } | null>(null)
  const [folderPickerOpen, setFolderPickerOpen] = useState(false)
  const [folderItems, setFolderItems] = useState<{ id: string; name: string; type: string }[]>([])
  const [folderPath, setFolderPath] = useState<{ id: string; name: string }[]>([{ id: "0", name: "All Files" }])
  const [folderLoading, setFolderLoading] = useState(false)

  const loadBoxReports = () => {
    if (boxReports !== null) { setBoxOpen(o => !o); return }
    setBoxOpen(true)
    setBoxLoading(true)
    fetch(`${API_BASE}/api/box/reports`)
      .then(r => r.json())
      .then(d => setBoxReports(d.reports || []))
      .catch(() => setBoxReports([]))
      .finally(() => setBoxLoading(false))
  }

  const loadFolderPicker = (id: string, path: { id: string; name: string }[]) => {
    setFolderLoading(true)
    fetch(`${API_BASE}/api/box/folder/${id}`)
      .then(r => r.json())
      .then(d => {
        setFolderItems((d.items || []).filter((i: { type: string }) => i.type === "folder"))
        setFolderPath(path)
      })
      .catch(() => {})
      .finally(() => setFolderLoading(false))
  }

  const openFolderPicker = () => {
    setFolderPickerOpen(true)
    loadFolderPicker("0", [{ id: "0", name: "All Files" }])
  }

  const selectFolder = (id: string, name: string) => {
    setDefaultFolder({ id, name })
    setFolderPickerOpen(false)
    fetch(`${API_BASE}/api/prefs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ boxOutputFolderId: id, boxOutputFolderName: name }),
    }).catch(() => {})
  }

  useEffect(() => {
    fetch(`${API_BASE}/api/prefs`)
      .then(r => r.json())
      .then(p => {
        if (p.boxOutputFolderId) setDefaultFolder({ id: p.boxOutputFolderId, name: p.boxOutputFolderName || p.boxOutputFolderId })
      })
      .catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const [userFilter, setUserFilter] = useState("all")
  const [outcomeFilter, setOutcomeFilter] = useState("all")

  useEffect(() => {
    fetch(`${API_BASE}/api/audit`)
      .then(r => r.json())
      .then(d => setEntries((d.entries || []).slice().reverse()))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const uniqueUsers = useMemo(() => {
    const seen = new Map<string, string>()
    for (const e of entries) seen.set(e.userId, e.displayName || e.userId)
    return Array.from(seen.entries()).map(([id, name]) => ({ id, name }))
  }, [entries])

  const filtered = useMemo(() => {
    const cutoff = dateRange === "all" ? null : new Date(Date.now() - parseInt(dateRange) * 86400_000)
    return entries.filter(e => {
      if (cutoff && new Date(e.timestamp) < cutoff) return false
      if (userFilter !== "all" && e.userId !== userFilter) return false
      if (outcomeFilter !== "all" && e.outcome !== outcomeFilter) return false
      return true
    })
  }, [entries, dateRange, userFilter, outcomeFilter])

  const stats = useMemo(() => ({
    total: filtered.length,
    companies: new Set(filtered.map(e => e.ticker || e.entity).filter(Boolean)).size,
    users: new Set(filtered.map(e => e.userId)).size,
    reports: filtered.filter(e => e.docxName).length,
  }), [filtered])

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-[hsl(var(--navy-deep))] text-primary-foreground">
        <div className="max-w-7xl mx-auto px-6 py-5 flex items-center gap-4">
          <button
            onClick={() => navigate("/")}
            className="flex items-center gap-1.5 text-sm text-primary-foreground/60 hover:text-primary-foreground transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Home
          </button>
          <span className="text-primary-foreground/20">|</span>
          <span className="font-heading text-xl font-light">Audit Log</span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Reviews run", value: stats.total },
            { label: "Companies", value: stats.companies },
            { label: "Users", value: stats.users },
            { label: "Reports generated", value: stats.reports },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-sm border border-border bg-card p-4">
              <p className="text-2xl font-semibold text-foreground">{value}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-muted-foreground">Period:</span>
            {(["7", "30", "90", "all"] as const).map(v => (
              <button
                key={v}
                onClick={() => setDateRange(v)}
                className={`px-2.5 py-1 rounded-sm border transition-colors ${
                  dateRange === v
                    ? "bg-foreground text-background border-foreground"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                {v === "all" ? "All time" : `Last ${v}d`}
              </button>
            ))}
          </div>
          <select
            value={userFilter}
            onChange={e => setUserFilter(e.target.value)}
            className="h-7 px-2 text-xs border border-border rounded-sm bg-background focus:outline-none"
          >
            <option value="all">All users</option>
            {uniqueUsers.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
          </select>
          <select
            value={outcomeFilter}
            onChange={e => setOutcomeFilter(e.target.value)}
            className="h-7 px-2 text-xs border border-border rounded-sm bg-background focus:outline-none"
          >
            <option value="all">All outcomes</option>
            <option value="success">Success</option>
            <option value="error">Error</option>
          </select>
          <span className="text-xs text-muted-foreground ml-auto">{filtered.length} entries</span>
        </div>

        {/* Table */}
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-muted-foreground">No audit entries match the current filters.</p>
        ) : (
          <div className="rounded-sm border border-border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-muted/30 border-b border-border">
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground whitespace-nowrap">Date / Time</th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">User</th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Company</th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Type</th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Source</th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Parameters</th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Outcome</th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Report</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {filtered.map(e => (
                    <tr key={e.id} className="hover:bg-muted/20 transition-colors">
                      <td className="px-4 py-2.5 text-muted-foreground whitespace-nowrap font-mono">
                        {fmt(e.timestamp)}
                      </td>
                      <td className="px-4 py-2.5">
                        <p className="font-medium text-foreground">{e.displayName || "—"}</p>
                        <p className="text-muted-foreground">{e.userId}</p>
                      </td>
                      <td className="px-4 py-2.5">
                        <p className="font-medium text-foreground">{e.entity || e.ticker || "—"}</p>
                        {e.ticker && e.entity && <p className="text-muted-foreground">{e.ticker}</p>}
                      </td>
                      <td className="px-4 py-2.5 capitalize text-foreground whitespace-nowrap">
                        {e.reportType === "interim" ? "Half-year" : e.reportType || "—"}
                      </td>
                      <td className="px-4 py-2.5 text-foreground whitespace-nowrap">
                        {SOURCE_LABEL[e.source] || e.source}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        <span className={e.asxEnabled ? "text-foreground" : "line-through"}>ASX</span>
                        {e.downloadAsx && <span className="ml-1.5 text-[10px] px-1 bg-muted rounded">+PDFs</span>}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-block px-1.5 py-0.5 rounded-sm font-medium capitalize ${OUTCOME_CLS[e.outcome] || "bg-muted text-muted-foreground"}`}>
                          {e.outcome}
                        </span>
                        {e.errorMessage && (
                          <p className="text-[10px] text-destructive mt-0.5 max-w-[200px] truncate" title={e.errorMessage}>
                            {e.errorMessage}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        {e.docxName ? (
                          <a
                            href={`${import.meta.env.VITE_API_URL || ""}/api/download/${e.docxName}`}
                            className="flex items-center gap-1 text-accent hover:underline whitespace-nowrap"
                            download
                          >
                            <FileText className="w-3 h-3" /> .docx
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
          </div>
        )}
        {/* Prior reports in Box */}
        <div className="rounded-sm border border-border overflow-hidden">
          <button
            onClick={loadBoxReports}
            className="w-full flex items-center gap-2 px-4 py-3 text-sm font-medium text-foreground bg-card hover:bg-muted/30 transition-colors"
          >
            <FolderOpen className="w-4 h-4 text-accent" />
            Prior reports in Box
            {boxLoading
              ? <Loader2 className="w-3.5 h-3.5 animate-spin ml-auto text-muted-foreground" />
              : boxOpen
                ? <ChevronUp className="w-4 h-4 ml-auto text-muted-foreground" />
                : <ChevronDown className="w-4 h-4 ml-auto text-muted-foreground" />
            }
          </button>
          {boxOpen && !boxLoading && (
            <div className="border-t border-border">
              {!boxReports || boxReports.length === 0 ? (
                <p className="px-4 py-4 text-sm text-muted-foreground">
                  No disclosure review reports found in Box. Reports are saved automatically when generated from a Box-sourced review.
                </p>
              ) : (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-muted/20 border-b border-border">
                      <th className="text-left px-4 py-2 font-medium text-muted-foreground">Report</th>
                      <th className="text-left px-4 py-2 font-medium text-muted-foreground">Folder</th>
                      <th className="text-left px-4 py-2 font-medium text-muted-foreground whitespace-nowrap">Last modified</th>
                      <th className="text-left px-4 py-2 font-medium text-muted-foreground">Size</th>
                      <th className="px-4 py-2" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {boxReports.map(r => (
                      <tr key={r.id} className="hover:bg-muted/20 transition-colors">
                        <td className="px-4 py-2.5 font-medium text-foreground">{r.name}</td>
                        <td className="px-4 py-2.5 text-muted-foreground">{r.parentName || "—"}</td>
                        <td className="px-4 py-2.5 text-muted-foreground whitespace-nowrap">
                          {r.modifiedAt ? new Date(r.modifiedAt).toLocaleDateString("en-AU", { day: "2-digit", month: "short", year: "numeric" }) : "—"}
                        </td>
                        <td className="px-4 py-2.5 text-muted-foreground">{fmtSize(r.size)}</td>
                        <td className="px-4 py-2.5">
                          <a
                            href={`${API_BASE}/api/box/file/${r.id}`}
                            download={r.name}
                            className="flex items-center gap-1 text-accent hover:underline whitespace-nowrap"
                          >
                            <FileText className="w-3 h-3" /> Download
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
        {/* Default Box output folder */}
        <div className="rounded-sm border border-border bg-card p-4 flex items-center gap-4">
          <div className="flex-1">
            <p className="text-sm font-medium text-foreground">Default Box output folder</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              All generated reports are saved here automatically, regardless of review source.
            </p>
            {defaultFolder && (
              <p className="text-xs text-accent mt-1 font-medium">{defaultFolder.name}</p>
            )}
          </div>
          <button
            onClick={openFolderPicker}
            className="shrink-0 px-3 py-1.5 text-xs font-medium border border-border rounded-sm hover:bg-muted/50 transition-colors"
          >
            {defaultFolder ? "Change folder" : "Set folder"}
          </button>
        </div>

        {/* Folder picker modal */}
        {folderPickerOpen && (
          <>
            <div className="fixed inset-0 z-40 bg-black/30" onClick={() => setFolderPickerOpen(false)} />
            <div className="fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[480px] max-h-[70vh] bg-background border border-border rounded-sm shadow-2xl flex flex-col">
              <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                <p className="text-sm font-semibold text-foreground">Select output folder</p>
                <button onClick={() => setFolderPickerOpen(false)} className="text-muted-foreground hover:text-foreground text-lg leading-none">×</button>
              </div>
              {/* Breadcrumb */}
              <div className="flex items-center gap-1 px-4 py-2 text-xs text-muted-foreground border-b border-border flex-wrap">
                {folderPath.map((crumb, i) => (
                  <span key={crumb.id} className="flex items-center gap-1">
                    {i > 0 && <span>/</span>}
                    <button
                      onClick={() => loadFolderPicker(crumb.id, folderPath.slice(0, i + 1))}
                      className={i === folderPath.length - 1 ? "text-foreground font-medium" : "hover:text-foreground transition-colors"}
                    >
                      {crumb.name}
                    </button>
                  </span>
                ))}
              </div>
              {/* Current folder as selectable option */}
              <div className="px-4 pt-3 pb-1">
                <button
                  onClick={() => selectFolder(folderPath[folderPath.length - 1].id, folderPath[folderPath.length - 1].name)}
                  className="w-full text-left px-3 py-2 text-sm bg-accent/5 border border-accent/30 rounded-sm text-accent font-medium hover:bg-accent/10 transition-colors"
                >
                  Use "{folderPath[folderPath.length - 1].name}"
                </button>
              </div>
              <div className="flex-1 overflow-y-auto divide-y divide-border px-2 pb-2">
                {folderLoading ? (
                  <div className="flex items-center gap-2 px-2 py-4 text-sm text-muted-foreground">
                    <Loader2 className="w-4 h-4 animate-spin" /> Loading…
                  </div>
                ) : folderItems.length === 0 ? (
                  <p className="px-2 py-4 text-sm text-muted-foreground">No subfolders here.</p>
                ) : folderItems.map(item => (
                  <button
                    key={item.id}
                    onClick={() => loadFolderPicker(item.id, [...folderPath, { id: item.id, name: item.name }])}
                    className="w-full text-left px-3 py-2.5 flex items-center gap-2 text-sm hover:bg-muted/50 transition-colors rounded-sm"
                  >
                    <FolderOpen className="w-4 h-4 text-accent shrink-0" />
                    <span className="flex-1 truncate text-foreground">{item.name}</span>
                    <span className="text-muted-foreground text-xs">→</span>
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
