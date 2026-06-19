import React, { useCallback, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Upload, FileText, ChevronDown, ChevronUp, Loader2, Globe } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"
import type { FindingsJSON } from "@/types"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"

type Stage = "idle" | "uploading" | "reviewing" | "building" | "done" | "error"

const STAGE_LABELS: Record<Stage, string> = {
  idle: "",
  uploading: "Uploading PDF…",
  reviewing: "Running checklist & fetching ASX announcements…",
  building: "Running checklist & fetching ASX announcements…",
  done: "Complete",
  error: "Failed",
}

const STAGE_PROGRESS: Record<Stage, number> = {
  idle: 0,
  uploading: 15,
  reviewing: 70,
  building: 70,
  done: 100,
  error: 0,
}

export default function UploadPage() {
  const navigate = useNavigate()
  const API_BASE = import.meta.env.VITE_API_URL || ""
  const [mode, setMode] = useState<"file" | "asx">("file")
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [stage, setStage] = useState<Stage>("idle")
  const [errorMsg, setErrorMsg] = useState("")
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [ticker, setTicker] = useState("")
  const [reportType, setReportType] = useState("auto")
  const [materiality, setMateriality] = useState("")
  const [includeAsx, setIncludeAsx] = useState(true)
  const [downloadAsx, setDownloadAsx] = useState(false)
  const [asOfPeriod, setAsOfPeriod] = useState(false)

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f?.type === "application/pdf") setFile(f)
  }, [])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) setFile(f)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (mode === "file" && !file) return
    if (mode === "asx" && !ticker.trim()) return

    setStage(mode === "file" ? "uploading" : "reviewing")
    setErrorMsg("")

    const form = new FormData()
    if (mode === "file" && file) {
      form.append("file", file)
    }
    form.append("ticker", ticker)
    form.append("report_type", mode === "asx" && reportType === "auto" ? "annual" : reportType)
    form.append("materiality", materiality)
    form.append("no_asx", String(!includeAsx))
    form.append("download_asx", String(downloadAsx))
    form.append("as_of_period", String(asOfPeriod))

    try {
      setStage("reviewing")
      const res = await fetch(`${API_BASE}/api/review`, { method: "POST", body: form })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || `HTTP ${res.status}`)
      }
      setStage("done")
      const data = await res.json() as { findings: FindingsJSON }
      navigate("/results", { state: { findings: data.findings } })
    } catch (err: unknown) {
      setStage("error")
      setErrorMsg(err instanceof Error ? err.message : String(err))
    }
  }

  const isRunning = stage !== "idle" && stage !== "error" && stage !== "done"

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-[hsl(var(--navy-deep))] text-primary-foreground">
        <div className="max-w-4xl mx-auto px-6 py-5 flex items-baseline gap-3">
          <span className="font-heading text-2xl font-light tracking-tight">Growth Partners</span>
          <span className="text-sm text-primary-foreground/50 font-sans">Disclosure Review</span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-12">
        <h1 className="font-heading text-4xl font-light text-foreground mb-2">
          ASX Disclosure Review
        </h1>
        <p className="text-muted-foreground mb-10 text-sm">
          Upload an Appendix 4D (half-year) or 4E (annual) report PDF to screen it against AASB&nbsp;/&nbsp;IFRS disclosure requirements.
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
          <Tabs defaultValue="file" value={mode} onValueChange={(val) => setMode(val as "file" | "asx")} className="w-full">
            <TabsList className="grid grid-cols-2 mb-6 bg-muted/60 p-1 rounded-sm">
              <TabsTrigger value="file" className="flex items-center gap-2 text-xs font-semibold py-2">
                <Upload className="w-4 h-4" />
                Upload PDF File
              </TabsTrigger>
              <TabsTrigger value="asx" className="flex items-center gap-2 text-xs font-semibold py-2">
                <Globe className="w-4 h-4" />
                Fetch via ASX Ticker
              </TabsTrigger>
            </TabsList>

            <TabsContent value="file" className="space-y-4 outline-none">
              {/* Drop zone */}
              <div
                onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                className={cn(
                  "border-2 border-dashed rounded-sm p-10 text-center cursor-pointer transition-colors outline-none",
                  dragging ? "border-accent bg-accent/5" : "border-border hover:border-accent/50",
                  file && "border-accent/40 bg-accent/5"
                )}
                onClick={() => document.getElementById("pdf-input")?.click()}
              >
                <input id="pdf-input" type="file" accept=".pdf" className="hidden" onChange={handleFileChange} />
                {file ? (
                  <div className="flex items-center justify-center gap-3 text-accent">
                    <FileText className="w-6 h-6 shrink-0" />
                    <span className="text-sm font-medium truncate max-w-xs">{file.name}</span>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <Upload className="w-8 h-8" />
                    <p className="text-sm">Drop a PDF here, or click to browse</p>
                    <p className="text-xs">Text-based PDFs only (scanned PDFs require OCR first)</p>
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="asx" className="space-y-4 outline-none">
              <div className="border border-border rounded-sm p-6 bg-card space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      ASX Ticker Code
                    </label>
                    <input
                      type="text"
                      value={ticker}
                      onChange={(e) => setTicker(e.target.value)}
                      placeholder="e.g. NVU"
                      required={mode === "asx"}
                      className="w-full h-10 px-3 text-sm border border-input rounded-sm bg-background focus:outline-none focus:ring-1 focus:ring-accent font-semibold placeholder:font-normal uppercase"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Report to Fetch
                    </label>
                    <select
                      value={reportType === "auto" ? "annual" : reportType}
                      onChange={(e) => setReportType(e.target.value)}
                      className="w-full h-10 px-3 text-sm border border-input rounded-sm bg-background focus:outline-none focus:ring-1 focus:ring-accent"
                    >
                      <option value="annual">Annual Report (Appendix 4E)</option>
                      <option value="interim">Half-Year Report (Appendix 4D)</option>
                    </select>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  The system will automatically query the ASX announcements database for the specified ticker, identify the latest publication matching the report type, and download it for review.
                </p>
              </div>
            </TabsContent>
          </Tabs>

          {/* Advanced options toggle */}
          <button
            type="button"
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            Advanced options
          </button>

          {showAdvanced && (
            <div className="border border-border rounded-sm p-5 space-y-4 bg-card">
              {mode === "file" && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">Ticker (override)</label>
                    <input
                      type="text"
                      value={ticker}
                      onChange={(e) => setTicker(e.target.value)}
                      placeholder="e.g. NVU"
                      className="w-full h-9 px-3 text-sm border border-input rounded-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">Report type</label>
                    <select
                      value={reportType}
                      onChange={(e) => setReportType(e.target.value)}
                      className="w-full h-9 px-3 text-sm border border-input rounded-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      <option value="auto">Auto-detect</option>
                      <option value="interim">Half-year (Appendix 4D)</option>
                      <option value="annual">Annual (Appendix 4E)</option>
                    </select>
                  </div>
                </div>
              )}
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">Planning materiality (AUD, optional)</label>
                <input
                  type="number"
                  value={materiality}
                  onChange={(e) => setMateriality(e.target.value)}
                  placeholder="e.g. 250000 — default: 5% of total assets"
                  className="w-full h-9 px-3 text-sm border border-input rounded-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={includeAsx} onChange={(e) => setIncludeAsx(e.target.checked)} className="rounded" />
                  Include ASX announcements (12-month history)
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={downloadAsx} onChange={(e) => setDownloadAsx(e.target.checked)} className="rounded" />
                  Download announcement PDFs locally
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={asOfPeriod} onChange={(e) => setAsOfPeriod(e.target.checked)} className="rounded" />
                  Anchor ASX window to report period-end (instead of today)
                </label>
              </div>
            </div>
          )}

          {/* Progress */}
          {isRunning && (
            <div className="space-y-2">
              <Progress value={STAGE_PROGRESS[stage]} />
              <p className="text-sm text-muted-foreground flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                {STAGE_LABELS[stage]}
              </p>
            </div>
          )}

          {/* Error */}
          {stage === "error" && (
            <div className="rounded-sm border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive whitespace-pre-wrap">
              {errorMsg}
            </div>
          )}

          <Button type="submit" disabled={(mode === "file" ? !file : !ticker.trim()) || isRunning} className="w-full" size="lg">
            {isRunning ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Running review…</>
            ) : (
              "Run review"
            )}
          </Button>
        </form>
      </main>
    </div>
  )
}
