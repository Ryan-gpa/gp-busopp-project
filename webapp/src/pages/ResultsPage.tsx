import { useState, useEffect } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { ArrowLeft, Loader2, Download, FileText } from "lucide-react"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { SummaryCards } from "@/components/app/SummaryCards"
import { DisclosuresTab } from "@/components/app/DisclosuresTab"
import { CorporateActivityTab } from "@/components/app/CorporateActivityTab"
import { OpportunitiesTab } from "@/components/app/OpportunitiesTab"
import { TypeConfigPanel } from "@/components/app/TypeConfigPanel"
import AnnouncementViewer from "@/components/app/AnnouncementViewer"
import type { FindingsJSON, UserPrefs, AsxItem, CurrentUser } from "@/types"

interface LocationState {
  findings: FindingsJSON
  auditId?: string
}

interface Props {
  currentUser: CurrentUser | null
}

export default function ResultsPage({ currentUser }: Props) {
  const location = useLocation()
  const navigate = useNavigate()
  const state = location.state as LocationState | null
  const API_BASE = import.meta.env.VITE_API_URL || ""

  const findings = state?.findings
  const auditId = state?.auditId ?? ""
  const allKeys = findings
    ? (findings.asx.items.map(i => i.documentKey).filter(Boolean) as string[])
    : []

  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(() => new Set(allKeys))
  const [generating, setGenerating] = useState(false)
  const [generateError, setGenerateError] = useState("")
  const [docxName, setDocxName] = useState<string | null>(null)
  const [pdfName, setPdfName] = useState<string | null>(null)
  const [boxUploaded, setBoxUploaded] = useState(false)
  const [prefs, setPrefs] = useState<UserPrefs | null>(null)
  const [configPanelOpen, setConfigPanelOpen] = useState(false)
  const [activeAnn, setActiveAnn] = useState<AsxItem | null>(null)

  // Load prefs on mount and auto-apply excluded types
  useEffect(() => {
    if (!findings) return
    fetch(`${API_BASE}/api/prefs`)
      .then(r => r.json())
      .then((p: UserPrefs) => {
        setPrefs(p)
        if (p.excludedTypes.length > 0) {
          const excludedSet = new Set(p.excludedTypes)
          setSelectedKeys(prev => {
            const next = new Set(prev)
            for (const item of findings.asx.items) {
              if (item.documentKey && excludedSet.has(item.type)) {
                next.delete(item.documentKey)
              }
            }
            return next
          })
        }
      })
      .catch(() => {
        setPrefs({ version: "1.0", excludedTypes: [], typeHistory: {} })
      })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!findings) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-4">
          <p className="text-muted-foreground">No results to display.</p>
          <Button onClick={() => navigate("/")}>Run a new review</Button>
        </div>
      </div>
    )
  }

  const handleToggleKey = (key: string) => {
    setSelectedKeys(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const handleSelectAll = () => setSelectedKeys(new Set(allKeys))
  const handleDeselectAll = () => setSelectedKeys(new Set())

  // Record per-type include/exclude stats from this session
  const recordSessionStats = async () => {
    const typeGroups = new Map<string, { included: number; excluded: number }>()
    for (const item of findings.asx.items) {
      if (!item.documentKey || !item.type) continue
      const grp = typeGroups.get(item.type) ?? { included: 0, excluded: 0 }
      if (selectedKeys.has(item.documentKey)) grp.included++
      else grp.excluded++
      typeGroups.set(item.type, grp)
    }
    const typeStats: Record<string, string> = {}
    for (const [type, { included, excluded }] of typeGroups) {
      if (included > 0 && excluded > 0) typeStats[type] = "mixed"
      else if (excluded > 0) typeStats[type] = "excluded"
      else typeStats[type] = "included"
    }
    try {
      const res = await fetch(`${API_BASE}/api/prefs/record`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ typeStats }),
      })
      const updated = await res.json() as UserPrefs
      setPrefs(updated)
    } catch {
      // non-critical
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    setGenerateError("")
    setDocxName(null)
    setPdfName(null)

    // Build per-type exclusion summary for the document scope note
    const typeStats = new Map<string, { total: number; selected: number; rag: string }>()
    for (const item of findings.asx.items) {
      if (!item.type || !item.documentKey) continue
      const existing = typeStats.get(item.type) ?? { total: 0, selected: 0, rag: item.rag }
      existing.total++
      if (selectedKeys.has(item.documentKey)) existing.selected++
      typeStats.set(item.type, existing)
    }
    const excludedTypeInfo = Array.from(typeStats.entries())
      .filter(([, s]) => s.selected < s.total)
      .map(([type, s]) => ({ type, total: s.total, excluded: s.total - s.selected, rag: s.rag }))
      .sort((a, b) => b.excluded - a.excluded)

    try {
      const res = await fetch(`${API_BASE}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selectedKeys: Array.from(selectedKeys), excludedTypeInfo, auditId }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
        throw new Error(data.detail || `HTTP ${res.status}`)
      }
      const data = await res.json() as { docxName: string; pdfName?: string | null; boxUploaded?: boolean }
      setDocxName(data.docxName)
      setPdfName(data.pdfName ?? null)
      setBoxUploaded(data.boxUploaded ?? false)
      await recordSessionStats()
    } catch (err: unknown) {
      setGenerateError(err instanceof Error ? err.message : String(err))
    } finally {
      setGenerating(false)
    }
  }

  const handleSavePrefs = async (excludedTypes: string[]) => {
    try {
      const res = await fetch(`${API_BASE}/api/prefs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ excludedTypes }),
      })
      const updated = await res.json() as UserPrefs
      setPrefs(updated)
      // Re-apply to current selectedKeys: start from all, remove excluded types
      const excludedSet = new Set(excludedTypes)
      setSelectedKeys(() => {
        const next = new Set(allKeys)
        for (const item of findings.asx.items) {
          if (item.documentKey && excludedSet.has(item.type)) {
            next.delete(item.documentKey)
          }
        }
        return next
      })
    } catch {
      // non-critical
    }
    setConfigPanelOpen(false)
  }

  const totalAnnouncements = findings.asx.items.filter(i => i.documentKey).length

  return (
    <div className="min-h-screen bg-background pb-24">
      {/* Header */}
      <header className="bg-[hsl(var(--navy-deep))] text-primary-foreground">
        <div className="max-w-6xl mx-auto px-6 py-5 flex items-center gap-4">
          <button
            onClick={() => navigate("/")}
            className="flex items-center gap-1.5 text-sm text-primary-foreground/60 hover:text-primary-foreground transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> New review
          </button>
          <span className="text-primary-foreground/20">|</span>
          <span className="font-heading text-xl font-light">Growth Partners — Disclosure Review</span>
          <button
            onClick={() => navigate("/votes")}
            className="ml-auto flex items-center gap-1.5 text-sm text-primary-foreground/60 hover:text-primary-foreground transition-colors"
          >
            Vote history
          </button>
        </div>
      </header>

      <main className={`${activeAnn ? "max-w-[1600px]" : "max-w-6xl"} mx-auto px-6 py-8 transition-all duration-300`}>
        <div className="flex gap-6 items-start">
          <div className={`transition-all duration-300 ${activeAnn ? "w-3/5 shrink-0" : "w-full"}`}>
            <Tabs defaultValue="summary">
              <TabsList className="mb-6 w-full justify-start">
                <TabsTrigger value="summary">Summary</TabsTrigger>
                <TabsTrigger value="disclosures">
                  Disclosures
                  {findings.summary.not_found > 0 && (
                    <span className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full text-xs status-notfound">
                      {findings.summary.not_found}
                    </span>
                  )}
                </TabsTrigger>
                <TabsTrigger value="activity">
                  Corporate Activity
                  <span className="ml-2 text-xs text-muted-foreground">
                    ({selectedKeys.size}/{totalAnnouncements})
                  </span>
                </TabsTrigger>
                <TabsTrigger value="opportunities">Opportunities</TabsTrigger>
              </TabsList>

              <TabsContent value="summary">
                <SummaryCards findings={findings} />
              </TabsContent>

              <TabsContent value="disclosures">
                <DisclosuresTab findings={findings} />
              </TabsContent>

              <TabsContent value="activity">
                <CorporateActivityTab
                  findings={findings}
                  selectedKeys={selectedKeys}
                  onToggleKey={handleToggleKey}
                  onSelectAll={handleSelectAll}
                  onDeselectAll={handleDeselectAll}
                  onOpenConfig={() => setConfigPanelOpen(true)}
                  onSelectAnnouncement={setActiveAnn}
                />
              </TabsContent>

              <TabsContent value="opportunities">
                <OpportunitiesTab
                  findings={findings}
                  onSelectAnnouncement={setActiveAnn}
                />
              </TabsContent>
            </Tabs>
          </div>

          {activeAnn && (
            <div className="w-2/5 shrink-0 sticky top-6">
              <AnnouncementViewer
                announcement={activeAnn}
                checklistItems={findings.results}
                onClose={() => setActiveAnn(null)}
                currentUser={currentUser}
              />
            </div>
          )}
        </div>
      </main>

      {/* Sticky generate bar */}
      <div className="fixed bottom-0 left-0 right-0 z-30 bg-card border-t border-border shadow-lg">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex flex-col">
            <span className="text-sm font-medium text-foreground">
              {selectedKeys.size} of {totalAnnouncements} announcements selected for report
            </span>
            {generateError && (
              <span className="text-xs text-destructive mt-0.5">{generateError}</span>
            )}
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {boxUploaded && (
              <span className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-sm">
                Saved to Box
              </span>
            )}
            {pdfName && (
              <a
                href={`${API_BASE}/api/download/${encodeURIComponent(pdfName)}`}
                download={pdfName}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-accent text-white rounded-sm hover:bg-accent/90 transition-colors"
              >
                <Download className="w-4 h-4" />
                Download PDF
              </a>
            )}
            {docxName && (
              <a
                href={`${API_BASE}/api/download/${encodeURIComponent(docxName)}`}
                download={docxName}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium border border-accent text-accent rounded-sm hover:bg-accent/5 transition-colors"
              >
                <Download className="w-4 h-4" />
                Download Word
              </a>
            )}
            <Button onClick={handleGenerate} disabled={generating} size="default">
              {generating ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Generating…</>
              ) : (
                <><FileText className="w-4 h-4 mr-2" />Generate Report</>
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Type configuration panel */}
      {configPanelOpen && prefs && (
        <TypeConfigPanel
          findings={findings}
          prefs={prefs}
          onClose={() => setConfigPanelOpen(false)}
          onSave={handleSavePrefs}
        />
      )}

      {/* Config panel loading state — show gear button even before prefs loads */}
      {configPanelOpen && !prefs && (
        <>
          <div className="fixed inset-0 z-40 bg-black/20" onClick={() => setConfigPanelOpen(false)} />
          <div className="fixed right-0 top-0 bottom-0 z-50 w-[420px] bg-background border-l border-border shadow-2xl flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        </>
      )}
    </div>
  )
}
